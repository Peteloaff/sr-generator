"""Built-in signature style presets for instrument players.

A grid of style archetypes - acoustic through metal - for every instrument role
except vocals. These are *style characteristics*, not anyone's recordings: a
tuned :class:`~sr.common.playerstyle.StyleProfile` you can drop into a band with
one click and then adjust like a trained player.

id  = "<role>.<vibe>"   e.g. "lead_guitar.metal", "drums.doom"
"""

from __future__ import annotations

from sr.common.playerstyle import StyleProfile
from sr.models.player import PLAYER_ROLES

# ordered acoustic -> heavy
VIBES = (
    "acoustic", "clean", "blues", "indie", "classic_rock", "hard_rock",
    "metal", "modern_metal", "doom",
)

_VIBE_LABEL = {
    "acoustic": "Acoustic", "clean": "Clean", "blues": "Blues", "indie": "Indie",
    "classic_rock": "Classic Rock", "hard_rock": "Hard Rock", "metal": "Metal",
    "modern_metal": "Modern Metal", "doom": "Doom",
}
_ROLE_SHORT = {
    "lead_guitar": "Lead", "rhythm_guitar": "Rhythm", "bass": "Bass",
    "drums": "Drums", "keys": "Keys",
}

# column order for the rows in _GRID
_F = (
    "drive", "brightness", "attack", "sustain", "busyness",
    "dynamics", "swing", "low_end", "register_hz",
)

