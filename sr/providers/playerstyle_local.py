"""LocalDspPlayerStyleProvider - deterministic instrument-style analysis.

Runs :mod:`sr.common.playerstyle` over the separated instrument stems and blends
the per-sample profiles into one. Not a model - it measures tendencies (drive,
tone, attack, density, dynamics, swing) that Stage 14 applies to brand-new parts.
A neural provider implements the same ``analyze`` contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sr.common import playerstyle
from sr.common.dsp import SR, load_stereo
from sr.providers.base import PlayerStyleProvider

_MAX_SECONDS = 45


class LocalDspPlayerStyleProvider(PlayerStyleProvider):
    name = "local_dsp"
    version = "local-playerstyle-0.13.0"
    trains = True

    def analyze(
        self, stem_paths: list[Path], *, role: str, bpm: float = 0.0
    ) -> dict[str, Any]:
        profiles = []
        for p in stem_paths:
            stereo = load_stereo(Path(p))[: SR * _MAX_SECONDS]
            profiles.append(playerstyle.analyze(stereo, role, sr=SR, bpm=bpm))
        if not profiles:
            return playerstyle.StyleProfile(role=role).to_dict()
        return playerstyle.blend(profiles).to_dict()
