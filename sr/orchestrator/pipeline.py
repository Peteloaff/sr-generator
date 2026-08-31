"""Generation pipeline definition (blueprint section 10).

Stage 0 only declares the stage graph and a dry-run planner so the shape is
fixed. Real stage execution lands incrementally from Stage 2 onward - each stage
becomes one or more queued GenerationJobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PipelineStage(StrEnum):
    PLAN = "plan"
    MUSIC = "music"
    GUIDE_MELODY = "guide_melody"
    VOCAL_DIRECT = "vocal_direct"
    VOICE_RENDER = "voice_render"
    ENSEMBLE_EXPAND = "ensemble_expand"
    ALIGN = "align"
    VOCAL_PROCESS = "vocal_process"
    STEM_MIX = "stem_mix"
    MASTER = "master"
    EXPORT = "export"


PIPELINE_ORDER: list[PipelineStage] = list(PipelineStage)


@dataclass(frozen=True)
class PlannedStep:
    stage: PipelineStage
    job_type: str | None
    note: str


def plan_dry_run(song_id: str) -> list[PlannedStep]:
    """Return the ordered steps that a full song generation *would* run."""
    mapping = {
        PipelineStage.PLAN: (None, "structure + section planning (in-process)"),
        PipelineStage.MUSIC: ("mock_generation", "instrumental/section music"),
        PipelineStage.GUIDE_MELODY: (None, "guide melody/vocal extraction"),
        PipelineStage.VOCAL_DIRECT: (None, "resolve section/line vocal roles"),
        PipelineStage.VOICE_RENDER: ("render_voice", "per-singer rendering"),
        PipelineStage.ENSEMBLE_EXPAND: ("expand_ensemble", "harmony/double/gang takes"),
        PipelineStage.ALIGN: (None, "timing + pitch alignment"),
        PipelineStage.VOCAL_PROCESS: (None, "de-ess/EQ/compression hooks"),
        PipelineStage.STEM_MIX: ("mix", "stem-level mix"),
        PipelineStage.MASTER: ("master", "optional mastering (stems preserved)"),
        PipelineStage.EXPORT: (None, "WAV + stems + project state"),
    }
    return [PlannedStep(st, mapping[st][0], mapping[st][1]) for st in PIPELINE_ORDER]
