"""Rule-by-rule tests for the Alfredo engine, one per ruleset clause.

Each test cites the section of ``alfredoRuleSet.md`` it pins. Hands and draw
piles are pre-arranged so behaviour is exact rather than statistical.
"""

from __future__ import annotations

import random

import pytest

from alfredo_helpers import CLUBS, DIAMONDS, HEARTS, SPADES, card, make_game
from cardgame.alfredo.bots import ScriptedPolicy
from cardgame.alfredo.cards import build_deck, card_value, deck_count_for
from cardgame.alfredo.engine import CALLER_PENALTY, CALLER_REWARD, AlfredoGame, GameConfig
from cardgame.alfredo.state import Slot

# ------------------------------------------------------------------ §2 cards


@pytest.mark.parametrize(
    ("rank", "suit", "expected"),
    [
        ("A", SPADES, 1),
        ("A", HEARTS, 1),
        ("2", CLUBS, 2),
        ("7", DIAMONDS, 7),
        ("10", HEARTS, 10),
        ("J", SPADES, 11),
        ("Q", CLUBS, 12),
        ("K", SPADES, 13),
        ("K", CLUBS, 13),
        ("K", HEARTS, 0),
        ("K", DIAMONDS, 0),
    ],
)
def test_card_values_match_the_ruleset_table(rank: str, suit, expected: int) -> None:
    """§2 "Card values": red Kings are 0, black Kings 13, J 11, Q 12, A 1."""
    assert card_value(rank, suit) == expected


@pytest.mark.parametrize(("players", "decks"), [(2, 1), (4, 1), (5, 2), (8, 2), (9, 3)])
def test_deck_count_is_ceiling_of_players_over_four(players: int, decks: int) -> None:
    """§2: number of decks = ceil(players / 4)."""
    assert deck_count_for(players) == decks


def test_deck_has_fifty_two_cards_per_deck_and_no_jokers() -> None:
    """§2: standard 52-card poker decks, jokers removed, combined into one pile."""
    rng = random.Random(3)
    deck = build_deck(2, rng)
    assert len(deck) == 104
    assert len({card_instance.card_id for card_instance in deck}) == 104
    assert sum(1 for card_instance in deck if card_instance.rank == "K") == 8
    assert sum(1 for card_instance in deck if card_instance.suit.is_red) == 52


def test_deck_count_rejects_a_single_player() -> None:
    with pytest.raises(ValueError):
        deck_count_for(1)


# ------------------------------------------------------------------ §3 setup


def test_setup_deals_four_cards_and_leaves_the_rest_as_draw_pile() -> None:
    """§3: 4 face-down cards each, remainder forms the draw pile."""
    rng = random.Random(11)
    game = AlfredoGame(["A", "B", "C", "D"], rng, GameConfig(num_players=4, num_rounds=1))
    game.start_round()
    assert all(player.card_count == 4 for player in game.players)
    assert len(game.deck) == 52 - 16
    assert game.discard == []


def test_each_player_remembers_exactly_one_starting_card() -> None:
    """§3.3-3.4: each player looks at exactly one of their own cards."""
    rng = random.Random(5)
    game = AlfredoGame(["A", "B", "C", "D"], rng, GameConfig(num_players=4, num_rounds=1))
    game.start_round()
    for player in game.players:
        known = [slot for slot in player.hand if slot.memory_valid]
        assert len(known) == 1
        assert known[0].memory_rank == known[0].card.rank
        assert known[0].memory_suit == known[0].card.suit


def test_playing_order_is_the_established_order() -> None:
    """§3.6: turns follow the established order."""
    rng = random.Random(2)
    game = AlfredoGame(["A", "B", "C", "D"], rng, GameConfig(num_players=4, num_rounds=1))
    game.start_round()
    assert game.current == 0
    assert [game.players[index].name for index in game.final_order] == []


# --------------------------------------------------------------- §4 a turn


def test_ace_cannot_be_taken_from_the_discard_pile() -> None:
    """§4 Option B: any discard-pile card except an Ace."""
    hands = [[card("5"), card("6"), card("7"), card("8")]] * 2
    game = make_game(hands, [ScriptedPolicy(), ScriptedPolicy()])
    game.discard.append(card("A", HEARTS))
    assert game.legal_discard_picks() == []


