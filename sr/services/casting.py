"""Resolve which player performs each instrument in a section.

A section-specific ``InstrumentSlot`` wins over the whole-song default. The
resolved value is an *effective* style profile: the player's learned style, then
the slot's dials (busier / brighter / harder / push / swing), then the
``explore`` knob (0 = faithful, 1 = wander), then gain / mute.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.playerstyle import StyleProfile
from sr.common.seeds import bounded_jitter, derive_seed
from sr.models.instrument_slot import InstrumentSlot
from sr.models.player import Player
from sr.models.song import SongSection

# dial name -> (style-profile field it pushes, how far a full dial moves it)
_DIAL_TARGET = {
    "busier": ("busyness", 0.5),
    "brighter": ("brightness", 0.6),
    "harder": ("drive", 0.5),
    "push": ("attack", 0.4),
    "swing": ("swing", 0.5),
}
_EXPLORE_FIELDS = ("drive", "brightness", "busyness", "attack", "sustain", "swing", "syncopation")


def _clamp(field: str, v: float) -> float:
    lo, hi = (-1.0, 1.0) if field == "brightness" else (0.0, 1.0)
    return float(min(hi, max(lo, v)))


def _apply_dials(prof: dict, dials: dict | None) -> dict:
    if not dials:
        return prof
    out = dict(prof)
    for dial, (field, scale) in _DIAL_TARGET.items():
        d = float(dials.get(dial) or 0.0)
        if d:
            out[field] = _clamp(field, float(out.get(field, 0.5)) + d * scale)
    return out


def _explore(prof: dict, amount: float, seed: int) -> dict:
    if amount <= 0:
        return prof
    out = dict(prof)
    for i, field in enumerate(_EXPLORE_FIELDS):
        j = bounded_jitter(derive_seed(seed, "explore", i), -1.0, 1.0) * amount * 0.4
        out[field] = _clamp(field, float(out.get(field, 0.5)) + j)
    return out


def resolve_section_players(db: Session, section: SongSection, *, seed: int) -> dict[str, dict]:
    slots = list(
        db.scalars(
            select(InstrumentSlot).where(InstrumentSlot.song_id == section.song_id)
        )
    )
    by_role: dict[str, InstrumentSlot] = {}
    for s in slots:
        if s.section_id == section.id:
            by_role[s.role] = s
        elif s.section_id is None:
            by_role.setdefault(s.role, s)

    out: dict[str, dict] = {}
    for role, slot in by_role.items():
        if slot.muted:
            out[role] = {"mute": True}
            continue
        if not slot.player_id:
            continue
        player = db.get(Player, slot.player_id)
        if player is None or not player.consent_generation:
            continue
        base = player.style_profile_json or StyleProfile(role=role).to_dict()
        eff = _apply_dials(dict(base), slot.dials_json)
        eff = _explore(
            eff, float(slot.explore or 0.0),
            derive_seed(seed, "sec", section.id, role),
        )
        eff["gain_db"] = float(slot.gain_db or 0.0)
        eff["player_id"] = player.id
        eff["player_name"] = player.name
        out[role] = eff
    return out
