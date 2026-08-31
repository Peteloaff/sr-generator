"""Dataset quality checks for reference songs.

A reference can only be approved for training when it analysed cleanly. These
checks flag the obvious problems - clipped, silent, too short, near-mono, very
quiet - so a poor dataset is refused rather than silently trained on.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sr.common.dsp import SR, load_stereo

MIN_SECONDS = 20.0


def check_file(path: Path) -> dict:
    stereo = load_stereo(Path(path))
    n = stereo.shape[0]
    seconds = n / SR
    mono = stereo.mean(axis=1)

    flags: list[str] = []
    clip_frac = float(np.mean(np.abs(stereo) >= 0.999))
    rms = float(np.sqrt(np.mean(mono**2)))
    loud_db = 20.0 * np.log10(max(rms, 1e-9))
    silent_frac = float(np.mean(np.abs(mono) < 1e-4))
    side = float(np.sqrt(np.mean(((stereo[:, 0] - stereo[:, 1]) * 0.5) ** 2)))
    mid = float(np.sqrt(np.mean(((stereo[:, 0] + stereo[:, 1]) * 0.5) ** 2))) + 1e-9

    if seconds < MIN_SECONDS:
        flags.append(f"too short ({seconds:.0f}s < {MIN_SECONDS:.0f}s)")
    if clip_frac > 0.005:
        flags.append(f"clipped ({clip_frac * 100:.1f}% of samples at full scale)")
    if loud_db < -35.0:
        flags.append(f"very quiet ({loud_db:.0f} dBFS)")
    if silent_frac > 0.4:
        flags.append(f"mostly silent ({silent_frac * 100:.0f}%)")
    if side / mid < 0.02:
        flags.append("effectively mono")

    penalty = min(1.0, 0.35 * len(flags) + 4.0 * clip_frac)
    score = round(max(0.0, 1.0 - penalty), 3)
    hard_fail = seconds < MIN_SECONDS or silent_frac > 0.6 or clip_frac > 0.05
    return {
        "score": score,
        "passed": not hard_fail,
        "flags": flags,
        "metrics": {
            "seconds": round(seconds, 2),
            "loudness_dbfs": round(loud_db, 2),
            "clip_fraction": round(clip_frac, 5),
            "silent_fraction": round(silent_frac, 3),
            "stereo_width": round(side / mid, 4),
        },
    }
