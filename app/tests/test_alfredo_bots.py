"""Bot-vs-bot integration tests: full matches must be legal and reproducible."""

from __future__ import annotations

import random

import pytest

from cardgame.alfredo.bots import make_policies
from cardgame.alfredo.engine import AlfredoGame, GameConfig
from cardgame.alfredo.simulate import DEFAULT_NAMES, simulate_match


@pytest.mark.parametrize("num_players", [2, 3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("style", ["mixed", "careful", "chaotic"])
def test_full_match_completes_without_error(num_players: int, style: str) -> None:
    """A seeded bot-vs-bot match always terminates and scores every round."""
    summary = simulate_match(num_players=num_players, num_rounds=4, seed=42, style=style)
    assert len(summary.rounds) == 4
    for result in summary.rounds:
        assert result.case in {"A", "B", "C", "none"}
        assert set(result.round_scores) == set(summary.players)


def test_same_seed_reproduces_identical_results() -> None:
    """Determinism: the engine + policies share one seeded RNG."""
    first = simulate_match(num_players=4, num_rounds=6, seed=7)
    second = simulate_match(num_players=4, num_rounds=6, seed=7)
    assert [(r.case, r.caller, r.round_scores) for r in first.rounds] == [
        (r.case, r.caller, r.round_scores) for r in second.rounds
    ]
    assert first.standings == second.standings


def test_different_seeds_diverge() -> None:
    """Sanity check that the simulation is not degenerate."""
    outcomes = {
        tuple(score for score in simulate_match(num_players=4, num_rounds=3, seed=seed).standings)
        for seed in range(12)
    }
    assert len(outcomes) > 1


def test_cumulative_equals_sum_of_round_scores() -> None:
    """§10: cumulative totals are the sum of each round's score."""
    rng = random.Random(99)
    names = list(DEFAULT_NAMES[:4])
    game = AlfredoGame(
        names, rng, GameConfig(num_players=4, num_rounds=5), policies=make_policies(4, rng)
    )
    results = game.play_match()
    for player in game.players:
        assert player.cumulative_score == sum(r.round_scores[player.name] for r in results)


def test_every_round_has_at_most_one_caller_and_one_case() -> None:
    """Exactly one scoring case per round, with a caller unless the pile ran out."""
    summary = simulate_match(num_players=4, num_rounds=10, seed=3)
    for result in summary.rounds:
        if result.case == "none":
            assert result.caller is None or result.ended_by_draw_pile
        else:
            assert result.caller in summary.players


def test_case_b_lowest_players_score_zero() -> None:
    """§8 Case B observed in real play: lowest non-callers score 0."""
    summary = simulate_match(num_players=4, num_rounds=20, seed=11)
    case_b = [r for r in summary.rounds if r.case == "B"]
    assert case_b, "expected at least one failed Alfredo call in 20 rounds"
    for result in case_b:
        lowest = min(result.card_totals.values())
        for name, score in result.round_scores.items():
            if result.card_totals[name] == lowest and name != result.caller:
                assert score == 0


def test_case_a_caller_scores_exactly_minus_ten() -> None:
    """§8 Case A observed in real play: the caller scores −10, not −10 + total."""
    summary = simulate_match(num_players=4, num_rounds=20, seed=5)
    case_a = [r for r in summary.rounds if r.case == "A"]
    assert case_a, "expected at least one successful Alfredo call in 20 rounds"
    for result in case_a:
        assert result.round_scores[result.caller] == -10
        for name, score in result.round_scores.items():
            if name != result.caller:
                assert score == result.card_totals[name]


def test_special_abilities_never_fire_after_a_call() -> None:
    """§7: in a round where Alfredo was called, no ability resolves afterwards."""
    rng = random.Random(23)
    game = AlfredoGame(
        list(DEFAULT_NAMES[:4]),
        rng,
        GameConfig(num_players=4, num_rounds=3),
        policies=make_policies(4, rng),
    )
    game.play_match()
    rounds_with_call = {
        entry.round_number for entry in game.log.entries if entry.kind == "alfredo"
    }
    call_turn = {
        entry.round_number: entry.turn
        for entry in game.log.entries
        if entry.kind == "alfredo"
    }
    for entry in game.log.entries:
        if entry.kind == "ability" and entry.round_number in rounds_with_call:
            assert entry.turn < call_turn[entry.round_number]


def test_standing_is_sorted_lowest_first() -> None:
    """§10: the winner has the lowest cumulative score."""
    summary = simulate_match(num_players=4, num_rounds=8, seed=13)
    scores = [score for _, score in summary.standings]
    assert scores == sorted(scores)
