"""Run a bot-vs-bot Alfredo match from the command line.

Example::

    python -m cardgame.alfredo.simulate --players 4 --rounds 10 --seed 7
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from .bots import BotPolicy, make_policies
from .engine import AlfredoGame, GameConfig, RoundResult
from .report import render_match

#: Seat names used by the simulator, mirroring the reference implementation.
DEFAULT_NAMES: tuple[str, ...] = (
    "Milo",
    "Sofia",
    "Leo",
    "Nina",
    "Marco",
    "Ada",
    "Theo",
    "Iris",
)


#: Bounds enforced by both the CLI and the web route.
MIN_PLAYERS: int = 2
MAX_PLAYERS: int = 8
MIN_ROUNDS: int = 1
MAX_ROUNDS: int = 50

#: Bot personality families accepted by :func:`make_policies`.
STYLES: tuple[str, ...] = ("mixed", "careful", "chaotic")


@dataclass
class MatchSummary:
    """Machine readable result of a simulated match."""

    players: list[str]
    rounds: list[RoundResult]
    standings: list[tuple[str, int]]
    game: AlfredoGame
    seed: int
    style: str


def resolve_seed(seed: int | None) -> int:
    """Return ``seed``, or a fresh one so any run stays reproducible afterwards."""
    if seed is None:
        return random.SystemRandom().randrange(1, 2**31 - 1)
    return int(seed)


def simulate_match(
    num_players: int = 4,
    num_rounds: int = 10,
    seed: int | None = None,
    style: str = "mixed",
    names: list[str] | None = None,
) -> MatchSummary:
    """Play a full bot-vs-bot match and return its structured result."""
    if not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
        raise ValueError(f"Alfredo supports between {MIN_PLAYERS} and {MAX_PLAYERS} players")
    if not MIN_ROUNDS <= num_rounds <= MAX_ROUNDS:
        raise ValueError(f"A match supports between {MIN_ROUNDS} and {MAX_ROUNDS} rounds")
    if style not in STYLES:
        raise ValueError(f"Unknown bot style: {style!r}")
    player_names = names or list(DEFAULT_NAMES[:num_players])
    if len(player_names) != num_players:
        raise ValueError("Exactly one name per player is required")
    resolved_seed = resolve_seed(seed)
    rng = random.Random(resolved_seed)
    policies: list[BotPolicy] = make_policies(num_players, rng, style)
    game = AlfredoGame(
        player_names,
        rng,
        GameConfig(num_players=num_players, num_rounds=num_rounds),
        policies,
    )
    results = game.play_match()
    standings = [
        (player.name, player.cumulative_score)
        for player in sorted(game.players, key=lambda p: p.cumulative_score)
    ]
    return MatchSummary(
        players=player_names,
        rounds=results,
        standings=standings,
        game=game,
        seed=resolved_seed,
        style=style,
    )


def build_parser() -> argparse.ArgumentParser:
    """Command line arguments for the simulator."""
    parser = argparse.ArgumentParser(
        prog="cardgame.alfredo.simulate",
        description="Simulate a bot-vs-bot Alfredo match.",
    )
    parser.add_argument("--players", type=int, default=4, help="seats at the table (2-8)")
    parser.add_argument(
        "--rounds", type=int, default=10, help=f"rounds to play (1-{MAX_ROUNDS})"
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    parser.add_argument(
        "--style",
        choices=STYLES,
        default="mixed",
        help="bot personality family",
    )
    parser.add_argument("--log", action="store_true", help="also print the event log")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: simulate and print the report."""
    args = build_parser().parse_args(argv)
    try:
        summary = simulate_match(
            num_players=args.players,
            num_rounds=args.rounds,
            seed=args.seed,
            style=args.style,
        )
    except ValueError as error:
        print(str(error))
        return 2
    print(render_match(summary.game, summary.rounds))
    if args.log:
        print("\nEvent log")
        for entry in summary.game.log.entries:
            print(f"  r{entry.round_number} t{entry.turn} [{entry.kind}] {entry.message}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