def test_discard_pile_pick_must_be_exchanged_never_returned() -> None:
    """§4: a discard-pile card must be exchanged and cannot go back."""
    five = card("5", CLUBS)
    queen = card("Q", HEARTS)
    hands = [[card("9"), card("10"), card("2"), card("3")], [card("4"), card("4"), card("4"), card("4")]]
    policy = ScriptedPolicy(
        sources=[("discard", five.card_id)],
        slots=[0],
        queen_targets=[None],
        default_reaction=None,
    )
    other = ScriptedPolicy(default_reaction=None)
    game = make_game(hands, [policy, other])
    game.discard.append(five)
    game.take_turn(0)
    assert game.players[0].hand[0].card is five
    assert five not in game.discard
    assert game.players[0].card_count == 4
    # The replaced card is the one now on the discard pile.
    assert game.discard and game.discard[-1].rank == "9"


def test_deck_draw_may_be_discarded_and_its_ability_ignored() -> None:
    """§4: discarding the drawn card directly ignores its special ability."""
    drawn = card("Q", SPADES)
    hands = [[card("2"), card("3"), card("4"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policy = ScriptedPolicy(keeps=[False], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[drawn])
    before = [player.card_count for player in game.players]
    game.take_turn(0)
    assert game.discard[-1] is drawn
    assert [player.card_count for player in game.players] == before
    # No Queen ability happened: nobody gained a memory of an extra card.
    assert sum(1 for entry in game.log.entries if entry.kind == "ability") == 0


def test_normal_exchange_does_not_change_card_count() -> None:
    """§4: a normal exchange leaves the player's card count unchanged."""
    drawn = card("2", CLUBS)
    hands = [[card("K", SPADES), card("Q", CLUBS), card("J", HEARTS), card("9")]] * 2
    policy = ScriptedPolicy(keeps=[True], slots=[0], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[drawn])
    game.take_turn(0)
    assert game.players[0].card_count == 4
    assert game.players[0].hand[0].card is drawn


def test_replaced_card_ability_resolves_outside_the_final_round() -> None:
    """§4 step 4 / §5: the discarded card's ability is resolved."""
    hands = [[card("A", CLUBS), card("9"), card("9"), card("9")], [card("7"), card("7"), card("7"), card("7")]]
    extra = card("4", HEARTS)
    policy = ScriptedPolicy(
        keeps=[True],
        slots=[0],
        ace_targets=[1],
        default_reaction=None,
    )
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[card("2"), extra])
    game.take_turn(0)
    assert game.players[1].card_count == 5
    assert extra in [slot.card for slot in game.players[1].hand]


# ------------------------------------------------------------- §5 specials


def test_ace_may_target_the_actor_and_adds_one_card() -> None:
    """§5 Ace: the actor may choose themselves; the recipient gains a card."""
    hands = [[card("A", SPADES), card("5"), card("5"), card("5")], [card("6"), card("6"), card("6"), card("6")]]
    extra = card("10", DIAMONDS)
    policy = ScriptedPolicy(ace_targets=[0], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[extra])
    game._ability_ace(0, card("A", SPADES))
    assert game.players[0].card_count == 5
    assert extra in [slot.card for slot in game.players[0].hand]
    assert game.players[1].card_count == 4


def test_ace_target_gains_card_without_replacing_anything() -> None:
    """§5 Ace: the recipient adds the card without replacing one."""
    hands = [[card("A", CLUBS), card("5"), card("5"), card("5")], [card("6"), card("6"), card("6"), card("6")]]
    extra = card("K", HEARTS)
    policy = ScriptedPolicy(ace_targets=[1], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[extra])
    game._ability_ace(0, card("A", CLUBS))
    recipient = game.players[1]
    assert recipient.card_count == 5
    assert recipient.hand[0].card.rank == "6"


def test_jack_swaps_between_two_different_players_blindly() -> None:
    """§5 Jack: two different players, cards stay face down, nobody looks."""
    first = card("2", CLUBS)
    second = card("K", SPADES)
    hands = [[first, card("5"), card("5"), card("5")], [second, card("6"), card("6"), card("6")]]
    policy = ScriptedPolicy(jack_pairs=[(0, 1)], jack_slots=[(0, 0)], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)])
    game._ability_jack(0, card("J", HEARTS))
    assert game.players[0].hand[0].card is second
    assert game.players[1].hand[0].card is first
    # Neither owner learned anything: memory follows the slot, not the card.
    assert not game.players[0].hand[0].memory_valid
    assert not game.players[1].hand[0].memory_valid
    assert game.players[0].card_count == 4 and game.players[1].card_count == 4


