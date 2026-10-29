"""HTTP routes for the Alfredo bot-vs-bot simulator page.

Kept separate from ``routes.py`` because the Alfredo engine has no dependency
on the score storage: the page simulates a match and renders it, it never
writes to ``scores.json``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .alfredo.simulate import MatchSummary
    from .config import Config

#: Defaults shown on a fresh page load.
DEFAULT_PLAYERS = 4
DEFAULT_ROUNDS = 5
DEFAULT_STYLE = "mixed"


def _parse_int(raw: str | None, default: int | None) -> tuple[int | None, str | None]:
    """Parse an optional integer field, returning ``(value, error)``."""
    if raw is None or raw.strip() == "":
        return default, None
    try:
        return int(raw.strip()), None
    except ValueError:
        return None, f"Value '{raw}' is not a whole number."


def build_match_context(summary: MatchSummary) -> dict[str, Any]:
    """Turn a :class:`MatchSummary` into template friendly rows."""
    rounds: list[dict[str, Any]] = []
    for result in summary.rounds:
        rounds.append(
            {
                "number": result.round_number,
                "caller": result.caller,
                "case": result.case,
                "message": result.message,
                "turns": result.turns,
                "ended_by_draw_pile": result.ended_by_draw_pile,
                "rows": [
                    {
                        "name": name,
                        "card_total": result.card_totals[name],
                        "round_score": result.round_scores[name],
                        "cumulative": result.cumulative[name],
                    }
                    for name in summary.players
                ],
            }
        )
    standings = [
        {"rank": rank, "name": name, "score": score}
        for rank, (name, score) in enumerate(summary.standings, start=1)
    ]
    log = [
        {
            "round_number": entry.round_number,
            "turn": entry.turn,
            "kind": entry.kind,
            "message": entry.message,
        }
        for entry in summary.game.log.entries
    ]
    return {
        "players": summary.players,
        "rounds": rounds,
        "standings": standings,
        "seed": summary.seed,
        "style": summary.style,
        "deck_count": summary.game.deck_count,
        "log": log,
    }


def create_alfredo_router(templates: Jinja2Templates, config: "Config | None" = None) -> APIRouter:
    """Build the ``/alfredo`` router."""
    router = APIRouter()

    @router.get("/alfredo", name="alfredo.view")
    def alfredo_view(request: Request) -> Any:
        """Simulate a bot-vs-bot match and render it.

        The match parameters live in the query string, so any result can be
        reproduced or shared by its URL.
        """
        # Imported lazily so that ``python -m cardgame.alfredo.simulate`` stays
        # warning-free: importing this module must not pre-load the simulator.
        from .alfredo import simulate as simulator

        errors: list[str] = []
        params = request.query_params

        players, error = _parse_int(params.get("players"), DEFAULT_PLAYERS)
        if error:
            errors.append(error)
            players = DEFAULT_PLAYERS
        rounds, error = _parse_int(params.get("rounds"), DEFAULT_ROUNDS)
        if error:
            errors.append(error)
            rounds = DEFAULT_ROUNDS
        seed_raw = params.get("seed")
        seed, error = _parse_int(seed_raw, None)
        if error:
            errors.append(error)
        style = params.get("style") or DEFAULT_STYLE
        if style not in simulator.STYLES:
            errors.append(f"Unknown bot style '{style}'.")
            style = DEFAULT_STYLE

        form = {
            "players": players,
            "rounds": rounds,
            "style": style,
            "seed": seed if seed is not None else (seed_raw or ""),
        }

        match: dict[str, Any] | None = None
        if not errors:
            try:
                summary = simulator.simulate_match(
                    num_players=players or DEFAULT_PLAYERS,
                    num_rounds=rounds or DEFAULT_ROUNDS,
                    seed=seed,
                    style=style,
                )
            except ValueError as validation_error:
                errors.append(str(validation_error))
            else:
                match = build_match_context(summary)
                # Reflect the seed actually used so the permalink replays exactly.
                form["seed"] = summary.seed

        return templates.TemplateResponse(
            request,
            "alfredo.html",
            {
                "url_for": request.app.url_path_for,
                "active_tab": "alfredo",
                "match": match,
                "form": form,
                "errors": errors,
                "styles": simulator.STYLES,
                "min_players": simulator.MIN_PLAYERS,
                "max_players": simulator.MAX_PLAYERS,
                "min_rounds": simulator.MIN_ROUNDS,
                "max_rounds": simulator.MAX_ROUNDS,
                "app_version": config.app_version if config else "dev",
                "github_url": config.github_url if config else "",
            },
        )

    return router
