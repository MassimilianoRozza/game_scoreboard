"""Typed domain model shared by storage, stats and routes."""

from __future__ import annotations

from dataclasses import dataclass, field

#: In-memory representation of ``scores.json``: player name -> stats.
ScoreData = dict[str, "PlayerStats"]

#: Placeholder value for an existing player who did not play in a match.
PLACEHOLDER_ABSENT = "-"


@dataclass
class PlayerStats:
    """Persisted state of a single player: the ordered list of match scores."""

    history: list[float | str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, object]:
        """Serialise back to the on-disk JSON shape."""
        return {"history": list(self.history)}


@dataclass
class PlayerRow:
    """A rendered row of one of the two leaderboard tables."""

    name: str
    matches: int
    total_points: float
    average: float
    bayesian_average: float
    rank: str = ""
    badge: str = ""
    badge_title: str = ""


@dataclass
class HistoryRow:
    """A rendered row of the match-by-match history table."""

    name: str
    average: float
    history: list[float | str]

    def to_json_dict(self) -> dict[str, object]:
        """Serialise the row for the Chart.js payload."""
        return {
            "name": self.name,
            "history": [None if item == PLACEHOLDER_ABSENT else item for item in self.history],
        }


@dataclass(frozen=True)
class GlobalStats:
    """Aggregate statistics used by the Bayesian average."""

    mean: float
    max_matches: int
    c: float


@dataclass(frozen=True)
class Leaderboards:
    """The two leaderboards rendered on the home page."""

    bayesian: list[PlayerRow]
    raw: list[PlayerRow]
