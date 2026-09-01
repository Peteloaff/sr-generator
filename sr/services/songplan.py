"""Deterministic song planner.

Turns a prompt (+ optional lyrics, band DNA, seed) into a concrete structure: an
ordered list of sections with type / bars / seconds / energy / key, a lyric-line
distribution, and a default vocal arrangement per section. Pure and seed-stable -
``sr/services/fullsong.py`` executes the plan; Stage 10 replaces the arrangement
heuristics with the intelligent arranger.
"""

from __future__ import annotations

from typing import Any

from sr.common.seeds import derive_seed
from sr.models.singer import Singer

_TEMPLATES = [
    ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"],
    ["intro", "verse", "pre_chorus", "chorus", "verse", "pre_chorus", "chorus",
     "breakdown", "chorus", "outro"],
    ["verse", "chorus", "verse", "chorus", "bridge", "chorus"],
    ["intro", "verse", "chorus", "breakdown", "chorus", "outro"],
]
_BARS = {
    "intro": 4, "verse": 8, "pre_chorus": 4, "chorus": 8, "post_chorus": 4,
    "bridge": 8, "breakdown": 8, "solo": 8, "outro": 4, "other": 8,
}
_ENERGY = {
    "intro": 0.30, "verse": 0.50, "pre_chorus": 0.66, "chorus": 0.90,
    "post_chorus": 0.78, "bridge": 0.55, "breakdown": 0.95, "solo": 0.80,
    "outro": 0.35, "other": 0.6,
}
_KEYS = ["C major", "G major", "D major", "A minor", "E minor", "B minor", "F major"]
_LYRIC_SECTIONS = {"verse", "pre_chorus", "chorus", "bridge", "breakdown"}


def _words(prompt: str) -> list[str]:
    toks = [w.strip(".,!?;:").lower() for w in (prompt or "").split() if w.strip(".,!?;:")]
    return toks or ["the", "night", "we", "run", "burning", "louder", "again", "now"]


def _scaffold_lines(prompt: str, n_lines: int, seed: int) -> list[str]:
    words = _words(prompt)
    lines: list[str] = []
    for i in range(n_lines):
        pick = [words[derive_seed(seed, "w", i, j) % len(words)] for j in range(4)]
        lines.append(" ".join(pick))
    return lines


def plan_song(
    *,
    prompt: str,
    lyrics: str | None = None,
    bpm: float | None = None,
    seed: int,
    dna: dict | None = None,
    section_seconds: float | None = None,
    structure: list[str] | None = None,
) -> dict[str, Any]:
    dna = dna or {}
    tpl = structure or _TEMPLATES[derive_seed(seed, "structure") % len(_TEMPLATES)]
    bpm = float(bpm or (dna.get("bpm") or {}).get("median") or 120.0)
    key_dist = dna.get("key_distribution") or {}
    key = next(iter(key_dist), None) or _KEYS[derive_seed(seed, "key") % len(_KEYS)]
    beat = 60.0 / bpm

    sections: list[dict] = []
    cursor = 0.0
    chorus_i = 0
    for stype in tpl:
        bars = _BARS.get(stype, 8)
        seconds = round(section_seconds or bars * 4 * beat, 3)
        name = None
        if stype == "chorus":
            chorus_i += 1
            name = f"Chorus {chorus_i}"
        elif stype == "verse":
            name = f"Verse {sum(1 for s in sections if s['type'] == 'verse') + 1}"
        sections.append({
            "type": stype,
            "name": name,
            "bars": bars,
            "seconds": seconds,
            "start": round(cursor, 3),
            "end": round(cursor + seconds, 3),
            "energy": _ENERGY.get(stype, 0.6),
        })
        cursor += seconds

    # --- lyric lines -------------------------------------------------------
    lyric_source = "provided" if lyrics and lyrics.strip() else "scaffold"
    lyric_sections = [i for i, s in enumerate(sections) if s["type"] in _LYRIC_SECTIONS]
    lines_out: list[dict] = []
    order = 0
    if lyric_source == "provided":
        blocks = [b.strip() for b in lyrics.split("\n\n") if b.strip()]
        if not blocks:
            blocks = [lyrics.strip()]
        for pos, sec_i in enumerate(lyric_sections):
            block = blocks[pos % len(blocks)]
            for text in block.splitlines():
                lines_out.append({"section": sec_i, "order": order, "text": text})
                order += 1
    else:
        # one scaffold block per unique lyric section-type, choruses share theirs
        chorus_block = _scaffold_lines(prompt, 4, derive_seed(seed, "lyr", "chorus"))
        for sec_i in lyric_sections:
            stype = sections[sec_i]["type"]
            if stype == "chorus":
                block = chorus_block
            else:
                nlines = 4 if stype in ("verse", "breakdown") else 2
                block = _scaffold_lines(prompt, nlines, derive_seed(seed, "lyr", sec_i))
            for text in block:
                lines_out.append({"section": sec_i, "order": order, "text": text})
                order += 1

    return {
        "prompt": prompt,
        "bpm": round(bpm, 2),
        "key": key,
        "template": tpl,
        "sections": sections,
        "lyric_lines": lines_out,
        "lyrics_source": lyric_source,
        "duration": round(cursor, 3),
        "seed": seed,
    }


# --- default arrangement (Stage 8 heuristic; Stage 10 supersedes) ---------

def default_arrangement(
    section: dict, singers: list[Singer], section_index: int, seed: int
) -> list[dict[str, Any]]:
    consenting = [s for s in singers if s.consent_generation]
    if not consenting:
        return []
    stype = section["type"]
    energy = section["energy"]
    lead = consenting[section_index % len(consenting)]
    roles: list[dict] = [{
        "role_type": "lead", "ensemble_size": 1, "width": 0.0,
        "assignments": [{"singer_id": lead.id, "weight_percent": 100.0}],
    }]

    if stype in ("chorus", "breakdown", "post_chorus") and len(consenting) >= 1:
        size = 10 if stype == "breakdown" else 8
        primary = 50.0
        rest = consenting
        share = (100.0 - primary) / max(1, len(rest) - 1) if len(rest) > 1 else 0.0
        assigns = [
            {
                "singer_id": s.id,
                "weight_percent": primary if s.id == lead.id else round(share, 2),
            }
            for s in rest
        ]
        roles.append({
            "role_type": "gang" if stype == "breakdown" else "background",
            "ensemble_size": size,
            "width": 70.0,
            "humanize_timing_ms": 20.0,
            "humanize_pitch_cents": 7.0,
            "assignments": assigns,
        })

    if stype == "chorus" and len(consenting) >= 2:
        harm = consenting[(section_index + 1) % len(consenting)]
        interval = 3.0 if derive_seed(seed, "harm", section_index) % 2 else 7.0
        roles.append({
            "role_type": "harmony", "ensemble_size": 2, "width": 40.0,
            "humanize_pitch_cents": 4.0,
            "assignments": [{
                "singer_id": harm.id, "weight_percent": 100.0,
                "interval_semitones": interval,
            }],
        })

    if stype == "verse" and energy >= 0.5 and len(consenting) >= 2:
        dbl = consenting[(section_index + 1) % len(consenting)]
        roles.append({
            "role_type": "double", "ensemble_size": 1, "width": 25.0,
            "assignments": [{
                "singer_id": dbl.id, "weight_percent": 100.0,
                "interval_semitones": -12.0,
            }],
        })
    return roles
