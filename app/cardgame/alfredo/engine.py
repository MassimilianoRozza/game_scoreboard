"""The Alfredo rules engine.

This module is the authoritative implementation of ``alfredoRuleSet.md``. Each
method cites the section it implements. ``alfredo_card_game.html`` was used as
a reference only where it agrees with the ruleset (scoring, final-round order,
deck count); its reaction handling, Ace targeting, forced Queen peek and
draw-pile recycling are deliberately *not* reproduced.

Rulings where the ruleset is silent, recorded here so behaviour is explicit:

* **Draw pile empty.** A player must draw from the deck only when the discard
  pile offers no legal pick (no non-Ace card), or when their hand is empty and
  they therefore cannot exchange. If the draw pile is also empty the round ends
  immediately and is scored with whatever caller exists (often none), so no
  ``±10`` adjustment applies. There is no reshuffle: the ruleset never mentions
  one, and Aces in the discard pile stay unreachable forever.
* **Ace gift with an empty draw pile.** Nothing is given and the ability is a
  no-op rather than ending the round, because §5 describes a gift rather than a
  required draw.
* **Reaction window opening.** A window opens after *any* discard, including a
  deck draw that was discarded directly. The directly discarded card's own
  ability stays ignored (§4), but other players may still match its rank (§6).
* **Reaction ability cascade.** A correct reaction discard resolves its ability
  (§6) but does *not* open a new window: the required rank remains that of the
  original discard, and the window closes when the next turn would begin.
* **Jack with empty hands.** A Jack cannot target a player holding no cards, so
  the ability is skipped when fewer than two players hold cards.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cards import Card, build_deck, deck_count_for
from .state import GameLog, Player, Slot
from .views import GameView, PlayerView, SlotView

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .bots import BotPolicy

#: How many face-down cards each player is dealt (ruleset §3).
CARDS_PER_PLAYER = 4

#: Points awarded to a caller with the uniquely lowest total (ruleset §8 Case A).
CALLER_REWARD = -10

#: Points added to a caller who is not lowest (ruleset §8 Case B).
CALLER_PENALTY = 10


@dataclass(frozen=True)
class GameConfig:
    """Tunable, non-rule parameters of a match."""

    num_players: int = 4
    num_rounds: int = 1
    #: Upper bound on reaction attempts per player per window, purely a guard
    #: against a policy that never returns ``None``.
    max_reaction_attempts: int = 12


@dataclass
class RoundResult:
    """Outcome of one round, ready for the report layer."""

    round_number: int
    caller: str | None
    case: str
    message: str
    card_totals: dict[str, int]
    round_scores: dict[str, int]
    cumulative: dict[str, int]
    turns: int
    ended_by_draw_pile: bool


class AlfredoGame:
    """One Alfredo match: rounds, turns, abilities, reactions and scoring."""

    def __init__(
        self,
        player_names: list[str],
        rng: random.Random,
        config: GameConfig | None = None,
        policies: list["BotPolicy"] | None = None,
    ) -> None:
        self.config = config or GameConfig(num_players=len(player_names))
        if len(player_names) < 2:
            raise ValueError("Alfredo needs at least 2 players")
        if policies is not None and len(policies) != len(player_names):
            raise ValueError("One policy is required per player")
        self.rng = rng
        self.deck_count = deck_count_for(len(player_names))
        self.players: list[Player] = [
            Player(name=name, is_bot=True, policy=policies[index] if policies else None)
            for index, name in enumerate(player_names)
        ]
        self.log = GameLog()
        self.deck: list[Card] = []
        self.discard: list[Card] = []
        self.current: int = 0
        self.caller: int | None = None
        self.final_round: bool = False
        self.final_order: list[int] = []
        self.final_pos: int = 0
        self.turn_number: int = 0
        self.round_number: int = 0
        self.ended_by_draw_pile: bool = False
        self.results: list[RoundResult] = []

    # ------------------------------------------------------------------ setup

    def start_round(self, deck: list[Card] | None = None) -> None:
        """Deal a fresh round (ruleset §3).

        ``deck`` lets a caller supply a pre-arranged draw pile for tests or
        replays; the last element is the top of the pile. When omitted, the
        required number of shuffled decks is built.
        """
        self.round_number += 1
        self.log.round_number = self.round_number
        self.log.turn = 0
        self.turn_number = 0
        self.deck = list(deck) if deck is not None else build_deck(self.deck_count, self.rng)
        self.discard = []
        self.current = 0
        self.caller = None
        self.final_round = False
        self.final_order = []
        self.final_pos = 0
        self.ended_by_draw_pile = False

        for player in self.players:
            player.hand = []
            player.round_score = None
            player.card_total = None

        # §3.2 deal 4 face-down cards to each player, one at a time.
        for _ in range(CARDS_PER_PLAYER):
            for player in self.players:
                player.hand.append(Slot(card=self.deck.pop()))

        # §3.3-3.4 each player looks at exactly one of their own cards and
        # returns it face down to the same position.
        for player in self.players:
            slot_index = self.rng.randrange(len(player.hand))
            slot = player.hand[slot_index]
            slot.remember(slot.card.rank, slot.card.suit)
            self.log.add(
                player.name,
                "peek",
                f"{player.name} looked at one of their own cards and put it back.",
            )

        self.log.add(
            None,
            "deal",
            f"Round {self.round_number} dealt with {self.deck_count} deck(s); "
            f"{len(self.deck)} cards remain in the draw pile.",
        )

    # ------------------------------------------------------------- draw pile

    def _draw(self) -> Card | None:
        """Take the top card of the draw pile, or ``None`` when it is empty."""
        if not self.deck:
            return None
        return self.deck.pop()

    def legal_discard_picks(self) -> list[Card]:
        """Cards currently takeable from the discard pile (ruleset §4 Option B).

        Aces may never be taken from the discard pile.
        """
        return [card for card in self.discard if not card.is_ace]

    # ------------------------------------------------------------- abilities

    def resolve_ability(self, actor_index: int, card: Card) -> None:
        """Resolve a discarded card's special ability (ruleset §5).

        Abilities fire only when the card is discarded from a player's
        face-down cards, and never once Alfredo has been called (§7).
        """
        if self.final_round:
            self.log.add(
                self.players[actor_index].name,
                "ability_skipped",
                f"{card.label} discarded after Alfredo: special abilities are off.",
            )
            return
        if self.players[actor_index].policy is None:  # pragma: no cover - human seats
            return
        if card.rank == "A":
            self._ability_ace(actor_index, card)
        elif card.rank == "J":
            self._ability_jack(actor_index, card)
        elif card.rank == "Q":
            self._ability_queen(actor_index, card)

    def _ability_ace(self, actor_index: int, card: Card) -> None:
        """Ace: give one extra face-down card to any player, including self (§5)."""
        actor = self.players[actor_index]
        target_index = actor.policy.choose_ace_target(self.view(), actor_index)
        if target_index is None or not (0 <= target_index < len(self.players)):
            self.log.add(actor.name, "ability", f"{actor.name} declined the Ace ability.")
            return
        extra = self._draw()
        if extra is None:
            self.log.add(
                actor.name,
                "ability",
                f"{actor.name} tried to give {self.players[target_index].name} a card, "
                "but the draw pile is empty.",
            )
            return
        self.players[target_index].hand.append(Slot(card=extra))
        self.log.add(
            actor.name,
            "ability",
            f"{actor.name} used the Ace to give {self.players[target_index].name} "
            f"an extra face-down card ({self.players[target_index].card_count} cards now).",
        )

    def _ability_jack(self, actor_index: int, card: Card) -> None:
        """Jack: swap one face-down card between two different players (§5)."""
        actor = self.players[actor_index]
        pair = actor.policy.choose_jack_pair(self.view(), actor_index)
        if pair is None:
            self.log.add(actor.name, "ability", f"{actor.name} declined the Jack ability.")
            return
        first_index, second_index = pair
        if first_index == second_index:
            raise ValueError("A Jack must swap cards between two different players")
        if not (
            0 <= first_index < len(self.players) and 0 <= second_index < len(self.players)
        ):
            raise ValueError("Jack targets must be players at this table")
        if not self.players[first_index].hand or not self.players[second_index].hand:
            self.log.add(
                actor.name,
                "ability",
                f"{actor.name} could not use the Jack: a target holds no cards.",
            )
            return
        first_slot, second_slot = actor.policy.choose_jack_slots(
            self.view(), actor_index, first_index, second_index
        )
        self._swap_slots(first_index, first_slot, second_index, second_slot)
        self.log.add(
            actor.name,
            "ability",
            f"{actor.name} used the Jack to swap one face-down card between "
            f"{self.players[first_index].name} and {self.players[second_index].name}.",
        )

    def _swap_slots(
        self, first_index: int, first_slot: int, second_index: int, second_slot: int
    ) -> None:
        """Exchange two cards while keeping both face down and both memories stale."""
        a = self.players[first_index].hand[first_slot]
        b = self.players[second_index].hand[second_slot]
        a.card, b.card = b.card, a.card
        # Memory follows the slot, not the card: neither owner learns anything.
        a.invalidate_memory()
        b.invalidate_memory()

    def _ability_queen(self, actor_index: int, card: Card) -> None:
        """Queen: privately look at one face-down card, optionally (§5)."""
        actor = self.players[actor_index]
        target = actor.policy.choose_queen_target(self.view(), actor_index)
        if target is None:
            self.log.add(actor.name, "ability", f"{actor.name} declined the Queen ability.")
            return
        player_index, slot_index = target
        if not (0 <= player_index < len(self.players)):
            raise ValueError("Queen target must be a player at this table")
        hand = self.players[player_index].hand
        if not (0 <= slot_index < len(hand)):
            raise ValueError("Queen target must be a slot that exists")
        slot = hand[slot_index]
        slot.remember(slot.card.rank, slot.card.suit)
        self.log.add(
            actor.name,
            "ability",
            f"{actor.name} used the Queen to look at one of "
            f"{self.players[player_index].name}'s face-down cards.",
        )

    # ------------------------------------------------------------ reactions

    def run_reaction_window(self, required_rank: str, actor_index: int) -> None:
        """Let the other players react to a discard (ruleset §6).

        The required rank is the rank of the card that opened the window; suits
        do not matter. A player may shed as many matching cards as they like,
        but the first wrong attempt bans them for the rest of the window.
        """
        order = [
            (actor_index + step) % len(self.players)
            for step in range(1, len(self.players))
        ]
        banned: set[int] = set()
        self.log.add(
            None,
            "reaction_open",
            f"Reaction window: match a {required_rank} before the next turn begins.",
        )
        for player_index in order:
            player = self.players[player_index]
            if player.policy is None:
                continue
            attempts = 0
            while player_index not in banned and attempts < self.config.max_reaction_attempts:
                slot_index = player.policy.choose_reaction_slot(
                    self.view(), player_index, required_rank
                )
                if slot_index is None:
                    break
                attempts += 1
                if not self._attempt_reaction(player_index, slot_index, required_rank):
                    # A wrong attempt bans this player for the rest of the window.
                    banned.add(player_index)

    def _attempt_reaction(self, player_index: int, slot_index: int, required_rank: str) -> bool:
        """One player's attempt to discard a matching card (ruleset §6).

        Returns ``True`` when the player may keep reacting, ``False`` when they
        are banned from the rest of this window.
        """
        player = self.players[player_index]
        if not (0 <= slot_index < len(player.hand)):
            return True
        slot = player.hand[slot_index]
        if slot.card.rank == required_rank:
            # Correct: the card goes face up on the discard pile and its ability
            # resolves, unless we are in the final Alfredo round.
            player.hand.pop(slot_index)
            self.discard.append(slot.card)
            self.log.add(
                player.name,
                "reaction_ok",
                f"{player.name} matched the {required_rank} and discarded {slot.card.label}.",
            )
            self.resolve_ability(player_index, slot.card)
            return True
        # Incorrect: keep the attempted card face down where it was, draw one
        # penalty card, and this player is done for this window.
        penalty = self._draw()
        if penalty is None:
            self.ended_by_draw_pile = True
            self.log.add(
                player.name,
                "draw_pile_empty",
                "The draw pile is empty: the round ends here.",
            )
            return False
        player.hand.append(Slot(card=penalty))
        self.log.add(
            player.name,
            "reaction_bad",
            f"{player.name} tried to match a {required_rank} with {slot.card.label}, "
            f"kept it and drew a penalty card ({player.card_count} cards now).",
        )
        return False

    # ---------------------------------------------------------- calling out

    def call_alfredo(self, caller_index: int) -> None:
        """Declare Alfredo and start the final round (ruleset §7).

        Every player other than the caller gets exactly one final turn, in the
        normal order, so the last final turn belongs to the player immediately
        before the caller. The caller gets no further turn.
        """
        self.caller = caller_index
        self.final_round = True
        count = len(self.players)
        self.final_order = [(caller_index + step) % count for step in range(1, count)]
        self.final_pos = 0
        self.log.add(
            self.players[caller_index].name,
            "alfredo",
            f"{self.players[caller_index].name} called Alfredo! Everyone else gets one "
            "final turn; special abilities are off.",
        )

    # ---------------------------------------------------------- taking turn

    def take_turn(self, actor_index: int) -> None:
        """Play one normal or final turn for ``actor_index`` (ruleset §4)."""
        actor = self.players[actor_index]
        self.turn_number += 1
        self.log.turn = self.turn_number

        if actor.policy is None:  # pragma: no cover - human seats are out of scope
            return

        if actor.policy.should_call_alfredo(self.view(), actor_index):
            self.call_alfredo(actor_index)
            return

        picks = self.legal_discard_picks()
        source, discard_card_id = actor.policy.choose_source(self.view(), actor_index)

        # A discard-pile card must be exchanged with an existing card, so a
        # player holding nothing can only draw from the deck (§4).
        if not actor.hand:
            source, discard_card_id = "deck", None

        chosen: Card | None = None
        if source == "discard" and discard_card_id is not None:
            chosen = self._take_from_discard(discard_card_id)
            if chosen is None:
                source = "deck"

        if source == "deck" or chosen is None:
            if not self.deck:
                # A discard-pile pick is only legal when the player can exchange
                # it, so an empty-handed player with an empty deck ends the round.
                if picks and actor.hand:
                    fallback = picks[0]
                    chosen = self._take_from_discard(fallback.card_id)
                    source = "discard"
                else:
                    self.ended_by_draw_pile = True
                    self.log.add(
                        actor.name,
                        "draw_pile_empty",
                        f"{actor.name} could not draw: the draw pile is empty and the "
                        "discard pile holds no takeable card. The round ends.",
                    )
                    return
            else:
                chosen = self._draw()
                source = "deck"

        assert chosen is not None
        self._finish_turn_with_card(actor_index, chosen, source)

    def _take_from_discard(self, card_id: int) -> Card | None:
        """Remove a card from the discard pile, rejecting Aces (§4 Option B)."""
        for position, card in enumerate(self.discard):
            if card.card_id == card_id:
                if card.is_ace:
                    raise ValueError("Aces cannot be taken from the discard pile")
                return self.discard.pop(position)
        return None

    def _finish_turn_with_card(self, actor_index: int, card: Card, source: str) -> None:
        """Decide between keeping the selected card or discarding it (§4)."""
        actor = self.players[actor_index]

        if source == "discard":
            # A card taken from the discard pile must be exchanged with one of
            # the player's existing cards; it can never go straight back.
            slot_index = actor.policy.choose_slot_to_replace(self.view(), actor_index, card)
            self._exchange(actor_index, slot_index, card)
            return

        keep = actor.policy.should_keep_drawn(self.view(), actor_index, card)
        if not actor.hand:
            # With no cards on the table the only legal option is to keep it,
            # and there is nothing to replace: the card simply joins the table.
            actor.hand.append(Slot(card=card))
            self.log.add(
                actor.name,
                "keep_empty",
                f"{actor.name} had no cards left and put {card.label} down.",
            )
            return
        if keep:
            slot_index = actor.policy.choose_slot_to_replace(self.view(), actor_index, card)
            self._exchange(actor_index, slot_index, card)
        else:
            # §4: discarding the drawn card directly ignores its special ability.
            self.discard.append(card)
            self.log.add(
                actor.name,
                "discard_drawn",
                f"{actor.name} drew and discarded {card.label} without replacing a card.",
            )
            self.run_reaction_window(card.rank, actor_index)

    def _exchange(self, actor_index: int, slot_index: int, incoming: Card) -> None:
        """Replace one face-down card and discard the replaced one (§4)."""
        actor = self.players[actor_index]
        if not (0 <= slot_index < len(actor.hand)):
            raise ValueError("Replacement slot must exist")
        slot = actor.hand[slot_index]
        replaced = slot.card
        slot.card = incoming
        # The incoming card was just looked at privately, so the owner knows it.
        slot.remember(incoming.rank, incoming.suit)
        self.discard.append(replaced)
        self.log.add(
            actor.name,
            "exchange",
            f"{actor.name} replaced a card with {incoming.label}; {replaced.label} "
            "went to the discard pile.",
        )
        # §4 step 4: resolve the ability of the discarded card, then §6 reactions.
        self.resolve_ability(actor_index, replaced)
        self.run_reaction_window(replaced.rank, actor_index)

    # ------------------------------------------------------------- scoring

    def score_round(self) -> RoundResult:
        """Score the round (ruleset §8) and add it to the cumulative totals."""
        totals = [player.true_total() for player in self.players]
        lowest = min(totals)
        lowest_indexes = [index for index, total in enumerate(totals) if total == lowest]

        if self.caller is None:
            case = "none"
            scores = list(totals)
            message = (
                "The round ended without an Alfredo call: everyone scores their own "
                "card total."
            )
        elif totals[self.caller] == lowest and len(lowest_indexes) == 1:
            # Case A: uniquely lowest caller.
            case = "A"
            scores = [
                CALLER_REWARD if index == self.caller else totals[index]
                for index in range(len(totals))
            ]
            message = (
                f"{self.players[self.caller].name} called Alfredo with the uniquely "
                f"lowest total ({lowest}) and scores {CALLER_REWARD}."
            )
        elif totals[self.caller] == lowest:
            # Case C: the caller ties for lowest, no adjustment at all.
            case = "C"
            scores = list(totals)
            message = (
                f"{self.players[self.caller].name} tied for the lowest total ({lowest}): "
                "everyone scores their own card total."
            )
        else:
            # Case B: caller is not lowest.
            case = "B"
            scores = [
                totals[index] + CALLER_PENALTY
                if index == self.caller
                else (0 if index in lowest_indexes else totals[index])
                for index in range(len(totals))
            ]
            message = (
                f"{self.players[self.caller].name} called Alfredo but was not lowest: "
                f"caller scores {totals[self.caller]} + {CALLER_PENALTY}, the lowest "
                f"player(s) score 0."
            )

        card_totals: dict[str, int] = {}
        round_scores: dict[str, int] = {}
        cumulative: dict[str, int] = {}
        for index, player in enumerate(self.players):
            player.card_total = totals[index]
            player.round_score = scores[index]
            player.cumulative_score += scores[index]
            card_totals[player.name] = totals[index]
            round_scores[player.name] = scores[index]
            cumulative[player.name] = player.cumulative_score

        result = RoundResult(
            round_number=self.round_number,
            caller=self.players[self.caller].name if self.caller is not None else None,
            case=case,
            message=message,
            card_totals=card_totals,
            round_scores=round_scores,
            cumulative=cumulative,
            turns=self.turn_number,
            ended_by_draw_pile=self.ended_by_draw_pile,
        )
        self.results.append(result)
        self.log.add(None, "score", message)
        return result

    # -------------------------------------------------------------- driving

    def play_round(self) -> RoundResult:
        """Play one whole round from the deal to the score sheet."""
        self.start_round()
        guard = 0
        limit = 500 * len(self.players)
        while True:
            if self.ended_by_draw_pile:
                break
            if self.final_round:
                if self.final_pos >= len(self.final_order):
                    break
                self.current = self.final_order[self.final_pos]
                self.take_turn(self.current)
                self.final_pos += 1
            else:
                self.take_turn(self.current)
                self.current = (self.current + 1) % len(self.players)
            if self.ended_by_draw_pile:
                break
            guard += 1
            if guard > limit:  # pragma: no cover - defensive, rules guarantee progress
                self.log.add(None, "stall", "Turn limit reached; ending the round.")
                break
        return self.score_round()

    def play_match(self) -> list[RoundResult]:
        """Play ``config.num_rounds`` rounds, keeping cumulative scores (§10)."""
        for _ in range(self.config.num_rounds):
            self.play_round()
        return self.results

    # --------------------------------------------------------------- views

    def view(self) -> GameView:
        """A memory-only snapshot handed to bot policies, so they cannot cheat."""
        player_views: list[PlayerView] = []
        for index, player in enumerate(self.players):
            slots = [
                SlotView(
                    slot_index=slot_index,
                    known_rank=slot.known_rank,
                    known_suit=slot.memory_suit if slot.memory_valid else None,
                )
                for slot_index, slot in enumerate(player.hand)
            ]
            player_views.append(
                PlayerView(
                    index=index,
                    name=player.name,
                    card_count=len(player.hand),
                    slots=slots,
                )
            )
        return GameView(
            current_index=self.current,
            caller_index=self.caller,
            final_round=self.final_round,
            turn_number=self.turn_number,
            deck_size=len(self.deck),
            discard_picks=[card for card in self.legal_discard_picks()],
            players=player_views,
        )
