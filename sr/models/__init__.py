"""All ORM models. Import from here so Alembic autogenerate sees every table."""

from sr.models.audio_asset import AudioAsset
from sr.models.band import Band
from sr.models.band_reference import BandReference
from sr.models.base import Base
from sr.models.generation_job import GenerationJob
from sr.models.project import Project
from sr.models.render_cache import RenderCache
from sr.models.render_take import RenderTake
from sr.models.singer import Singer
from sr.models.song import LyricLine, Song, SongSection
from sr.models.vocal import VocalAssignment, VocalRole

__all__ = [
    "Base",
    "Band",
    "Project",
    "Singer",
    "Song",
    "SongSection",
    "LyricLine",
    "VocalRole",
    "VocalAssignment",
    "BandReference",
    "GenerationJob",
    "AudioAsset",
    "RenderTake",
    "RenderCache",
]
