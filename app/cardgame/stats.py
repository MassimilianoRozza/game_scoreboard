"""Pure statistics: Bayesian average, leaderboards and history rows."""

from __future__ import annotations

from .models import GlobalStats, HistoryRow, Leaderboards, PlayerRow, ScoreData

#: Fraction of the most prolific player's match count used as Bayesian weight C.
C_FRACTION = 0.3

#: Points recorded for the player who wins a match (lower is better).
WIN_POINTS: float = -10.0


def bayesian_average(total_points: float, matches: int, c: float, mean: float) -> float:
    """Bayesian average: ``(C * M + total_points) / (C + matches)``."""
    if (c + matches) > 0:
        return (c * mean + total_points) / (c + matches)
    return mean


def compute_global_stats(data: ScoreData) -> GlobalStats:
    """Global mean M over every recorded match, and the regularization weight C."""
    all_points: list[float] = []
    max_matches = 0

    for stats in data.values():
        history = stats.history
        if len(history) > max_matches:
            max_matches = len(history)
        all_points.extend(history)

    mean = (sum(all_points) / len(all_points)) if all_points else 0.0
    c = max(C_FRACTION * max_matches, 1.0) if max_matches > 0 else 1.0
    return GlobalStats(mean=mean, max_matches=max_matches, c=c)


def build_leaderboards(data: ScoreData, stats: GlobalStats) -> Leaderboards:
    """Build the Bayesian and raw leaderboards, sorted ascending (lower = better)."""
    bayesian_leaderboard: list[PlayerRow] = []
    raw_leaderboard: list[PlayerRow] = []

    for player, player_stats in data.items():
        history = player_stats.history
        matches = len(history)
        total_points = sum(history)
        raw_avg = (total_points / matches) if matches > 0 else 0.0
        bayes_avg = bayesian_average(total_points, matches, stats.c, stats.mean)

        bayesian_leaderboard.append(
            PlayerRow(
                name=player,
                matches=matches,
                total_points=round(total_points, 2),
                average=round(raw_avg, 2),
                bayesian_average=round(bayes_avg, 2),
            )
        )
        raw_leaderboard.append(
            PlayerRow(
                name=player,
                matches=matches,
                total_points=round(total_points, 2),
                average=round(raw_avg, 2),
                bayesian_average=round(bayes_avg, 2),
            )
        )

    bayesian_leaderboard.sort(key=lambda row: row.bayesian_average)
    raw_leaderboard.sort(key=lambda row: row.average)

    for index, row in enumerate(bayesian_leaderboard):
        row.rank = str(index + 1)
    for index, row in enumerate(raw_leaderboard):
        row.rank = str(index + 1)

    assign_badges(bayesian_leaderboard)
    return Leaderboards(bayesian=bayesian_leaderboard, raw=raw_leaderboard)


def assign_badges(rows: list[PlayerRow]) -> None:
    """Crown for #1, skull for the last player (only when there is more than one)."""
    if not rows:
        return
    rows[0].badge = "👑"
    rows[0].badge_title = "Leader in classifica (Miglior media bayesiana)"
    if len(rows) > 1:
        last = rows[-1]
        last.badge = "💀"
        last.badge_title = "Ultimo in classifica (Peggior media bayesiana)"


def build_history_rows(data: ScoreData) -> tuple[list[HistoryRow], int]:
    """Per-player history rows sorted by raw average, plus the max match count."""
    leaderboard: list[HistoryRow] = []
    max_matches = 0

    for player, player_stats in data.items():
        history = player_stats.history
        if len(history) > max_matches:
            max_matches = len(history)

        matches = len(history)
        total_points = sum(history)
        avg = (total_points / matches) if matches > 0 else 0.0
        leaderboard.append(HistoryRow(name=player, average=round(avg, 2), history=list(history)))

    leaderboard.sort(key=lambda row: row.average)
    return leaderboard, max_matches
