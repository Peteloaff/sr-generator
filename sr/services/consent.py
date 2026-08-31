"""Voice consent gate.

Blueprint rule: never train or render a singer's voice without the required
authorization flag. These checks are the single choke point - the API calls them
before queuing work, and the job handlers call them again (defence in depth).
"""

from __future__ import annotations

from collections.abc import Iterable

from sr.models.singer import Singer


class ConsentError(PermissionError):
    """Raised when a required consent flag is missing. Maps to HTTP 403."""


def require_training(singer: Singer) -> None:
    if not singer.consent_training:
        raise ConsentError(f"singer {singer.name!r} has not authorized voice-model training")


def require_generation(singer: Singer) -> None:
    if singer.consent_generation:
        return
    raise ConsentError(f"singer {singer.name!r} has not authorized voice generation")


def blocked_for_generation(singers: Iterable[Singer]) -> list[str]:
    return sorted(s.name for s in singers if not s.consent_generation)
