"""Stage 9 - surgical regeneration.

Regenerate one section, or one vocal role (optionally swapping its singer),
without touching anything else. Section renders are already isolated (a render
only writes its own section's assets); role regeneration re-renders the section
but perturbs only the target role's plan seed, so every other role's stems come
out byte-identical (the layering engine is deterministic).

Every regeneration writes a ``SectionRevision`` snapshot so edits can be rolled
back. Locked sections refuse regeneration.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.seeds import derive_seed
from sr.models.generation_job import GenerationJob
from sr.models.section_revision import SectionRevision
from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.models.vocal import VocalAssignment, VocalRole
from sr.providers.base import ProviderResult
from sr.services.consent import blocked_for_generation
from sr.services.render import render_section

ENGINE_VERSION = "regen-0.9.0"

_ROLE_FIELDS = (
    "role_type", "ensemble_size", "width",
    "humanize_timing_ms", "humanize_pitch_cents", "humanize_formant", "notes",
)
_ASSIGN_FIELDS = (
    "singer_id", "weight_percent", "gain_db", "pan", "interval_semitones",
    "pitch_offset_semitones", "timing_offset_ms", "formant_shift", "style", "seed",
)


def snapshot_roles(section: SongSection) -> list[dict]:
    return [
        {
            **{f: getattr(r, f) for f in _ROLE_FIELDS},
            "processing": r.processing_json,
            "assignments": [
                {f: getattr(a, f) for f in _ASSIGN_FIELDS} for a in r.assignments
            ],
        }
        for r in section.vocal_roles
    ]


def restore_roles(db: Session, section: SongSection, snapshot: list[dict]) -> None:
    for role in list(section.vocal_roles):
        db.delete(role)
    db.flush()
    for rspec in snapshot or []:
        role = VocalRole(
            section_id=section.id,
            processing_json=rspec.get("processing"),
            **{f: rspec[f] for f in _ROLE_FIELDS if f in rspec},
        )
        for a in rspec.get("assignments", []):
            role.assignments.append(
                VocalAssignment(**{f: a[f] for f in _ASSIGN_FIELDS if f in a})
            )
        db.add(role)
    db.flush()


def record_revision(
    db: Session,
    section: SongSection,
    *,
    kind: str,
    render_job_id: str | None,
    note: str | None = None,
    changed_role_id: str | None = None,
) -> SectionRevision:
    prior = list(
        db.scalars(
            select(SectionRevision).where(SectionRevision.section_id == section.id)
        )
    )
    for rev in prior:
        rev.is_current = False
    rev = SectionRevision(
        section_id=section.id,
        revision=max((r.revision for r in prior), default=0) + 1,
        kind=kind,
        roles_snapshot_json=snapshot_roles(section),
        render_job_id=render_job_id,
        changed_role_id=changed_role_id,
        note=note,
        is_current=True,
    )
    db.add(rev)
    db.flush()
    return rev


def _guard_unlocked(section: SongSection) -> None:
    if section.locked:
        raise PermissionError(
            f"section {section.name or section.section_type!r} is locked; unlock it to regenerate"
        )


def regenerate_section(
    db: Session, job: GenerationJob, *, section_id: str, seed: int, params: dict
) -> ProviderResult:
    section = db.get(SongSection, section_id)
    if section is None:
        raise LookupError(f"section {section_id} not found")
    _guard_unlocked(section)

    result = render_section(db, job, section_id=section_id, seed=seed, params={})
    rev = record_revision(
        db, section, kind="full", render_job_id=job.id, note=params.get("note")
    )
    meta = dict(result.metadata)
    meta.update({"regen": "section", "revision": rev.revision})
    return ProviderResult(
        provider="regen-engine", provider_version=ENGINE_VERSION, outputs=[],
        metadata=meta,
        logs=[*result.logs, f"section regenerated -> revision {rev.revision}"],
    )


def regenerate_role(
    db: Session, job: GenerationJob, *, role_id: str, seed: int, params: dict
) -> ProviderResult:
    role = db.get(VocalRole, role_id)
    if role is None:
        raise LookupError(f"role {role_id} not found")
    if role.section_id is None:
        raise ValueError("only section-scoped roles can be regenerated in isolation")
    section = db.get(SongSection, role.section_id)
    _guard_unlocked(section)

    kind = "role"
    swap_to = params.get("swap_to_singer_id")
    if swap_to:
        target = None
        want_from = params.get("swap_from_singer_id")
        for a in role.assignments:
            if want_from and a.singer_id != want_from:
                continue
            target = a
            break
        if target is None:
            raise ValueError("no matching assignment to swap on this role")
        new_singer = db.get(Singer, swap_to)
        if new_singer is None or new_singer.band_id != section.song.band_id:
            raise ValueError("swap target singer not found in this band")
        blocked = blocked_for_generation([new_singer])
        if blocked:
            raise PermissionError(f"consent_generation missing for: {', '.join(blocked)}")
        target.singer_id = swap_to
        db.flush()
        kind = "swap"

    salt = params.get("seed") or derive_seed(seed, "reroll", role_id)
    result = render_section(
        db, job, section_id=section.id, seed=seed,
        params={"role_seed_salt": {role_id: salt}},
    )
    rev = record_revision(
        db, section, kind=kind, render_job_id=job.id,
        note=params.get("note"), changed_role_id=role_id,
    )
    meta = dict(result.metadata)
    meta.update({"regen": kind, "role_id": role_id, "revision": rev.revision})
    return ProviderResult(
        provider="regen-engine", provider_version=ENGINE_VERSION, outputs=[],
        metadata=meta,
        logs=[*result.logs, f"role {role.role_type} {kind} -> revision {rev.revision}"],
    )


def rollback_section(db: Session, section: SongSection, revision: int) -> SectionRevision:
    target = db.scalar(
        select(SectionRevision).where(
            SectionRevision.section_id == section.id,
            SectionRevision.revision == revision,
        )
    )
    if target is None:
        raise LookupError(f"section has no revision {revision}")
    _guard_unlocked(section)
    restore_roles(db, section, target.roles_snapshot_json or [])
    db.refresh(section)
    rev = record_revision(
        db, section, kind="rollback", render_job_id=target.render_job_id,
        note=f"rolled back to revision {revision}",
    )
    db.commit()
    return rev
