"""Controlled vocabularies used across models and schemas.

Stored as plain strings in the DB (portable, easy to migrate) but validated
through these enums at the API boundary.
"""

from __future__ import annotations

from enum import StrEnum


class SongStatus(StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    GENERATING = "generating"
    READY = "ready"
    ARCHIVED = "archived"


class SectionType(StrEnum):
    INTRO = "intro"
    VERSE = "verse"
    PRE_CHORUS = "pre_chorus"
    CHORUS = "chorus"
    POST_CHORUS = "post_chorus"
    BRIDGE = "bridge"
    BREAKDOWN = "breakdown"
    SOLO = "solo"
    OUTRO = "outro"
    OTHER = "other"


class VocalRoleType(StrEnum):
    LEAD = "lead"
    DOUBLE = "double"
    HARMONY = "harmony"
    BACKGROUND = "background"
    GANG = "gang"
    SCREAM = "scream"


class TrainingStatus(StrEnum):
    NONE = "none"
    QUEUED = "queued"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"


class JobType(StrEnum):
    # Stage 0 exercises only MOCK_GENERATION; the rest are declared so the
    # job schema and worker routing are stable as later stages land.
    MOCK_GENERATION = "mock_generation"
    ANALYZE_REFERENCE = "analyze_reference"
    SEPARATE_STEMS = "separate_stems"
    RENDER_SECTION = "render_section"
    RENDER_VOICE = "render_voice"
    EXPAND_ENSEMBLE = "expand_ensemble"
    MIX = "mix"
    MASTER = "master"
    TRAIN_SINGER = "train_singer"
    TRAIN_BAND_ADAPTER = "train_band_adapter"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetType(StrEnum):
    UPLOAD = "upload"
    REFERENCE = "reference"
    GUIDE_VOCAL = "guide_vocal"
    SOURCE_TAKE = "source_take"  # a singer's recorded take of a section
    INSTRUMENTAL_BED = "instrumental_bed"  # section instrumental supplied for mixing
    TAKE_STEM = "take_stem"  # one rendered virtual performance
    ROLE_STEM = "role_stem"  # all takes of one vocal role, summed
    STEM_DRUMS = "stem_drums"
    STEM_BASS = "stem_bass"
    STEM_GUITARS = "stem_guitars"
    STEM_SYNTHS = "stem_synths"
    STEM_LEAD_VOCAL = "stem_lead_vocal"
    STEM_BACKGROUND_VOCAL = "stem_background_vocal"
    STEM_GANG_VOCAL = "stem_gang_vocal"
    STEM_INSTRUMENTAL = "stem_instrumental"
    VOCAL_BUS = "vocal_bus"  # every vocal role stem, summed
    SECTION_RENDER = "section_render"
    MIX = "mix"
    MASTER = "master"
    PROJECT_STATE = "project_state"
    OTHER = "other"


ROLE_STEM_TYPE = {
    "lead": AssetType.STEM_LEAD_VOCAL,
    "double": AssetType.STEM_LEAD_VOCAL,
    "scream": AssetType.STEM_LEAD_VOCAL,
    "harmony": AssetType.STEM_BACKGROUND_VOCAL,
    "background": AssetType.STEM_BACKGROUND_VOCAL,
    "gang": AssetType.STEM_GANG_VOCAL,
}
