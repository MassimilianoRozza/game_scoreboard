"""Shared helpers for the Alfredo tests: deterministic decks and scripted tables."""

from __future__ import annotations

import random

from cardgame.alfredo.cards import Card, Suit
from cardgame.alfredo.engine import AlfredoGame, GameConfig
from cardgame.alfredo.state import Slot

HEARTS = Suit.HEARTS
DIAMONDS = Suit.DIAMONDS
CLUBS = Suit.CLUBS
SPADES = Suit.SPADES

_next_id = 1


def card(rank: str, suit: Suit = SPADES) -> Card:
    """Build a card with a fresh unique id."""
    global _next_id
    instance = Card(card_id=_next_id, rank=rank, suit=suit)
    _next_id += 1
    return instance


def build_deck_for(
    hands: list[list[Card]], extra_deck: list[Card] | None = None
) -> list[Card]:
    """Assemble a draw pile that deals exactly ``hands`` to the players.

    Dealing pops from the end of the list, one card per player per round, so
    the tail of the returned list is what gets dealt first. ``extra_deck`` is
    placed underneath and is drawn later, in the given order.
    """
    num_players = len(hands)
    per_slot: list[Card] = []
    for slot in range(max(len(hand) for hand in hands)):
        for player_index in range(num_players):
            if slot < len(hands[player_index]):
                per_slot.append(hands[player_index][slot])
    # Dealing pops from the end, so per_slot[0] must sit at the end of the pile
    # and the later-drawn cards go underneath it.
    pile = list(reversed(extra_deck or []))
    pile.extend(reversed(per_slot))
    return pile


def make_game(
    hands: list[list[Card]],
    policies: list[object],
    extra_deck: list[Card] | None = None,
    known_slots: list[list[int]] | None = None,
    seed: int = 0,
) -> AlfredoGame:
    """A game with pre-arranged hands, draw pile and memories.

    Hands of any length are supported: the deal is performed from a pile that
    holds filler cards on top (immediately overwritten) with the requested
    ``extra_deck`` underneath, so later draws come in the given order.
    """
    names = [f"P{index}" for index in range(len(hands))]
    padded = [list(hand) + [card("2", CLUBS) for _ in range(4 - len(hand))] for hand in hands]
    game = AlfredoGame(
        names,
        random.Random(seed),
        GameConfig(num_players=len(hands), num_rounds=1),
        policies=policies,  # type: ignore[arg-type]
    )
    game.start_round(deck=build_deck_for(padded, extra_deck))
    for player_index, hand in enumerate(hands):
        game.players[player_index].hand = [Slot(card=one) for one in hand]
    if known_slots is None:
        known_slots = [list(range(len(hand))) for hand in hands]
    for player_index, player in enumerate(game.players):
        for slot_index, slot in enumerate(player.hand):
            if slot_index in known_slots[player_index]:
                slot.remember(slot.card.rank, slot.card.suit)
            else:
                slot.memory_valid = False
    return game
