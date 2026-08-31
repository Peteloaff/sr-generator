"""Resolve the effective vocal roles for a lyric line.

Rule: if a line has its own vocal roles, they fully override the section's. If it
has none, it inherits the section's roles. This keeps "set the whole chorus in
one action" working while still allowing per-line control.
"""

from __future__ import annotations

from dataclasses import dataclass

from sr.models.song import LyricLine
from sr.models.vocal import VocalRole


@dataclass(frozen=True)
class ResolvedRoles:
    line_id: str
    source: str  # "line" | "section" | "none"
    roles: list[VocalRole]


def resolve_line_roles(line: LyricLine) -> ResolvedRoles:
    if line.vocal_roles:
        return ResolvedRoles(line.id, "line", list(line.vocal_roles))
    if line.section is not None and line.section.vocal_roles:
        return ResolvedRoles(line.id, "section", list(line.section.vocal_roles))
    return ResolvedRoles(line.id, "none", [])
