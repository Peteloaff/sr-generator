"""Band DNA: aggregate the analysed reference catalogue into a band profile."""

from __future__ import annotations

import statistics
from collections import Counter

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.models.band import Band
from sr.models.band_reference import BandReference


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "mean": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "n": len(values),
    }


def band_dna(db: Session, band: Band) -> dict:
    refs = list(
        db.scalars(select(BandReference).where(BandReference.band_id == band.id))
    )
    ready = [r for r in refs if r.analysis_status == "ready"]

    bpms = [r.bpm for r in ready if r.bpm]
    keys = Counter(r.key for r in ready if r.key)
    tunings = Counter(r.tuning for r in ready if r.tuning)
    tags = Counter(t for r in ready for t in (r.tags or []))

    embeds = [
        r.analysis_json["embedding"]
        for r in ready
        if r.analysis_json and r.analysis_json.get("embedding")
    ]
    mean_embed = (
        [round(float(x), 4) for x in np.mean(embeds, axis=0)] if embeds else None
    )

    energy = [
        r.analysis_json["energy_curve"]
        for r in ready
        if r.analysis_json and r.analysis_json.get("energy_curve")
    ]
    energy_profile = None
    if energy:
        m = min(len(e) for e in energy)
        energy_profile = [
            round(float(x), 4) for x in np.mean([e[:m] for e in energy], axis=0)
        ]

    section_counts = [
        r.structure_json["count"]
        for r in ready
        if r.structure_json and r.structure_json.get("count")
    ]

    return {
        "band_id": band.id,
        "references": {
            "total": len(refs),
            "analyzed": len(ready),
            "approved": sum(1 for r in refs if r.approved_for_training),
            "total_seconds": round(sum(r.duration or 0.0 for r in ready), 1),
        },
        "bpm": _stats(bpms),
        "key_distribution": dict(keys.most_common()),
        "tuning_distribution": dict(tunings.most_common()),
        "tag_cloud": dict(tags.most_common(30)),
        "mean_embedding": mean_embed,
        "energy_profile": energy_profile,
        "structure_style": {
            "avg_sections": round(statistics.fmean(section_counts), 1) if section_counts else None,
        },
    }
