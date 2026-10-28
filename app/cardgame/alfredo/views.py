"""Memory-only views handed to bot policies.

A policy must never see ``Slot.card``: bots act on what their seat *believes*,
which is what produces realistic wrong reactions and premature Alfredo calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Card, Suit


@dataclass(frozen=True)
class SlotView:
    """One face-down card as its owner perceives it."""

    slot_index: int
    known_rank: str | None
    known_suit: Suit | None

    @property
    def is_known(self) -> bool:
        """True when the owner has a usable belief about this slot."""
        return self.known_rank is not None


@dataclass(frozen=True)
class PlayerView:
    """One seat as seen through memory: card count is public, faces are not."""

    index: int
    name: str
    card_count: int
    slots: list[SlotView] = field(default_factory=list)

    def estimated_total(self, unknown_value: float) -> float:
        """Sum of known values, with ``unknown_value`` assumed for the rest."""
        total = 0.0
        for slot in self.slots:
            if slot.is_known:
                total += rank_value(slot.known_rank or "", slot.known_suit)
            else:
                total += unknown_value
        return total


def rank_value(rank: str, suit: Suit | None) -> int:
    """Value of a remembered rank; a red King is only known if the suit is."""
    if rank == "A":
        return 1
    if rank == "J":
        return 11
    if rank == "Q":
        return 12
    if rank == "K":
        if suit is None:
            return 6  # red or black King, 50/50
        return 0 if suit.is_red else 13
    return int(rank)


@dataclass(frozen=True)
class GameView:
    """Everything a bot is allowed to know at decision time."""

    current_index: int
    caller_index: int | None
    final_round: bool
    turn_number: int
    deck_size: int
    discard_picks: list[Card]
    players: list[PlayerView]

    def player(self, index: int) -> PlayerView:
        """The view of one seat."""
        return self.players[index]

    @property
    def num_players(self) -> int:
        """Seats at the table."""
        return len(self.players)
