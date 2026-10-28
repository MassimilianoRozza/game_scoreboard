"""Mutable game state: slots, players, memory and the event log.

The critical modelling decision is that **memory belongs to the slot, not to
the card**. A player who peeked at slot 3 and later has that card swapped away
by a Jack keeps no knowledge of the new card in slot 3, and the player who
received the swapped card knows nothing about it either (ruleset §5, Jack:
"Neither selected card may be looked at during the swap").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .cards import Card, Suit

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps the package UI-free
    from .bots import BotPolicy


@dataclass
class Slot:
    """A face-down card in front of a player, plus that player's memory of it.

    ``memory_rank``/``memory_suit`` are what the owner *believes* is in this
    slot. ``memory_valid`` is False when the belief is known to be stale (for
    instance after a Jack swap moved the card away).
    """

    card: Card
    memory_rank: str | None = None
    memory_suit: Suit | None = None
    memory_valid: bool = False

    def remember(self, rank: str, suit: Suit) -> None:
        """Record that the owner legitimately looked at this slot."""
        self.memory_rank = rank
        self.memory_suit = suit
        self.memory_valid = True

    def invalidate_memory(self) -> None:
        """Mark the owner's belief about this slot as no longer trustworthy."""
        self.memory_valid = False

    @property
    def known_rank(self) -> str | None:
        """The rank the owner believes is here, or None when unknown."""
        return self.memory_rank if self.memory_valid else None


@dataclass
class Player:
    """A seat at the table: name, hand, policy and running scores."""

    name: str
    is_bot: bool
    hand: list[Slot] = field(default_factory=list)
    policy: "BotPolicy | None" = None
    cumulative_score: int = 0
    round_score: int | None = None
    card_total: int | None = None

    @property
    def card_count(self) -> int:
        """How many face-down cards this player currently holds."""
        return len(self.hand)

    def true_total(self) -> int:
        """Exact card total, used only for scoring (ruleset §8)."""
        return sum(slot.card.value for slot in self.hand)


@dataclass
class LogEntry:
    """One line of the match narrative, kept for the simulation report."""

    round_number: int
    turn: int
    actor: str | None
    kind: str
    message: str


class GameLog:
    """Append-only event log with a small typed vocabulary."""

    def __init__(self) -> None:
        self.entries: list[LogEntry] = []
        self.round_number: int = 0
        self.turn: int = 0

    def add(self, actor: str | None, kind: str, message: str) -> None:
        """Append one entry stamped with the current round and turn."""
        self.entries.append(
            LogEntry(
                round_number=self.round_number,
                turn=self.turn,
                actor=actor,
                kind=kind,
                message=message,
            )
        )
