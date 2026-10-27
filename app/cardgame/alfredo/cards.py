"""Cards, point values and deck construction for Alfredo.

Every rule referenced here comes from ``alfredoRuleSet.md`` section 2
("Players and Equipment").
"""

from __future__ import annotations

import enum
import math
import random
from dataclasses import dataclass
from typing import Final

#: Ranks present in a standard poker deck, jokers removed (ruleset §2).
RANKS: Final[tuple[str, ...]] = (
    "A",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
)

#: Ranks whose special ability fires when they are discarded from a player's
#: face-down cards (ruleset §5).
ABILITY_RANKS: Final[frozenset[str]] = frozenset({"A", "J", "Q"})


class Suit(enum.Enum):
    """The four poker suits, carrying their printed symbol."""

    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"

    @property
    def is_red(self) -> bool:
        """True for ♥ and ♦, the suits whose King is worth 0 (ruleset §2)."""
        return self in (Suit.HEARTS, Suit.DIAMONDS)

    @property
    def is_black(self) -> bool:
        """True for ♠ and ♣, the suits whose King is worth 13 (ruleset §2)."""
        return not self.is_red


def card_value(rank: str, suit: Suit) -> int:
    """Point value of one card (ruleset §2, "Card values").

    Ace 1, 2-10 printed value, Jack 11, Queen 12, black King 13, red King 0.
    """
    if rank == "A":
        return 1
    if rank == "J":
        return 11
    if rank == "Q":
        return 12
    if rank == "K":
        return 0 if suit.is_red else 13
    return int(rank)


@dataclass(frozen=True)
class Card:
    """One physical card, identified by a unique id within a round."""

    card_id: int
    rank: str
    suit: Suit

    @property
    def value(self) -> int:
        """Point value contributed to a player's card total (ruleset §2)."""
        return card_value(self.rank, self.suit)

    @property
    def label(self) -> str:
        """Short human readable label, e.g. ``K♥``."""
        return f"{self.rank}{self.suit.value}"

    @property
    def is_ace(self) -> bool:
        """Aces can never be taken from the discard pile (ruleset §4)."""
        return self.rank == "A"

    @property
    def has_ability(self) -> bool:
        """True for Ace, Jack and Queen (ruleset §5)."""
        return self.rank in ABILITY_RANKS


def deck_count_for(num_players: int) -> int:
    """Number of standard decks required (ruleset §2).

    ``ceil(num_players / 4)``; the standard game is 4 players, but 2 and 3 are
    allowed as well.
    """
    if num_players < 2:
        raise ValueError("Alfredo needs at least 2 players")
    return math.ceil(num_players / 4)


def build_deck(deck_count: int, rng: random.Random) -> list[Card]:
    """Build ``deck_count`` combined decks and shuffle them into one draw pile.

    Ruleset §2: with more than one deck the decks are combined into one draw
    pile; §3: the whole thing is shuffled before dealing.
    """
    cards: list[Card] = []
    card_id = 1
    for _ in range(deck_count):
        for suit in Suit:
            for rank in RANKS:
                cards.append(Card(card_id=card_id, rank=rank, suit=suit))
                card_id += 1
    rng.shuffle(cards)
    return cards
