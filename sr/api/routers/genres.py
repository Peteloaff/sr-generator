"""Genre / song-feel presets."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sr.common import genre as genre_mod

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("")
def list_genres() -> list[dict]:
    return genre_mod.list_genres()


@router.get("/{genre_id}")
def get_genre(genre_id: str) -> dict:
    key = genre_id.strip().lower().replace(" ", "_")
    if key not in genre_mod.GENRE_PRESETS:
        raise HTTPException(404, f"unknown genre {genre_id!r}")
    preset = genre_mod.GENRE_PRESETS[key]
    return {
        "id": key,
        "label": preset["label"],
        "bpm": list(preset["bpm"]),
        "mode": preset["mode"],
        "tuning_semitones": preset["tuning"],
        "character": preset["character"],
    }