def test_jack_rejects_two_identical_players() -> None:
    """§5 Jack: the two selected players must be different."""
    hands = [[card("5")] * 4, [card("6")] * 4]
    policy = ScriptedPolicy(jack_pairs=[(0, 0)], jack_slots=[(0, 0)], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)])
    with pytest.raises(ValueError):
        game._ability_jack(0, card("J", CLUBS))


def test_jack_may_include_the_actor_as_one_player() -> None:
    """§5 Jack: a player may choose themselves as one of the two players."""
    hands = [[card("2", CLUBS), card("5"), card("5"), card("5")], [card("9"), card("6"), card("6"), card("6")]]
    policy = ScriptedPolicy(jack_pairs=[(1, 0)], jack_slots=[(0, 1)], default_reaction=None)
    game = make_game(hands, [ScriptedPolicy(default_reaction=None), policy])
    game._ability_jack(1, card("J", SPADES))
    assert game.players[1].hand[0].card.rank == "5"
    assert game.players[0].hand[1].card.rank == "9"


def test_queen_peek_records_memory_without_changing_cards() -> None:
    """§5 Queen: look at one face-down card, return it face down."""
    hands = [[card("5"), card("5"), card("5"), card("5")], [card("Q", CLUBS), card("6"), card("6"), card("6")]]
    hidden = card("4", DIAMONDS)
    hands[1][1] = hidden
    policy = ScriptedPolicy(queen_targets=[(1, 1)], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)])
    game._ability_queen(0, card("Q", CLUBS))
    slot = game.players[1].hand[1]
    assert slot.memory_valid and slot.memory_rank == "4" and slot.memory_suit is DIAMONDS
    assert game.players[0].card_count == 4 and game.players[1].card_count == 4


def test_queen_ability_may_be_declined() -> None:
    """§5 Queen: the player *may* look, so declining is legal."""
    hands = [[card("Q", HEARTS), card("5"), card("5"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policy = ScriptedPolicy(queen_targets=[None], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)])
    game._ability_queen(0, card("Q", HEARTS))
    assert not any(entry.kind == "ability" and "used the Queen" in entry.message for entry in game.log.entries)


def test_red_king_has_no_ability_and_scores_zero() -> None:
    """§5 Red King: zero points, no special ability."""
    red_king = card("K", HEARTS)
    assert red_king.value == 0
    assert not red_king.has_ability
    hands = [[red_king, card("5"), card("5"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policy = ScriptedPolicy(keeps=[True], slots=[0], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[card("2")])
    game.take_turn(0)
    assert not any(entry.kind == "ability" for entry in game.log.entries)


# ------------------------------------------------------------ §6 reactions


def test_correct_reaction_discards_the_matching_card() -> None:
    """§6: a correct reaction removes the card and puts it on the discard pile."""
    hands = [[card("7"), card("7"), card("7"), card("7")], [card("7", HEARTS), card("2"), card("3"), card("4")]]
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, None], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("7", CLUBS)])
    before = game.players[1].card_count
    game.take_turn(0)
    assert game.players[1].card_count == before - 1
    assert game.discard[-1].rank == "7"


def test_wrong_reaction_keeps_card_and_draws_one_penalty() -> None:
    """§6 "An incorrect reaction": keep the card, draw one, count increases by one."""
    hands = [[card("7"), card("7"), card("7"), card("7")], [card("2"), card("3"), card("4"), card("5")]]
    penalty = card("9", DIAMONDS)
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, None], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("7", CLUBS), penalty])
    game.take_turn(0)
    assert game.players[1].card_count == 5
    assert penalty in [slot.card for slot in game.players[1].hand]
    # The wrongly attempted card stays face down in its place.
    assert game.players[1].hand[0].card.rank == "2"


def test_wrong_attempt_bans_the_player_for_the_rest_of_the_window() -> None:
    """§6: after a wrong attempt the player cannot react again in this window."""
    hands = [[card("7"), card("7"), card("7"), card("7")], [card("2"), card("7", HEARTS), card("3"), card("4")]]
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    # First attempt is wrong (slot 0 is a 2), second would have matched slot 1.
    reactor = ScriptedPolicy(reactions=[0, 1, None], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("7", CLUBS), card("9")])
    game.take_turn(0)
    assert game.players[1].card_count == 5
    assert not any(entry.kind == "reaction_ok" for entry in game.log.entries)