_GRID: dict[str, dict[str, tuple]] = {
    "lead_guitar": {
        "acoustic":     (0.00,  0.35, 0.55, 0.70, 0.40, 0.85, 0.12, 0.10, 1600),
        "clean":        (0.12,  0.40, 0.60, 0.60, 0.50, 0.65, 0.05, 0.10, 1500),
        "blues":        (0.40,  0.10, 0.45, 0.65, 0.45, 0.80, 0.35, 0.12, 1200),
        "indie":        (0.35,  0.30, 0.50, 0.55, 0.45, 0.60, 0.05, 0.12, 1400),
        "classic_rock": (0.55,  0.20, 0.60, 0.55, 0.55, 0.60, 0.10, 0.14, 1300),
        "hard_rock":    (0.75,  0.25, 0.70, 0.45, 0.65, 0.50, 0.00, 0.16, 1400),
        "metal":        (0.95,  0.35, 0.85, 0.30, 0.85, 0.40, 0.00, 0.15, 1600),
        "modern_metal": (1.00,  0.20, 0.95, 0.22, 0.90, 0.35, 0.00, 0.22, 1500),
        "doom":         (0.90, -0.45, 0.45, 0.90, 0.30, 0.55, 0.00, 0.35,  700),
    },
    "rhythm_guitar": {
        "acoustic":     (0.00,  0.25, 0.50, 0.55, 0.55, 0.75, 0.14, 0.15, 1100),
        "clean":        (0.10,  0.30, 0.45, 0.60, 0.50, 0.55, 0.06, 0.16, 1000),
        "blues":        (0.35,  0.00, 0.45, 0.55, 0.45, 0.70, 0.35, 0.20,  850),
        "indie":        (0.35,  0.25, 0.45, 0.55, 0.55, 0.55, 0.05, 0.18,  950),
        "classic_rock": (0.55,  0.10, 0.55, 0.50, 0.55, 0.55, 0.10, 0.22,  900),
        "hard_rock":    (0.72,  0.10, 0.65, 0.40, 0.65, 0.45, 0.00, 0.28,  850),
        "metal":        (0.96,  0.15, 0.85, 0.22, 0.80, 0.40, 0.00, 0.30,  800),
        "modern_metal": (1.00,  0.05, 0.98, 0.14, 0.88, 0.32, 0.00, 0.42,  720),
        "doom":         (0.95, -0.55, 0.40, 0.85, 0.25, 0.50, 0.00, 0.60,  500),
    },
    "bass": {
        "acoustic":     (0.00, -0.25, 0.40, 0.75, 0.45, 0.75, 0.20, 0.60,  110),
        "clean":        (0.12, -0.10, 0.50, 0.60, 0.45, 0.55, 0.05, 0.65,  140),
        "blues":        (0.28, -0.05, 0.45, 0.60, 0.50, 0.70, 0.35, 0.60,  130),
        "indie":        (0.25,  0.05, 0.55, 0.55, 0.55, 0.55, 0.05, 0.60,  150),
        "classic_rock": (0.35,  0.05, 0.60, 0.55, 0.50, 0.55, 0.10, 0.65,  140),
        "hard_rock":    (0.55,  0.15, 0.70, 0.45, 0.55, 0.50, 0.00, 0.70,  150),
        "metal":        (0.80,  0.25, 0.85, 0.30, 0.75, 0.40, 0.00, 0.72,  150),
        "modern_metal": (0.90,  0.30, 0.95, 0.20, 0.88, 0.35, 0.00, 0.80,  145),
        "doom":         (0.85, -0.30, 0.45, 0.90, 0.25, 0.55, 0.00, 1.00,   70),
    },
    "drums": {
        "acoustic":     (0.00,  0.10, 0.55, 0.35, 0.28, 0.90, 0.15, 0.35, 2400),
        "clean":        (0.05,  0.10, 0.65, 0.30, 0.42, 0.65, 0.06, 0.38, 2500),
        "blues":        (0.08,  0.05, 0.60, 0.32, 0.45, 0.78, 0.38, 0.40, 2300),
        "indie":        (0.10,  0.15, 0.65, 0.30, 0.48, 0.62, 0.05, 0.38, 2500),
        "classic_rock": (0.12,  0.05, 0.70, 0.28, 0.52, 0.62, 0.10, 0.45, 2200),
        "hard_rock":    (0.18,  0.10, 0.78, 0.25, 0.62, 0.52, 0.00, 0.48, 2300),
        "metal":        (0.28,  0.20, 0.90, 0.20, 0.85, 0.42, 0.00, 0.55, 2600),
        "modern_metal": (0.30,  0.25, 0.98, 0.16, 0.95, 0.30, 0.00, 0.62, 2800),
        "doom":         (0.20, -0.10, 0.80, 0.30, 0.20, 0.70, 0.00, 0.70, 1800),
    },
    "keys": {
        "acoustic":     (0.00,  0.25, 0.55, 0.55, 0.50, 0.85, 0.12, 0.28, 1200),
        "clean":        (0.03,  0.15, 0.45, 0.70, 0.35, 0.55, 0.05, 0.30, 1000),
        "blues":        (0.10,  0.00, 0.50, 0.55, 0.45, 0.75, 0.35, 0.30,  900),
        "indie":        (0.08,  0.25, 0.45, 0.65, 0.40, 0.55, 0.05, 0.28, 1100),
        "classic_rock": (0.15,  0.10, 0.50, 0.55, 0.45, 0.55, 0.10, 0.35,  950),
        "hard_rock":    (0.25,  0.15, 0.55, 0.50, 0.50, 0.48, 0.00, 0.40, 1000),
        "metal":        (0.35, -0.10, 0.70, 0.35, 0.55, 0.45, 0.00, 0.45,  800),
        "modern_metal": (0.30, -0.30, 0.55, 0.75, 0.30, 0.45, 0.00, 0.55,  650),
        "doom":         (0.10, -0.50, 0.40, 1.00, 0.15, 0.55, 0.00, 0.55,  600),
    },
}


def _profile(role: str, vibe: str) -> dict:
    vals = dict(zip(_F, _GRID[role][vibe], strict=True))
    return StyleProfile.from_dict({"role": role, **vals}).to_dict()


def preset_label(role: str, vibe: str) -> str:
    return f"{_VIBE_LABEL[vibe]} {_ROLE_SHORT[role]}"


def get_preset(preset_id: str) -> dict | None:
    try:
        role, vibe = preset_id.split(".", 1)
    except ValueError:
        return None
    if role not in _GRID or vibe not in _GRID[role]:
        return None
    return {
        "id": preset_id, "role": role, "vibe": vibe,
        "label": preset_label(role, vibe), "profile": _profile(role, vibe),
    }


def list_presets(role: str | None = None) -> list[dict]:
    roles = [role] if role else [r for r in PLAYER_ROLES if r in _GRID]
    out: list[dict] = []
    for r in roles:
        for v in VIBES:
            if v in _GRID.get(r, {}):
                out.append(get_preset(f"{r}.{v}"))
    return out
