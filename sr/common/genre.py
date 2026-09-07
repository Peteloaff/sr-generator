"""Genre / song-feel presets.

A preset is a named bundle of generation parameters that shapes a whole song:
tempo range, mode, string tuning, how long sections run, structure bias, energy
range, swing, and an instrumental *character* (drive / distortion, brightness,
drum busyness, note sustain, sub weight, chord progressions).

It sits at the bottom of the stack: genre -> band adapter -> per-section params
-> per-instrument player styles. Each layer modulates the one below, so a preset
is a starting point, never a cage.
"""

from __future__ import annotations

from typing import Any

from sr.common.seeds import derive_seed

# progression names must exist in sr/common/musicgen.py (_MAJOR_PROG / _MINOR_PROG)
_DARK_MINOR = ["i-VI-III-VII", "i-VII-VI-VII"]
_BRIGHT_MAJOR = ["I-V-vi-IV", "vi-IV-I-V"]

_NEUTRAL: dict[str, Any] = {
    "label": "Default",
    "bpm": (96, 132),
    "mode": "any",
    "tuning": 0,
    "section_scale": 1.0,
    "energy": (0.25, 0.95),
    "swing": 0.0,
    "character": {
        "brightness": 0.0, "drive": 0.2, "distortion": 0.1,
        "drum_busy": 0.5, "sustain": 0.5, "sub_weight": 0.35,
    },
}


def _p(**kw: Any) -> dict[str, Any]:
    """A preset that inherits every unset field (incl. nested character) from neutral."""
    out = {**_NEUTRAL, **kw}
    out["character"] = {**_NEUTRAL["character"], **kw.get("character", {})}
    return out


GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "metal": _p(
        label="Metal", bpm=(140, 190), mode="minor", tuning=-2, section_scale=1.0,
        energy=(0.6, 1.0), progressions=_DARK_MINOR,
        character={"brightness": 0.2, "drive": 0.85, "distortion": 0.9,
                   "drum_busy": 0.8, "sustain": 0.35, "sub_weight": 0.55},
    ),
    "thrash_metal": _p(
        label="Thrash Metal", bpm=(170, 220), mode="minor", tuning=-1, section_scale=0.85,
        energy=(0.7, 1.0), progressions=_DARK_MINOR,
        character={"brightness": 0.35, "drive": 0.9, "distortion": 0.95,
                   "drum_busy": 0.95, "sustain": 0.25, "sub_weight": 0.5},
    ),
    "sludge_metal": _p(
        label="Sludge Metal", bpm=(58, 84), mode="minor", tuning=-3, section_scale=1.7,
        energy=(0.5, 1.0), progressions=_DARK_MINOR,
        character={"brightness": -0.55, "drive": 0.95, "distortion": 1.0,
                   "drum_busy": 0.3, "sustain": 0.85, "sub_weight": 0.9},
    ),
    "doom_metal": _p(
        label="Doom Metal", bpm=(50, 75), mode="minor", tuning=-4, section_scale=1.9,
        energy=(0.4, 0.95), progressions=_DARK_MINOR,
        character={"brightness": -0.6, "drive": 0.8, "distortion": 0.85,
                   "drum_busy": 0.22, "sustain": 0.95, "sub_weight": 1.0},
    ),
    "metalcore": _p(
        label="Metalcore", bpm=(150, 200), mode="minor", tuning=-4, section_scale=1.0,
        energy=(0.65, 1.0), progressions=_DARK_MINOR,
        character={"brightness": 0.1, "drive": 0.9, "distortion": 0.95,
                   "drum_busy": 0.85, "sustain": 0.3, "sub_weight": 0.7},
    ),
    "black_metal": _p(
        label="Black Metal", bpm=(160, 230), mode="minor", tuning=-1, section_scale=1.3,
        energy=(0.6, 1.0), progressions=_DARK_MINOR,
        character={"brightness": 0.45, "drive": 0.8, "distortion": 0.85,
                   "drum_busy": 1.0, "sustain": 0.6, "sub_weight": 0.3},
    ),
    "hard_rock": _p(
        label="Hard Rock", bpm=(112, 150), mode="any", tuning=0, section_scale=1.0,
        energy=(0.5, 0.95),
        character={"brightness": 0.15, "drive": 0.6, "distortion": 0.55,
                   "drum_busy": 0.6, "sustain": 0.5, "sub_weight": 0.45},
    ),
    "classic_rock": _p(
        label="Classic Rock", bpm=(104, 138), mode="any", tuning=0, section_scale=1.0,
        energy=(0.4, 0.9), swing=0.12,
        character={"brightness": 0.05, "drive": 0.45, "distortion": 0.35,
                   "drum_busy": 0.5, "sustain": 0.55, "sub_weight": 0.4},
    ),
    "punk": _p(
        label="Punk", bpm=(165, 210), mode="major", tuning=0, section_scale=0.7,
        energy=(0.7, 1.0), progressions=_BRIGHT_MAJOR,
        character={"brightness": 0.3, "drive": 0.7, "distortion": 0.6,
                   "drum_busy": 0.7, "sustain": 0.3, "sub_weight": 0.35},
    ),
    "grunge": _p(
        label="Grunge", bpm=(90, 130), mode="minor", tuning=-1, section_scale=1.1,
        energy=(0.35, 1.0),
        character={"brightness": -0.15, "drive": 0.65, "distortion": 0.7,
                   "drum_busy": 0.5, "sustain": 0.5, "sub_weight": 0.5},
    ),
    "prog_rock": _p(
        label="Prog Rock", bpm=(100, 160), mode="any", tuning=0, section_scale=1.4,
        energy=(0.3, 0.95), swing=0.1,
        character={"brightness": 0.2, "drive": 0.4, "distortion": 0.3,
                   "drum_busy": 0.7, "sustain": 0.6, "sub_weight": 0.4},
    ),
    "indie_rock": _p(
        label="Indie Rock", bpm=(112, 152), mode="major", tuning=0, section_scale=1.0,
        energy=(0.35, 0.85), progressions=_BRIGHT_MAJOR,
        character={"brightness": 0.25, "drive": 0.35, "distortion": 0.25,
                   "drum_busy": 0.5, "sustain": 0.5, "sub_weight": 0.35},
    ),
    "pop": _p(
        label="Pop", bpm=(100, 128), mode="major", tuning=0, section_scale=0.95,
        energy=(0.35, 0.9), progressions=_BRIGHT_MAJOR,
        character={"brightness": 0.35, "drive": 0.15, "distortion": 0.05,
                   "drum_busy": 0.55, "sustain": 0.45, "sub_weight": 0.4},
    ),
    "synthwave": _p(
        label="Synthwave", bpm=(96, 118), mode="minor", tuning=0, section_scale=1.2,
        energy=(0.3, 0.85),
        character={"brightness": 0.3, "drive": 0.2, "distortion": 0.1,
                   "drum_busy": 0.45, "sustain": 0.8, "sub_weight": 0.55},
    ),
    "electronic": _p(
        label="Electronic", bpm=(120, 132), mode="minor", tuning=0, section_scale=1.1,
        energy=(0.35, 1.0),
        character={"brightness": 0.3, "drive": 0.25, "distortion": 0.15,
                   "drum_busy": 0.7, "sustain": 0.7, "sub_weight": 0.65},
    ),
    "ambient": _p(
        label="Ambient", bpm=(60, 90), mode="any", tuning=0, section_scale=2.0,
        energy=(0.1, 0.5),
        character={"brightness": 0.1, "drive": 0.05, "distortion": 0.0,
                   "drum_busy": 0.05, "sustain": 1.0, "sub_weight": 0.5},
    ),
    "acoustic": _p(
        label="Acoustic", bpm=(84, 124), mode="any", tuning=0, section_scale=1.0,
        energy=(0.2, 0.7), swing=0.08,
        character={"brightness": 0.2, "drive": 0.0, "distortion": 0.0,
                   "drum_busy": 0.25, "sustain": 0.4, "sub_weight": 0.25},
    ),
    "folk": _p(
        label="Folk", bpm=(92, 132), mode="major", tuning=0, section_scale=1.0,
        energy=(0.2, 0.7), swing=0.15, progressions=_BRIGHT_MAJOR,
        character={"brightness": 0.25, "drive": 0.0, "distortion": 0.0,
                   "drum_busy": 0.3, "sustain": 0.35, "sub_weight": 0.3},
    ),
    "blues": _p(
        label="Blues", bpm=(72, 116), mode="any", tuning=0, section_scale=1.1,
        energy=(0.3, 0.8), swing=0.4,
        character={"brightness": 0.0, "drive": 0.35, "distortion": 0.2,
                   "drum_busy": 0.4, "sustain": 0.5, "sub_weight": 0.4},
    ),
    "funk": _p(
        label="Funk", bpm=(96, 118), mode="minor", tuning=0, section_scale=1.0,
        energy=(0.4, 0.9), swing=0.2,
        character={"brightness": 0.25, "drive": 0.2, "distortion": 0.1,
                   "drum_busy": 0.8, "sustain": 0.25, "sub_weight": 0.55},
    ),
    "country": _p(
        label="Country", bpm=(96, 136), mode="major", tuning=0, section_scale=1.0,
        energy=(0.3, 0.8), swing=0.18, progressions=_BRIGHT_MAJOR,
        character={"brightness": 0.3, "drive": 0.15, "distortion": 0.05,
                   "drum_busy": 0.45, "sustain": 0.4, "sub_weight": 0.35},
    ),
    "ballad": _p(
        label="Ballad", bpm=(64, 92), mode="any", tuning=0, section_scale=1.3,
        energy=(0.15, 0.7),
        character={"brightness": 0.1, "drive": 0.1, "distortion": 0.0,
                   "drum_busy": 0.3, "sustain": 0.8, "sub_weight": 0.4},
    ),
}


def list_genres() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in GENRE_PRESETS.items()]


def resolve(name: str | None) -> dict[str, Any]:
    if not name:
        return dict(_NEUTRAL)
    return GENRE_PRESETS.get(name.strip().lower().replace(" ", "_"), dict(_NEUTRAL))


def plan_bias(name: str | None, *, seed: int, bpm: float | None) -> dict[str, Any]:
    """Concrete numbers the song planner applies for this genre."""
    g = resolve(name)
    lo, hi = g["bpm"]
    if bpm:
        chosen_bpm = float(bpm)
    else:
        frac = (derive_seed(seed, "genre_bpm") % 1000) / 1000.0
        chosen_bpm = lo + (hi - lo) * frac
    ef, ec = g["energy"]
    return {
        "bpm": round(chosen_bpm, 1),
        "mode": g["mode"],
        "tuning_semitones": int(g["tuning"]),
        "section_scale": float(g["section_scale"]),
        "energy_floor": float(ef),
        "energy_ceiling": float(ec),
        "swing": float(g.get("swing", 0.0)),
        "structure": g.get("structure"),
        "progressions": g.get("progressions"),
    }


def character(name: str | None) -> dict[str, Any]:
    """Instrumental character knobs for this genre (fed to the music provider)."""
    g = resolve(name)
    out = dict(g["character"])
    out["tuning_semitones"] = int(g["tuning"])
    out["swing"] = float(g.get("swing", 0.0))
    if g.get("progressions"):
        out["progressions"] = list(g["progressions"])
    return out