def test_player_may_discard_several_matching_cards_in_one_window() -> None:
    """§6: multiple reactions by the same player while the window is open."""
    hands = [
        [card("7"), card("7"), card("7"), card("7")],
        [card("7", HEARTS), card("7", DIAMONDS), card("7", CLUBS), card("2")],
    ]
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, 0, 0, None], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("7", CLUBS)])
    game.take_turn(0)
    assert game.players[1].card_count == 1
    assert sum(1 for entry in game.log.entries if entry.kind == "reaction_ok") == 3


def test_reaction_discard_resolves_its_ability() -> None:
    """§6: a correct reaction's ability is resolved outside the final round."""
    jack = card("J", CLUBS)
    hands = [
        [card("J"), card("J"), card("J"), card("J")],
        [jack, card("2"), card("3"), card("4")],
    ]
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, None], jack_pairs=[(0, 1)], jack_slots=[(0, 0)], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("J", DIAMONDS), card("9")])
    game.take_turn(0)
    assert any(entry.kind == "ability" and "used the Jack" in entry.message for entry in game.log.entries)
    # The swap really moved cards: P0 now holds the 2 that P1 discarded nothing of.
    assert "2" in [slot.card.rank for slot in game.players[0].hand]


def test_reaction_ability_does_not_open_a_new_window() -> None:
    """§6: the required rank stays that of the original discard."""
    jack = card("J", CLUBS)
    hands = [[card("J"), card("J"), card("J"), card("J")], [jack, card("2"), card("3"), card("4")]]
    actor = ScriptedPolicy(keeps=[False], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, None], jack_pairs=[(0, 1)], jack_slots=[(0, 0)], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("J", DIAMONDS), card("9")])
    game.take_turn(0)
    opens = [entry for entry in game.log.entries if entry.kind == "reaction_open"]
    assert len(opens) == 1
    assert "match a J" in opens[0].message


def test_actor_may_not_react_to_their_own_discard() -> None:
    """§6: the reaction opportunity belongs to the other players."""
    hands = [[card("7"), card("7"), card("7"), card("7")], [card("2"), card("3"), card("4"), card("5")]]
    actor = ScriptedPolicy(keeps=[False], reactions=[0, None], default_reaction=None)
    game = make_game(
        hands, [actor, ScriptedPolicy(default_reaction=None)], extra_deck=[card("7", CLUBS)]
    )
    game.take_turn(0)
    assert game.players[0].card_count == 4
    assert not any(entry.kind == "reaction_ok" for entry in game.log.entries)


def test_reaction_still_works_during_the_final_round() -> None:
    """§7: the matching-reaction rule remains in effect during the final round."""
    hands = [
        [card("J", CLUBS), card("7"), card("7"), card("7")],
        [card("J", HEARTS), card("2"), card("3"), card("4")],
    ]
    actor = ScriptedPolicy(keeps=[True], slots=[0], default_reaction=None)
    reactor = ScriptedPolicy(reactions=[0, None], default_reaction=None)
    game = make_game(hands, [actor, reactor], extra_deck=[card("2", DIAMONDS)])
    game.call_alfredo(1)
    assert game.final_round
    game.take_turn(0)
    # The Jack was discarded, its ability is off, but P1 still matched it.
    assert any(entry.kind == "ability_skipped" for entry in game.log.entries)
    assert any(entry.kind == "reaction_ok" for entry in game.log.entries)
    assert game.players[1].card_count == 3


def test_abilities_are_disabled_once_alfredo_is_called() -> None:
    """§7: special abilities no longer work after the call."""
    hands = [[card("A", CLUBS), card("5"), card("5"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policy = ScriptedPolicy(ace_targets=[1], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)], extra_deck=[card("2")])
    game.call_alfredo(1)
    assert game.final_round
    game.resolve_ability(0, card("A", CLUBS))
    assert game.players[1].card_count == 4
    assert any(entry.kind == "ability_skipped" for entry in game.log.entries)


# ---------------------------------------------------------- §7 calling out


def test_final_turns_end_with_the_player_before_the_caller() -> None:
    """§7 example: A→B→C→D, B calls, so C, D and A take the final turns."""
    names = ["A", "B", "C", "D"]
    rng = random.Random(0)
    game = AlfredoGame(names, rng, GameConfig(num_players=4, num_rounds=1))
    game.start_round()
    game.call_alfredo(1)
    assert [names[index] for index in game.final_order] == ["C", "D", "A"]
    assert 1 not in game.final_order


def test_every_other_player_gets_exactly_one_final_turn() -> None:
    """§7: exactly one final turn each, and the caller gets none."""
    hands = [[card("2"), card("3"), card("4"), card("5")]] * 4
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(4)]
    policies[1] = ScriptedPolicy(default_call=True, default_reaction=None)
    game = make_game(hands, policies)
    result = game.play_round()
    assert game.caller == 1
    assert game.final_order == [2, 3, 0]
    assert result.case in {"A", "B", "C"}


