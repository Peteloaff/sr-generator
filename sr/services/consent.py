"""Voice consent gate.

Blueprint rule: never train or render a singer's voice without the required
authorization flag. These checks are the single choke point - the API calls them
before queuing work, and the job handlers call them again (defence in depth).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from sr.models.singer import Singer

if TYPE_CHECKING:
    from sr.models.player import Player


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


def require_player_training(player: Player) -> None:
    if not player.consent_training:
        raise ConsentError(
            f"player {player.name!r} has not authorized style-model training"
        )


def require_player_generation(player: Player) -> None:
    if player.consent_generation:
        return
    raise ConsentError(f"player {player.name!r} has not authorized style generation")


def players_blocked_for_generation(players: Iterable[Player]) -> list[str]:
    return sorted(p.name for p in players if not p.consent_generation)
