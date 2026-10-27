"""Bot decision policies.

Bots decide from ``GameView`` only, i.e. from memory, never from real card
faces. Two failure modes are modelled explicitly:

* a *stale* memory (``known_rank`` present but the card moved away through a
  Jack swap) is trusted only with probability ``memory_reliability``;
* a *false recall* makes a bot believe a slot matches a rank it does not.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import Card
from .views import GameView, PlayerView, SlotView, rank_value

#: Value assumed for a card the bot has never looked at.
UNKNOWN_VALUE = 6.8


@dataclass
class BotPolicy:
    """A personality: how well the bot remembers and how eager it is to react."""

    name: str = "Bot"
    memory_reliability: float = 0.75
    false_recall: float = 0.08
    reaction_eagerness: float = 0.6
    call_confidence: float = 9.0
    rng: random.Random = field(default_factory=random.Random)

    # ------------------------------------------------------- turn decisions

    def should_call_alfredo(self, view: GameView, actor_index: int) -> bool:
        """Call Alfredo only on a noisy estimate, and never in the final round (§7)."""
        if view.final_round:
            return False
        if view.turn_number < 4:
            return False
        estimate = self._noisy_estimate(view.player(actor_index))
        if estimate < self.call_confidence:
            return self.rng.random() < 0.5
        if estimate < self.call_confidence + 3:
            return self.rng.random() < 0.08
        return self.rng.random() < 0.004

    def choose_source(
        self, view: GameView, actor_index: int
    ) -> tuple[str, int | None]:
        """Pick the deck, or a specific non-Ace discard-pile card (§4)."""
        player = view.player(actor_index)
        if not player.slots:
            return "deck", None
        worst = self._worst_slot(player)
        best = min(view.discard_picks, key=lambda card: card.value, default=None)
        if best is not None and best.value < self._slot_estimate(worst) and self.rng.random() < 0.7:
            return "discard", best.card_id
        return "deck", None

    def should_keep_drawn(self, view: GameView, actor_index: int, card: Card) -> bool:
        """Keep a deck draw only if it improves the believed hand (§4)."""
        player = view.player(actor_index)
        if not player.slots:
            return True
        worst = self._worst_slot(player)
        if card.value < self._slot_estimate(worst):
            return True
        return self.rng.random() < 0.2

    def choose_slot_to_replace(self, view: GameView, actor_index: int, card: Card) -> int:
        """Replace the slot with the highest believed value (§4)."""
        player = view.player(actor_index)
        if not player.slots:
            raise ValueError("A player with no cards has no slot to replace")
        return self._worst_slot(player).slot_index

    # ----------------------------------------------------- ability decisions

    def choose_ace_target(self, view: GameView, actor_index: int) -> int | None:
        """Ace: hand the extra card to the opponent we least want to help (§5).

        The actor is a legal target and is included in the candidate set, as the
        ruleset explicitly allows.
        """
        candidates = [
            player.index
            for player in view.players
            if player.card_count > 0 or player.index == actor_index
        ]
        if not candidates:
            return None
        # Prefer opponents with many cards: an extra card hurts them more.
        candidates.sort(key=lambda index: -view.player(index).card_count)
        if self.rng.random() < 0.25:
            return self.rng.choice(candidates)
        return candidates[0]

    def choose_jack_pair(
        self, view: GameView, actor_index: int
    ) -> tuple[int, int] | None:
        """Jack: two *different* players holding cards; the actor may be one (§5)."""
        holders = [player.index for player in view.players if player.card_count > 0]
        if len(holders) < 2:
            return None
        first = self.rng.choice(holders)
        second = self.rng.choice([index for index in holders if index != first])
        return first, second

    def choose_jack_slots(
        self,
        view: GameView,
        actor_index: int,
        first_index: int,
        second_index: int,
    ) -> tuple[int, int]:
        """Jack: pick one slot from each player, preferring our own worst card."""
        first_player = view.player(first_index)
        second_player = view.player(second_index)
        if first_index == actor_index:
            first_slot = self._worst_slot(first_player).slot_index
        else:
            first_slot = self.rng.randrange(first_player.card_count)
        if second_index == actor_index:
            second_slot = self._worst_slot(second_player).slot_index
        else:
            second_slot = self.rng.randrange(second_player.card_count)
        return first_slot, second_slot

    def choose_queen_target(
        self, view: GameView, actor_index: int
    ) -> tuple[int, int] | None:
        """Queen: look at an unknown slot, or decline when nothing is unknown (§5)."""
        unknown = [
            (player.index, slot.slot_index)
            for player in view.players
            for slot in player.slots
            if not slot.is_known
        ]
        if not unknown:
            return None
        # Prefer our own unknown cards: knowledge we keep is worth more.
        own = [target for target in unknown if target[0] == actor_index]
        pool = own if own and self.rng.random() < 0.6 else unknown
        return self.rng.choice(pool)

    # ---------------------------------------------------- reaction decisions

    def choose_reaction_slot(
        self, view: GameView, player_index: int, required_rank: str
    ) -> int | None:
        """Try to shed a card believed to match, or pass (§6).

        Returning a slot whose real rank differs is a wrong attempt: the engine
        keeps the card, draws a penalty card and bans this player for the rest
        of the window.
        """
        player = view.player(player_index)
        if not player.slots:
            return None
        believed = [
            slot.slot_index
            for slot in player.slots
            if slot.known_rank == required_rank
        ]
        if believed:
            if self.rng.random() < self.memory_reliability * self.reaction_eagerness:
                return self.rng.choice(believed)
            return None
        if self.rng.random() < self.false_recall * self.reaction_eagerness:
            return self.rng.choice([slot.slot_index for slot in player.slots])
        return None

    # ------------------------------------------------------------- internals

    def _worst_slot(self, player: PlayerView) -> SlotView:
        """The slot the bot believes is worst (highest value)."""
        return max(player.slots, key=self._slot_estimate)

    def _slot_estimate(self, slot: SlotView) -> float:
        """Believed value of one slot, with noise on a possibly stale memory."""
        if not slot.is_known:
            return UNKNOWN_VALUE
        value = float(rank_value(slot.known_rank or "", slot.known_suit))
        if self.rng.random() > self.memory_reliability:
            value += self.rng.choice((-2.0, 2.0))
        return value

    def _noisy_estimate(self, player: PlayerView) -> float:
        """A shaky total used only to decide whether to call Alfredo."""
        total = 0.0
        for slot in player.slots:
            if slot.is_known and self.rng.random() < self.memory_reliability:
                total += float(rank_value(slot.known_rank or "", slot.known_suit))
            else:
                total += UNKNOWN_VALUE
        return total


@dataclass
class ScriptedPolicy(BotPolicy):
    """A policy whose answers are pre-programmed, used by the rule tests.

    Each hook pops from its own queue; when a queue is empty the scripted
    default applies, so tests only specify what they care about.
    """

    calls: list[bool] = field(default_factory=list)
    sources: list[tuple[str, int | None]] = field(default_factory=list)
    keeps: list[bool] = field(default_factory=list)
    slots: list[int] = field(default_factory=list)
    ace_targets: list[int | None] = field(default_factory=list)
    jack_pairs: list[tuple[int, int] | None] = field(default_factory=list)
    jack_slots: list[tuple[int, int]] = field(default_factory=list)
    queen_targets: list[tuple[int, int] | None] = field(default_factory=list)
    reactions: list[int | None] = field(default_factory=list)
    default_call: bool = False
    default_source: tuple[str, int | None] = ("deck", None)
    default_keep: bool = True
    default_slot: int = 0
    default_reaction: int | None = None

    def _pop(self, queue: list[object], default: object) -> object:
        return queue.pop(0) if queue else default

    def should_call_alfredo(self, view: GameView, actor_index: int) -> bool:
        return bool(self._pop(self.calls, self.default_call))

    def choose_source(self, view: GameView, actor_index: int) -> tuple[str, int | None]:
        return self._pop(self.sources, self.default_source)  # type: ignore[return-value]

    def should_keep_drawn(self, view: GameView, actor_index: int, card: Card) -> bool:
        return bool(self._pop(self.keeps, self.default_keep))

    def choose_slot_to_replace(self, view: GameView, actor_index: int, card: Card) -> int:
        return int(self._pop(self.slots, self.default_slot))

    def choose_ace_target(self, view: GameView, actor_index: int) -> int | None:
        return self._pop(self.ace_targets, actor_index)  # type: ignore[return-value]

    def choose_jack_pair(
        self, view: GameView, actor_index: int
    ) -> tuple[int, int] | None:
        return self._pop(self.jack_pairs, (actor_index, (actor_index + 1) % view.num_players))  # type: ignore[return-value]

    def choose_jack_slots(
        self,
        view: GameView,
        actor_index: int,
        first_index: int,
        second_index: int,
    ) -> tuple[int, int]:
        return self._pop(self.jack_slots, (0, 0))  # type: ignore[return-value]

    def choose_queen_target(self, view: GameView, actor_index: int) -> tuple[int, int] | None:
        return self._pop(self.queen_targets, (actor_index, 0))  # type: ignore[return-value]

    def choose_reaction_slot(
        self, view: GameView, player_index: int, required_rank: str
    ) -> int | None:
        return self._pop(self.reactions, self.default_reaction)  # type: ignore[return-value]


def make_policies(count: int, rng: random.Random, style: str = "mixed") -> list[BotPolicy]:
    """Build ``count`` bot personalities, mirroring the reference table styles."""
    profiles: dict[str, list[tuple[float, float, float, float]]] = {
        "careful": [(0.90, 0.03, 0.45, 8.0), (0.86, 0.04, 0.40, 8.5), (0.91, 0.02, 0.35, 7.5)],
        "chaotic": [(0.55, 0.19, 0.90, 12.0), (0.63, 0.16, 0.85, 11.0), (0.59, 0.22, 0.95, 13.0)],
        "mixed": [(0.78, 0.07, 0.60, 9.0), (0.67, 0.12, 0.70, 10.0), (0.86, 0.045, 0.50, 8.5)],
    }
    table = profiles.get(style, profiles["mixed"])
    policies: list[BotPolicy] = []
    for index in range(count):
        memory, false_recall, eagerness, confidence = table[index % len(table)]
        policies.append(
            BotPolicy(
                name=f"bot{index + 1}",
                memory_reliability=memory,
                false_recall=false_recall,
                reaction_eagerness=eagerness,
                call_confidence=confidence,
                rng=rng,
            )
        )
    return policies
