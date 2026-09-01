"""Stage 10 - intelligent vocal arranger.

Recommends lead / double / harmony / background / gang roles per section from
section energy, lyric density, and user-entered singer metadata (range,
preferred roles, energy fit). Every recommendation carries a confidence and a
plain-text rationale, and applying never overwrites existing roles unless the
caller explicitly asks.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp
from sr.common.allocation import largest_remainder_allocation
from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.singer import Singer
from sr.models.song import Song, SongSection
from sr.models.vocal import VocalAssignment, VocalRole

ARRANGER_VERSION = "arranger-0.10.0"

_TYPE_ENERGY = {
    "intro": 0.30, "verse": 0.50, "pre_chorus": 0.66, "chorus": 0.90,
    "post_chorus": 0.80, "bridge": 0.55, "breakdown": 0.95, "solo": 0.80,
    "outro": 0.35, "other": 0.60,
}
# nominal melodic centre per section family, as MIDI note numbers
_TYPE_RANGE = {
    "chorus": (57, 66), "post_chorus": (57, 66), "breakdown": (52, 62),
    "verse": (52, 61), "pre_chorus": (55, 64), "bridge": (53, 62),
    "intro": (52, 60), "outro": (52, 60), "solo": (55, 65), "other": (54, 63),
}
_LEAD_ROLE_TAG = {
    "chorus": "chorus_lead", "post_chorus": "chorus_lead", "verse": "verse_lead",
    "pre_chorus": "verse_lead", "bridge": "verse_lead", "breakdown": "scream",
    "intro": "verse_lead", "outro": "verse_lead", "solo": "chorus_lead", "other": "verse_lead",
}


def _energy_band(e: float) -> str:
    return "high" if e >= 0.75 else "mid" if e >= 0.45 else "low"


def _section_energy(db: Session, section: SongSection) -> float:
    bed = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section.id,
            AudioAsset.asset_type.in_(("instrumental_bed", "mix")),
        ).order_by(AudioAsset.created_at.desc())
    )
    if bed is not None:
        path = get_storage().path_for(bed.file_path)
        if path.exists():
            rms = dsp.rms_dbfs(dsp.load_stereo(path))
            return float(np.clip((rms + 30.0) / 24.0, 0.0, 1.0))
    return _TYPE_ENERGY.get(section.section_type, 0.6)


def _lyric_density(section: SongSection) -> float:
    if section.start_time is None or section.end_time is None:
        return 0.0
    span = max(1.0, float(section.end_time) - float(section.start_time))
    chars = sum(len(ln.text) for ln in section.lines)
    return round(chars / span, 2)


def _range_ok(singer: Singer, lo: int, hi: int) -> bool:
    if singer.range_low_midi is None or singer.range_high_midi is None:
        return False
    return singer.range_low_midi <= lo and singer.range_high_midi >= hi


def _score_lead(singer: Singer, stype: str, energy: float) -> tuple[float, list[str]]:
    prefs = set(singer.preferred_roles or [])
    tag = _LEAD_ROLE_TAG.get(stype, "verse_lead")
    band = _energy_band(energy)
    lo, hi = _TYPE_RANGE.get(stype, (54, 63))
    score, why = 0.0, []
    if tag in prefs:
        score += 2.0
        why.append(f"prefers {tag}")
    if tag == "scream" and singer.scream_enabled:
        score += 1.0
        why.append("scream enabled")
    if singer.energy_fit == band:
        score += 1.0
        why.append(f"{band}-energy fit")
    if _range_ok(singer, lo, hi):
        score += 0.5
        why.append("range covers the part")
    return score, why


def _mk_assign(singer_id: str, weight: float = 100.0, interval: float = 0.0) -> dict:
    return {
        "singer_id": singer_id,
        "weight_percent": round(weight, 2),
        "interval_semitones": interval,
    }


def _recommend_for_section(
    section: SongSection, index: int, energy: float, density: float,
    singers: list[Singer], seed: int,
) -> list[dict]:
    if not singers:
        return []
    stype = section.section_type
    by_id = {s.id: s for s in singers}
    order = sorted(singers, key=lambda s: s.name)

    scored = sorted(
        ((*_score_lead(s, stype, energy), s) for s in order),
        key=lambda t: (-t[0], t[2].name),
    )
    best_score, best_why, lead = scored[0]
    max_score = 4.5
    if best_score <= 0:
        lead = order[index % len(order)]
        lead_conf, lead_why = 0.3, "no matching metadata - round-robin default"
    else:
        lead_conf = round(min(1.0, 0.35 + best_score / max_score), 2)
        lead_why = ", ".join(best_why)

    recs: list[dict] = [{
        "role_type": "lead", "ensemble_size": 1, "width": 0.0,
        "humanize_timing_ms": 0.0, "humanize_pitch_cents": 0.0,
        "assignments": [_mk_assign(lead.id)],
        "confidence": lead_conf, "rationale": f"lead: {lead.name} ({lead_why})",
    }]

    others = [s for s in order if s.id != lead.id]
    chorus_like = stype in ("chorus", "post_chorus", "solo")
    heavy = stype == "breakdown"

    # double - octave under, when energy is up and someone likes doubling
    if (energy >= 0.6 or density >= 12) and others:
        dbl = next(
            (s for s in others if "octave_double" in (s.preferred_roles or [])), None
        )
        if dbl is not None:
            recs.append({
                "role_type": "double", "ensemble_size": 1, "width": 25.0,
                "humanize_timing_ms": 8.0, "humanize_pitch_cents": 3.0,
                "assignments": [_mk_assign(dbl.id, 100.0, -12.0)],
                "confidence": 0.7,
                "rationale": f"double: {dbl.name} at -12 (prefers octave doubling, high energy)",
            })

    # harmony - on choruses, prefer a singer tagged high/low harmony
    if chorus_like and others:
        hi_h = next((s for s in others if "high_harmony" in (s.preferred_roles or [])), None)
        lo_h = next((s for s in others if "low_harmony" in (s.preferred_roles or [])), None)
        h_singer = hi_h or lo_h or others[0]
        interval = 3.0 if hi_h or not lo_h else -4.0
        conf = 0.75 if (hi_h or lo_h) else 0.45
        recs.append({
            "role_type": "harmony", "ensemble_size": 2, "width": 45.0,
            "humanize_timing_ms": 10.0, "humanize_pitch_cents": 4.0,
            "assignments": [_mk_assign(h_singer.id, 100.0, interval)],
            "confidence": conf,
            "rationale": f"harmony: {h_singer.name} at {interval:+.0f} semitones",
        })

    # background / gang - choruses and breakdowns, size scales with energy
    if chorus_like or heavy:
        size = int(round(6 + energy * 8))
        pool = order
        weights = {}
        for s in pool:
            w = 1.0
            if s.id == lead.id:
                w += 2.0
            if "gang" in (s.preferred_roles or []):
                w += 1.5
            weights[s.id] = w
        total = sum(weights.values())
        assigns = [
            _mk_assign(sid, round(weights[sid] / total * 100.0, 2)) for sid in weights
        ]
        # sanity: the allocation must land on whole takes
        largest_remainder_allocation(
            {a["singer_id"]: a["weight_percent"] for a in assigns}, size,
            tie_break_order=sorted(weights),
        )
        recs.append({
            "role_type": "gang" if heavy else "background",
            "ensemble_size": size,
            "width": 80.0 if heavy else 65.0,
            "humanize_timing_ms": 24.0 if heavy else 18.0,
            "humanize_pitch_cents": 9.0 if heavy else 6.0,
            "assignments": assigns,
            "confidence": round(0.5 + energy * 0.4, 2),
            "rationale": (
                f"{'gang' if heavy else 'background'} ensemble of {size} "
                f"(section energy {energy:.2f})"
            ),
        })

    _ = (by_id, seed)  # reserved for future range-aware voicing
    return recs


def recommend_arrangement(db: Session, song: Song, *, seed: int) -> dict:
    singers = [
        s for s in db.scalars(select(Singer).where(Singer.band_id == song.band_id))
        if s.consent_generation
    ]
    sections_out = []
    for i, section in enumerate(song.sections):
        energy = _section_energy(db, section)
        density = _lyric_density(section)
        recs = _recommend_for_section(section, i, energy, density, singers, seed)
        sections_out.append({
            "section_id": section.id,
            "section_type": section.section_type,
            "name": section.name,
            "locked": section.locked,
            "energy": round(energy, 3),
            "energy_band": _energy_band(energy),
            "lyric_density": density,
            "has_roles": bool(section.vocal_roles),
            "recommendations": recs,
        })
    return {
        "song_id": song.id,
        "arranger_version": ARRANGER_VERSION,
        "seed": seed,
        "singers_considered": [s.name for s in singers],
        "sections": sections_out,
    }


_ROLE_FIELDS = (
    "role_type", "ensemble_size", "width",
    "humanize_timing_ms", "humanize_pitch_cents", "humanize_formant",
)
_ASSIGN_FIELDS = ("singer_id", "weight_percent", "interval_semitones")


def apply_arrangement(
    db: Session, song: Song, *, section_ids: list[str] | None, overwrite: bool, seed: int
) -> dict:
    plan = recommend_arrangement(db, song, seed=seed)
    wanted = set(section_ids) if section_ids else None
    applied, skipped = [], []
    for sec_plan in plan["sections"]:
        sid = sec_plan["section_id"]
        if wanted is not None and sid not in wanted:
            continue
        section = db.get(SongSection, sid)
        if section.locked:
            skipped.append({"section_id": sid, "reason": "locked"})
            continue
        if section.vocal_roles and not overwrite:
            skipped.append({"section_id": sid, "reason": "already has roles"})
            continue
        if section.vocal_roles and overwrite:
            for r in list(section.vocal_roles):
                db.delete(r)
            db.flush()
        n_roles = 0
        for rec in sec_plan["recommendations"]:
            role = VocalRole(
                section_id=sid, **{f: rec[f] for f in _ROLE_FIELDS if f in rec}
            )
            for a in rec["assignments"]:
                role.assignments.append(
                    VocalAssignment(**{f: a[f] for f in _ASSIGN_FIELDS if f in a})
                )
            db.add(role)
            n_roles += 1
        applied.append({"section_id": sid, "roles": n_roles})
    db.commit()
    return {
        "song_id": song.id,
        "applied": applied,
        "skipped": skipped,
        "overwrite": overwrite,
    }
