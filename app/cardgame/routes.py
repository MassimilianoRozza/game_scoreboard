"""HTTP routes for the card game tracker (FastAPI)."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from .config import Config
from .models import PLACEHOLDER_ABSENT, PlayerStats
from .stats import WIN_POINTS, build_history_rows, build_leaderboards, compute_global_stats
from .storage import Storage

#: Session key holding queued flash messages as (category, message) pairs.
FLASH_SESSION_KEY = "flashes"

#: Minimum number of players required to register a match (mirrors match-form.js).
MIN_PLAYERS_PER_MATCH = 2


def _getlist(form: FormData, key: str) -> list[str]:
    """Return the form values for ``key`` as strings, ignoring uploaded files."""
    return [value for value in form.getlist(key) if isinstance(value, str)]


def create_router(
    storage: Storage, config: Config, templates: Jinja2Templates
) -> APIRouter:
    """Build the application router, closing over storage and config."""
    router = APIRouter()

    def flash(request: Request, message: str, category: str = "message") -> None:
        """Queue a flash message for the next rendered page (session-backed)."""
        pending = request.session.get(FLASH_SESSION_KEY, [])
        pending.append((category, message))
        request.session[FLASH_SESSION_KEY] = pending

    def take_flashes(request: Request) -> list[tuple[str, str]]:
        """Pop queued flash messages as (category, message) tuples."""
        flashes = request.session.pop(FLASH_SESSION_KEY, [])
        return [(str(category), str(message)) for category, message in flashes]

    def redirect_to_index(request: Request) -> RedirectResponse:
        """Redirect back to the leaderboard after a POST (303 => follow with GET)."""
        index_url = request.app.url_path_for("main.index")
        return RedirectResponse(url=index_url, status_code=303)

    def base_context(request: Request) -> dict[str, Any]:
        """Context shared by every page.

        ``url_for`` is bound to ``url_path_for`` so templates emit relative paths
        instead of host-absolute URLs (Starlette's default).
        """
        return {
            "url_for": request.app.url_path_for,
            "flashes": take_flashes(request),
        }

    def is_authorized(password: str) -> bool:
        """In dev mode the admin password check is bypassed."""
        if config.dev_mode:
            return True
        return hmac.compare_digest(password, config.admin_password)

    @router.get("/", name="main.index")
    def index(request: Request) -> Any:
        data = storage.load()
        global_stats = compute_global_stats(data)
        leaderboards = build_leaderboards(data, global_stats)

        # Names ordered by official (Bayesian) rank, used by the player dropdown.
        known_players: list[str] = [row.name for row in leaderboards.bayesian]

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                **base_context(request),
                "bayesian_leaderboard": leaderboards.bayesian,
                "raw_leaderboard": leaderboards.raw,
                "known_players": known_players,
                "global_mean": round(global_stats.mean, 2),
                "C": round(global_stats.c, 2),
                "max_matches": global_stats.max_matches,
                "active_tab": "bayesian",
                "dev_mode": config.dev_mode,
                "require_password": not config.dev_mode,
                "win_points": WIN_POINTS,
            },
        )

    @router.get("/history", name="main.history_view")
    def history_view(request: Request) -> Any:
        data = storage.load()
        leaderboard, max_matches = build_history_rows(data)
        chart_rows: list[dict[str, object]] = [row.to_json_dict() for row in leaderboard]
        return templates.TemplateResponse(
            request,
            "history.html",
            {
                **base_context(request),
                "leaderboard": leaderboard,
                "chart_rows": chart_rows,
                "max_matches": max_matches,
                "active_tab": "history",
            },
        )

    @router.post("/update", name="main.update_scores")
    async def update_scores(request: Request) -> RedirectResponse:
        form = await request.form()
        password = str(form.get("password", ""))
        if not is_authorized(password):
            flash(request, "Password non corretta!", "danger")
            return redirect_to_index(request)

        data = storage.load()
        names = _getlist(form, "player_name[]")
        points_list = _getlist(form, "player_points[]")
        winners_list = _getlist(form, "player_winner[]")

        # First pass: validate the entries. A winner's score depends on how many
        # winners the match has, so it is only resolved in the second pass.
        scored: list[tuple[str, float]] = []
        winners: list[str] = []
        seen: set[str] = set()
        duplicates: list[str] = []
        invalid: list[str] = []
        for name, pts_str, winner_flag in zip(names, points_list, winners_list):
            name = name.strip()
            if not name:
                continue

            # A player can only play one match per submission (case-insensitive,
            # mirroring the client-side duplicate guard).
            key = name.lower()
            if key in seen:
                duplicates.append(name)
                continue
            seen.add(key)

            if winner_flag == "1":
                winners.append(name)
                continue

            try:
                pts = float(pts_str)
            except ValueError:
                invalid.append(name)
                continue
            # Losers must enter a whole number of points strictly greater than
            # zero (mirrors the min="1" step="1" input in index.html).
            if pts <= 0 or not pts.is_integer():
                invalid.append(name)
                continue
            scored.append((name, pts))

        # A lone winner takes the fixed winning score; when several players win
        # together nobody gains, so each of them scores 0.
        win_pts = WIN_POINTS if len(winners) == 1 else 0.0
        scored.extend((name, win_pts) for name in winners)

        updated_count = len(scored)

        if updated_count >= MIN_PLAYERS_PER_MATCH:
            # Determine the current match index across all existing players before adding this match.
            # Any player who is already registered but did not participate in this match gets the placeholder.
            active_names = {name for name, _ in scored}
            max_rounds = max((len(stats.history) for stats in data.values()), default=0)

            # Bring existing players up to date if they had missing entries, then append scores/placeholders
            for existing_name, stats in data.items():
                if len(stats.history) < max_rounds:
                    stats.history.extend([PLACEHOLDER_ABSENT] * (max_rounds - len(stats.history)))

            # Now record the new match for all participating players
            for name, pts in scored:
                stats = data.get(name)
                if stats is None:
                    # New player: backfill past matches with placeholder so timeline aligns
                    stats = PlayerStats(history=[PLACEHOLDER_ABSENT] * max_rounds)
                    data[name] = stats
                stats.history.append(pts)

            # For every other player already in the database who didn't play in this match, add placeholder
            for existing_name, stats in data.items():
                if existing_name not in active_names:
                    stats.history.append(PLACEHOLDER_ABSENT)

            storage.save(data)
            flash(
                request,
                f"Punteggi aggiornati con successo per {updated_count} giocatore/i!",
                "success",
            )
        else:
            flash(
                request,
                f"Servono almeno {MIN_PLAYERS_PER_MATCH} giocatori per registrare una partita.",
                "warning",
            )

        if duplicates:
            flash(
                request,
                "Giocatore duplicato nella stessa partita (ignorato): "
                + ", ".join(dict.fromkeys(duplicates)),
                "warning",
            )
        if invalid:
            flash(
                request,
                "Punti non validi (i perdenti devono avere un numero intero di "
                "punti maggiore di 0): "
                + ", ".join(dict.fromkeys(invalid)),
                "warning",
            )

        return redirect_to_index(request)

    return router
