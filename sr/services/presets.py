"""Vocal preset capture and apply.

A preset stores roles with singers referenced *by name* + weight + interval +
mix, so "Brian Big Chorus" can be dropped onto any section of any band.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.models.vocal import VocalAssignment, VocalRole

_ROLE_FIELDS = (
    "role_type", "ensemble_size", "width",
    "humanize_timing_ms", "humanize_pitch_cents", "humanize_formant",
)
_ASSIGN_FIELDS = (
    "weight_percent", "gain_db", "pan", "interval_semitones",
    "pitch_offset_semitones", "timing_offset_ms", "formant_shift", "style",
)


def capture_from_section(db: Session, section: SongSection) -> dict[str, Any]:
    names = {
        s.id: s.name
        for s in db.scalars(select(Singer).where(Singer.band_id == section.song.band_id))
    }
    roles = []
    for role in section.vocal_roles:
        roles.append(
            {
                **{f: getattr(role, f) for f in _ROLE_FIELDS},
                "processing": role.processing_json,
                "assignments": [
                    {"singer": names.get(a.singer_id, a.singer_id),
                     **{f: getattr(a, f) for f in _ASSIGN_FIELDS}}
                    for a in role.assignments
                ],
            }
        )
    return {"roles": roles}


def apply_to_section(
    db: Session, section: SongSection, spec: dict[str, Any]
) -> tuple[list[VocalRole], list[str]]:
    by_name = {
        s.name: s.id
        for s in db.scalars(select(Singer).where(Singer.band_id == section.song.band_id))
    }
    created: list[VocalRole] = []
    skipped: list[str] = []
    for role_spec in spec.get("roles", []):
        role = VocalRole(
            section_id=section.id,
            processing_json=role_spec.get("processing"),
            **{f: role_spec[f] for f in _ROLE_FIELDS if f in role_spec},
        )
        for a in role_spec.get("assignments", []):
            sid = by_name.get(a.get("singer"))
            if sid is None:
                skipped.append(a.get("singer", "?"))
                continue
            role.assignments.append(
                VocalAssignment(
                    singer_id=sid,
                    **{f: a[f] for f in _ASSIGN_FIELDS if f in a},
                )
            )
        if role.assignments:
            db.add(role)
            created.append(role)
    db.commit()
    for r in created:
        db.refresh(r)
    return created, sorted(set(skipped))
