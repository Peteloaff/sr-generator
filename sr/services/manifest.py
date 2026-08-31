"""Reproducible training-dataset manifest for a band.

Every approved reference must have complete, ready analysis before it can go in
the manifest. ``dataset_version`` is a deterministic hash of the included set +
analysis versions, so the same catalogue always produces the same manifest.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.models.band import Band
from sr.models.band_reference import BandReference

_REQUIRED = ("bpm", "key", "tuning", "duration")
MANIFEST_VERSION = 1


class IncompleteManifest(ValueError):
    def __init__(self, incomplete: list[dict]):
        self.incomplete = incomplete
        super().__init__(f"{len(incomplete)} approved reference(s) missing metadata")


def _missing(ref: BandReference) -> list[str]:
    missing = [f for f in _REQUIRED if getattr(ref, f) in (None, "")]
    if ref.analysis_status != "ready":
        missing.append(f"analysis ({ref.analysis_status})")
    return missing


def _approved(db: Session, band: Band) -> list[BandReference]:
    return list(
        db.scalars(
            select(BandReference)
            .where(
                BandReference.band_id == band.id,
                BandReference.approved_for_training.is_(True),
            )
            .order_by(BandReference.content_hash)
        )
    )


def completeness_report(db: Session, band: Band) -> list[dict]:
    return [
        {"id": r.id, "title": r.title, "missing": m}
        for r in _approved(db, band)
        if (m := _missing(r))
    ]


def build_manifest(db: Session, band: Band, *, strict: bool = True) -> dict[str, Any]:
    approved = _approved(db, band)
    incomplete = [
        {"id": r.id, "title": r.title, "missing": m} for r in approved if (m := _missing(r))
    ]
    if strict and incomplete:
        raise IncompleteManifest(incomplete)

    ready = [r for r in approved if not _missing(r)]
    entries = [
        {
            "id": r.id,
            "title": r.title,
            "content_hash": r.content_hash,
            "source_file": r.source_file,
            "duration": r.duration,
            "bpm": r.bpm,
            "key": r.key,
            "tuning": r.tuning,
            "quality_score": (r.quality_json or {}).get("score"),
            "analysis_provider": r.analysis_provider,
            "analysis_version": r.analysis_version,
        }
        for r in ready
    ]
    fingerprint = json.dumps(
        [
            {"h": e["content_hash"], "a": e["analysis_version"]}
            for e in sorted(entries, key=lambda e: e["content_hash"] or "")
        ],
        sort_keys=True,
    )
    dataset_version = hashlib.sha256(
        f"{MANIFEST_VERSION}|{band.slug}|{fingerprint}".encode()
    ).hexdigest()[:16]

    warnings = [
        f"{e['title']}: low quality score {e['quality_score']}"
        for e in entries
        if (e["quality_score"] or 1.0) < 0.6
    ]
    return {
        "manifest_version": MANIFEST_VERSION,
        "band_id": band.id,
        "band_slug": band.slug,
        "dataset_version": dataset_version,
        "references": entries,
        "totals": {
            "count": len(entries),
            "total_seconds": round(sum(e["duration"] or 0.0 for e in entries), 2),
        },
        "warnings": warnings,
        "incomplete": incomplete,
    }
