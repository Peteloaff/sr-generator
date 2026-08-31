"""CenterSplitStemProvider - real, dependency-free center-channel separation.

Lifts a usable lead vocal + instrumental out of a stereo mix so a cover's vocal
can be replaced while the melody (carried by the extracted vocal, used as a
guide) and the instrumental are preserved. A Demucs-class model implements the
same ``separate`` contract - locally or via ``SR_STEM_PROVIDER=http``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sr.common.dsp import SR, load_stereo
from sr.common.separation import separate_center
from sr.providers.base import StemSeparation, StemSeparationProvider


class CenterSplitStemProvider(StemSeparationProvider):
    name = "center_split"
    version = "center-split-0.5.0"
    produces = ("stem_lead_vocal", "stem_instrumental")

    def separate(self, *, source_path: Path, params: dict[str, Any]) -> StemSeparation:
        stereo = load_stereo(Path(source_path))
        strength = float(params.get("strength", 1.4))
        parts = separate_center(stereo, sr=SR, strength=strength)
        return StemSeparation(
            stems={
                "stem_lead_vocal": parts["vocal"],
                "stem_instrumental": parts["instrumental"],
            },
            sample_rate=SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"strength": strength, "frames": int(stereo.shape[0])},
        )
