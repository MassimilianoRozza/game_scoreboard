"""Alfredo rules engine package.

Public API for playing, simulating and testing Alfredo exactly as described in
``alfredoRuleSet.md``. Nothing here imports FastAPI, so the engine can be used
from tests, scripts or a future web route alike.
"""

from __future__ import annotations

from .bots import BotPolicy, ScriptedPolicy, make_policies
from .cards import Card, Suit, build_deck, card_value, deck_count_for
from .engine import (
    CALLER_PENALTY,
    CALLER_REWARD,
    CARDS_PER_PLAYER,
    AlfredoGame,
    GameConfig,
    RoundResult,
)
from .report import render_match, render_round, render_standings
from .state import GameLog, LogEntry, Player, Slot
from .views import GameView, PlayerView, SlotView

__all__ = [
    "AlfredoGame",
    "BotPolicy",
    "CALLER_PENALTY",
    "CALLER_REWARD",
    "CARDS_PER_PLAYER",
    "Card",
    "GameConfig",
    "GameLog",
    "GameView",
    "LogEntry",
    "Player",
    "PlayerView",
    "RoundResult",
    "ScriptedPolicy",
    "Slot",
    "SlotView",
    "Suit",
    "build_deck",
    "card_value",
    "deck_count_for",
    "make_policies",
    "render_match",
    "render_round",
    "render_standings",
]
