"""DemucsStemProvider - real per-instrument separation (htdemucs_6s).

Splits a mix into drums / bass / guitar / keys / other / vocal. Requires the
``separation`` extra (``pip install "sr-generator[separation]"``); the model
weights download once on first use into the torch/HF cache.

Selected by ``SR_MULTISTEM_PROVIDER=demucs`` (the default). Falls back to a clear
error if the package is missing, so the rest of the app still imports.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np

from sr.providers.base import StemSeparation, StemSeparationProvider

# htdemucs_6s source name -> our asset_type
_MAP = {
    "drums": "stem_drums",
    "bass": "stem_bass",
    "guitar": "stem_guitar",
    "piano": "stem_keys",
    "vocals": "stem_vocal",
    "other": "stem_other",
}

_LOCK = threading.Lock()
_SEPARATOR: Any = None


def _get_separator(model: str):
    global _SEPARATOR
    with _LOCK:
        if _SEPARATOR is None or getattr(_SEPARATOR, "_sr_model", None) != model:
            from sr.common.deps import ensure_separation

            ensure_separation()  # import Demucs, or install it on first use
            from demucs.api import Separator

            # shifts=0: no random shift augmentation, so separation is
            # reproducible run-to-run (required for deterministic style learning).
            sep = Separator(model=model, progress=False, shifts=0)
            sep._sr_model = model  # noqa: SLF001
            _SEPARATOR = sep
    return _SEPARATOR


class DemucsStemProvider(StemSeparationProvider):
    name = "demucs"
    version = "demucs-4-htdemucs_6s"
    produces = ("stem_drums", "stem_bass", "stem_guitar", "stem_keys", "stem_other", "stem_vocal")
    default_model = "htdemucs_6s"

    def separate(self, *, source_path: Path, params: dict[str, Any]) -> StemSeparation:
        model = str(params.get("model") or self.default_model)
        sep = _get_separator(model)
        _, sources = sep.separate_audio_file(Path(source_path))

        stems: dict[str, np.ndarray] = {}
        for src_name, tensor in sources.items():
            arr = tensor.detach().cpu().numpy().astype(np.float32)  # (channels, samples)
            if arr.ndim == 1:
                arr = np.stack([arr, arr], axis=0)
            stereo = arr.T  # (samples, channels)
            if stereo.shape[1] == 1:
                stereo = np.repeat(stereo, 2, axis=1)
            stems[_MAP.get(src_name, f"stem_{src_name}")] = np.ascontiguousarray(stereo)

        return StemSeparation(
            stems=stems,
            sample_rate=int(sep.samplerate),
            provider=self.name,
            provider_version=f"{self.version}:{model}",
            metadata={"model": model, "sources": list(sources)},
        )