def test_calling_alfredo_consumes_the_callers_turn() -> None:
    """§7: the call replaces a normal turn; the caller takes no further turn."""
    hands = [[card("2"), card("3"), card("4"), card("5")]] * 3
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(3)]
    policies[0] = ScriptedPolicy(default_call=True, default_reaction=None)
    game = make_game(hands, policies)
    game.play_round()
    assert game.turn_number == 3
    assert game.final_order == [1, 2]


# ------------------------------------------------------------- §8 scoring


def _hand_summing_to(total: int) -> list[Slot]:
    """Four cards whose values add up to ``total`` (0-52 reachable)."""
    cards: list = []
    remaining = total
    for rank, value in (("K", 13), ("Q", 12), ("J", 11)):
        take = min(remaining // value, 1)
        if take:
            cards.append(_card_of_value(value))
            remaining -= value
    cards.append(_card_of_value(remaining))
    while len(cards) < 4:
        cards.append(_card_of_value(0))
    return [Slot(card=one) for one in cards]


def _score_with_totals(game: AlfredoGame, totals: dict[str, int]) -> None:
    """Give each named player a hand whose card total is exactly the target."""
    for name, total in totals.items():
        player = next(p for p in game.players if p.name == name)
        player.hand = _hand_summing_to(total)


def _card_of_value(value: int):
    """A card whose point value is exactly ``value`` (0-13)."""
    if value == 0:
        return card("K", HEARTS)
    if value == 1:
        return card("A")
    if value == 11:
        return card("J")
    if value == 12:
        return card("Q")
    if value == 13:
        return card("K", SPADES)
    return card(str(value))


def test_case_a_uniquely_lowest_caller_scores_minus_ten() -> None:
    """§8 Case A / §9: Alice 8, Bob 15, Charlie 21, Diana 12 → −10, 15, 21, 12."""
    hands = [[card("2")] * 4 for _ in range(4)]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(4)]
    game = make_game(hands, policies)
    assert [player.name for player in game.players] == ["P0", "P1", "P2", "P3"]
    _score_with_totals(game, {"P0": 8, "P1": 15, "P2": 21, "P3": 12})
    game.caller = 0
    result = game.score_round()
    assert result.case == "A"
    assert result.round_scores == {"P0": -10, "P1": 15, "P2": 21, "P3": 12}


def test_case_b_caller_not_lowest_gets_plus_ten_and_lowest_gets_zero() -> None:
    """§8 Case B / §9: Alice 14, Bob 9, Charlie 21, Diana 12 → 24, 0, 21, 12."""
    hands = [[card("2")] * 4 for _ in range(4)]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(4)]
    game = make_game(hands, policies)
    _score_with_totals(game, {"P0": 14, "P1": 9, "P2": 21, "P3": 12})
    game.caller = 0
    result = game.score_round()
    assert result.case == "B"
    assert result.round_scores == {"P0": 24, "P1": 0, "P2": 21, "P3": 12}


def test_case_c_caller_tied_for_lowest_no_adjustment() -> None:
    """§8 Case C / §9: caller ties for lowest → everyone scores their own total."""
    hands = [[card("2")] * 4 for _ in range(4)]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(4)]
    game = make_game(hands, policies)
    _score_with_totals(game, {"P0": 9, "P1": 9, "P2": 21, "P3": 12})
    game.caller = 0
    result = game.score_round()
    assert result.case == "C"
    assert result.round_scores == {"P0": 9, "P1": 9, "P2": 21, "P3": 12}


def test_caller_reward_and_penalty_constants() -> None:
    """§8: the reward is −10 and the penalty +10, applied as described."""
    assert CALLER_REWARD == -10
    assert CALLER_PENALTY == 10


