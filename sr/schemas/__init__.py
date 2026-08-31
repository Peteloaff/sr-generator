"""Pydantic request/response models for the API boundary."""

from sr.schemas.job import JobCreate, JobRead
from sr.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from sr.schemas.singer import SingerCreate, SingerRead, SingerUpdate
from sr.schemas.song import (
    LyricLineCreate,
    LyricLineRead,
    SectionCreate,
    SectionRead,
    SongCreate,
    SongRead,
    SongUpdate,
)

__all__ = [
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
    "SectionRead",
    "LyricLineCreate",
    "LyricLineRead",
    "JobCreate",
    "JobRead",
]
