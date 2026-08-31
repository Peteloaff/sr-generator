"""Pydantic request/response models for the API boundary."""

from sr.schemas.audio import AudioAssetRead, WaveformRead
from sr.schemas.band import BandCreate, BandRead, BandUpdate
from sr.schemas.job import JobCreate, JobRead
from sr.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from sr.schemas.render import RenderRequest, RenderTakeRead
from sr.schemas.singer import SingerCreate, SingerRead, SingerUpdate
from sr.schemas.song import (
    LyricLineCreate,
    LyricLineRead,
    LyricLineUpdate,
    LyricsReplace,
    SectionCreate,
    SectionRead,
    SectionUpdate,
    SongCreate,
    SongRead,
    SongUpdate,
)
from sr.schemas.vocal import (
    NormalizedShare,
    VocalAssignmentCreate,
    VocalAssignmentRead,
    VocalAssignmentUpdate,
    VocalRoleCreate,
    VocalRoleRead,
    VocalRoleUpdate,
)

__all__ = [
    "AudioAssetRead",
    "WaveformRead",
    "BandCreate",
    "BandUpdate",
    "BandRead",
    "SingerCreate",
    "SingerUpdate",
    "SingerRead",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectRead",
    "SongCreate",
    "SongUpdate",
    "SongRead",
    "SectionCreate",
    "SectionUpdate",
    "SectionRead",
    "LyricLineCreate",
    "LyricLineUpdate",
    "LyricLineRead",
    "LyricsReplace",
    "JobCreate",
    "JobRead",
    "RenderRequest",
    "RenderTakeRead",
    "NormalizedShare",
    "VocalRoleCreate",
    "VocalRoleUpdate",
    "VocalRoleRead",
    "VocalAssignmentCreate",
    "VocalAssignmentUpdate",
    "VocalAssignmentRead",
]
