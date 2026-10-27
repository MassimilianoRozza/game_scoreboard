"""Human readable rendering of a simulated match."""

from __future__ import annotations

from .engine import AlfredoGame, RoundResult


def render_round(result: RoundResult, players: list[str]) -> str:
    """One round as a small fixed-width table."""
    lines = [
        f"Round {result.round_number}  "
        f"(caller: {result.caller or 'none'}, case {result.case.upper()}, "
        f"{result.turns} turns)",
        f"  {'Player':<12}{'Total':>7}{'Round':>8}{'Cumulative':>12}",
    ]
    for name in players:
        lines.append(
            f"  {name:<12}{result.card_totals[name]:>7}"
            f"{result.round_scores[name]:>8}{result.cumulative[name]:>12}"
        )
    lines.append(f"  {result.message}")
    if result.ended_by_draw_pile:
        lines.append("  NOTE: the round ended because the draw pile ran out.")
    return "\n".join(lines)


def render_standings(game: AlfredoGame) -> str:
    """Final standings, lowest cumulative score first (ruleset §10)."""
    ordered = sorted(game.players, key=lambda player: player.cumulative_score)
    lines = ["", "Final standings (lowest wins)"]
    for rank, player in enumerate(ordered, start=1):
        lines.append(f"  {rank}. {player.name:<12}{player.cumulative_score:>6}")
    return "\n".join(lines)


def render_match(game: AlfredoGame, results: list[RoundResult]) -> str:
    """Full report: every round plus the standings."""
    names = [player.name for player in game.players]
    blocks = [render_round(result, names) for result in results]
    return "\n\n".join(blocks + [render_standings(game)])