def test_round_without_a_caller_scores_everyones_card_total() -> None:
    """§8 fallback: no Alfredo call means no ±10 adjustment anywhere."""
    hands = [[card("2")] * 4 for _ in range(2)]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(2)]
    game = make_game(hands, policies)
    _score_with_totals(game, {"P0": 5, "P1": 9})
    result = game.score_round()
    assert result.case == "none"
    assert result.round_scores == {"P0": 5, "P1": 9}


def test_cumulative_scores_accumulate_across_rounds() -> None:
    """§10: each round's score is added to the running total."""
    hands = [[card("2"), card("3"), card("4"), card("5")]] * 2
    policies = [
        ScriptedPolicy(default_call=True, default_reaction=None),
        ScriptedPolicy(default_reaction=None),
    ]
    game = make_game(hands, policies, seed=4)
    game.config = GameConfig(num_players=2, num_rounds=2)
    results = game.play_match()
    assert len(results) == 2
    for player in game.players:
        assert player.cumulative_score == sum(result.round_scores[player.name] for result in results)


# ------------------------------------------------------------ edge rulings


def test_draw_pile_exhaustion_ends_the_round() -> None:
    """Ruling: with no deck and no takeable discard the round ends and is scored."""
    hands = [[card("2"), card("3"), card("4"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(2)]
    game = make_game(hands, policies, extra_deck=[])
    game.deck = []
    game.discard = []
    game.take_turn(0)
    assert game.ended_by_draw_pile
    result = game.score_round()
    assert result.ended_by_draw_pile
    assert result.case == "none"
    assert result.round_scores == result.card_totals


def test_aces_left_in_the_discard_pile_are_never_reachable() -> None:
    """§4: Aces cannot be picked up, so they never return to play."""
    hands = [[card("2"), card("3"), card("4"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policies = [ScriptedPolicy(default_reaction=None) for _ in range(2)]
    game = make_game(hands, policies)
    ace = card("A", HEARTS)
    game.discard.append(ace)
    game.deck = []
    assert game.legal_discard_picks() == []
    assert ace not in game.deck


def test_two_player_match_is_supported() -> None:
    """§2 allows 2-3 players even though 4 is the standard game."""
    hands = [[card("2"), card("3"), card("4"), card("5")], [card("6"), card("7"), card("8"), card("9")]]
    policies = [
        ScriptedPolicy(default_call=True, default_reaction=None),
        ScriptedPolicy(default_reaction=None),
    ]
    game = make_game(hands, policies)
    result = game.play_round()
    assert game.deck_count == 1
    assert result.caller == "P0"


def test_jack_skipped_when_fewer_than_two_players_hold_cards() -> None:
    """Ruling: a Jack cannot target an empty hand, so the ability is skipped."""
    hands = [[card("5"), card("5"), card("5"), card("5")], []]
    policy = ScriptedPolicy(jack_pairs=[(0, 1)], default_reaction=None)
    game = make_game(hands, [policy, ScriptedPolicy(default_reaction=None)])
    game.players[1].hand = []
    game._ability_jack(0, card("J", CLUBS))
    assert any("could not use the Jack" in entry.message for entry in game.log.entries)


def test_card_count_invariant_holds_over_a_full_match() -> None:
    """§4/§5/§6: only an Ace gift or a wrong reaction changes a card count."""
    rng = random.Random(17)
    from cardgame.alfredo.bots import make_policies

    game = AlfredoGame(
        ["A", "B", "C", "D"],
        rng,
        GameConfig(num_players=4, num_rounds=3),
        policies=make_policies(4, rng, "mixed"),
    )
    game.play_match()
    counts = [player.card_count for player in game.players]
    assert all(count > 0 for count in counts)
    last_round = max(entry.round_number for entry in game.log.entries)
    entries = [entry for entry in game.log.entries if entry.round_number == last_round]
    gifts = sum(
        1
        for entry in entries
        if entry.kind == "ability" and "extra face-down card" in entry.message
    )
    penalties = sum(1 for entry in entries if entry.kind == "reaction_bad")
    matches = sum(1 for entry in entries if entry.kind == "reaction_ok")
    empties = sum(1 for entry in entries if entry.kind == "keep_empty")
    expected = 4 * 4 + gifts + penalties + empties - matches
    assert sum(counts) == expected
