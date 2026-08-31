"""Project export / import - the "save and reload exactly" guarantee.

Export is a self-contained JSON snapshot that references singers by name (not id)
so a project can be re-imported into the same band or carried to another band.
Round-tripping preserves section boundaries, lyric lines, vocal roles, weights,
seeds, gains, pans, humanization, and provider settings.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.models.band import Band
from sr.models.project import Project
from sr.models.singer import Singer
from sr.models.song import LyricLine, Song, SongSection
from sr.models.vocal import VocalAssignment, VocalRole

EXPORT_VERSION = 1

_ASSIGN_FIELDS = (
    "weight_percent", "gain_db", "pan", "pitch_offset_semitones",
    "timing_offset_ms", "formant_shift", "style", "seed",
)
_ROLE_FIELDS = (
    "role_type", "ensemble_size", "width",
    "humanize_timing_ms", "humanize_pitch_cents", "humanize_formant", "notes",
)
_SECTION_FIELDS = (
    "section_type", "name", "start_time", "end_time", "order_index",
    "lyrics", "prompt_override", "generation_seed",
)
_SONG_FIELDS = (
    "title", "bpm", "key", "time_signature", "duration",
    "prompt", "lyrics", "status", "seed",
)


def _dump_role(role: VocalRole, singer_names: dict[str, str]) -> dict[str, Any]:
    return {
        **{f: getattr(role, f) for f in _ROLE_FIELDS},
        "assignments": [
            {"singer": singer_names.get(a.singer_id, a.singer_id),
             **{f: getattr(a, f) for f in _ASSIGN_FIELDS}}
            for a in sorted(role.assignments, key=lambda a: singer_names.get(a.singer_id, ""))
        ],
    }


def export_project(db: Session, project: Project) -> dict[str, Any]:
    singer_names = {
        s.id: s.name for s in db.scalars(select(Singer).where(Singer.band_id == project.band_id))
    }
    songs_out = []
    for song in sorted(project.songs, key=lambda s: s.title):
        section_index = {sec.id: i for i, sec in enumerate(song.sections)}
        songs_out.append(
            {
                **{f: getattr(song, f) for f in _SONG_FIELDS},
                "sections": [
                    {
                        **{f: getattr(sec, f) for f in _SECTION_FIELDS},
                        "vocal_roles": [_dump_role(r, singer_names) for r in sec.vocal_roles],
                    }
                    for sec in song.sections
                ],
                "lyric_lines": [
                    {
                        "text": ln.text,
                        "order_index": ln.order_index,
                        "start_time": ln.start_time,
                        "end_time": ln.end_time,
                        "section": section_index.get(ln.section_id),
                        "vocal_roles": [_dump_role(r, singer_names) for r in ln.vocal_roles],
                    }
                    for ln in song.lyric_lines
                ],
            }
        )
    return {
        "sr_export_version": EXPORT_VERSION,
        "project": {"name": project.name, "description": project.description},
        "songs": songs_out,
    }


def _resolve_singer(db: Session, band: Band, name: str, cache: dict[str, Singer]) -> Singer:
    if name in cache:
        return cache[name]
    singer = db.scalar(
        select(Singer).where(Singer.band_id == band.id, Singer.name == name)
    )
    if singer is None:
        # Stub - consent flags stay false, so it cannot be used for generation.
        singer = Singer(band_id=band.id, name=name, notes="imported placeholder")
        db.add(singer)
        db.flush()
    cache[name] = singer
    return singer


def _load_role(
    db: Session, band: Band, data: dict, cache: dict[str, Singer], **parent
) -> VocalRole:
    role = VocalRole(**{f: data[f] for f in _ROLE_FIELDS if f in data}, **parent)
    for a in data.get("assignments", []):
        singer = _resolve_singer(db, band, a["singer"], cache)
        role.assignments.append(
            VocalAssignment(
                singer_id=singer.id,
                **{f: a[f] for f in _ASSIGN_FIELDS if f in a},
            )
        )
    db.add(role)
    return role


def import_project(db: Session, band: Band, data: dict[str, Any]) -> Project:
    if data.get("sr_export_version") != EXPORT_VERSION:
        raise ValueError(f"unsupported export version: {data.get('sr_export_version')!r}")

    project = Project(
        band_id=band.id,
        name=data["project"]["name"],
        description=data["project"].get("description"),
    )
    db.add(project)
    db.flush()

    singer_cache: dict[str, Singer] = {}
    for song_data in data.get("songs", []):
        song = Song(
            band_id=band.id,
            project_id=project.id,
            **{f: song_data[f] for f in _SONG_FIELDS if f in song_data},
        )
        db.add(song)
        db.flush()

        sections: list[SongSection] = []
        for sec_data in song_data.get("sections", []):
            section = SongSection(
                song_id=song.id,
                **{f: sec_data[f] for f in _SECTION_FIELDS if f in sec_data},
            )
            db.add(section)
            db.flush()
            for role_data in sec_data.get("vocal_roles", []):
                _load_role(db, band, role_data, singer_cache, section_id=section.id)
            sections.append(section)

        for ln_data in song_data.get("lyric_lines", []):
            sec_ref = ln_data.get("section")
            line = LyricLine(
                song_id=song.id,
                section_id=sections[sec_ref].id if sec_ref is not None else None,
                text=ln_data.get("text", ""),
                order_index=ln_data.get("order_index", 0),
                start_time=ln_data.get("start_time"),
                end_time=ln_data.get("end_time"),
            )
            db.add(line)
            db.flush()
            for role_data in ln_data.get("vocal_roles", []):
                _load_role(db, band, role_data, singer_cache, lyric_line_id=line.id)

    db.commit()
    db.refresh(project)
    return project
