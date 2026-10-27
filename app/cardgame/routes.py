"""HTTP routes for the card game tracker (FastAPI)."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from .config import Config
from .models import PlayerStats
from .stats import WIN_POINTS, build_history_rows, build_leaderboards, compute_global_stats
from .storage import Storage

#: Session key holding queued flash messages as (category, message) pairs.
FLASH_SESSION_KEY = "flashes"


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

        updated_count = 0
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
                # The winner always gets the fixed winning score.
                pts = WIN_POINTS
            else:
                try:
                    pts = float(pts_str)
                except ValueError:
                    invalid.append(name)
                    continue
                if pts < 0:
                    # Only the winner may have negative points.
                    invalid.append(name)
                    continue

            stats = data.get(name)
            if stats is None:
                stats = PlayerStats()
                data[name] = stats
            stats.history.append(pts)
            updated_count += 1

        if updated_count > 0:
            storage.save(data)
            flash(
                request,
                f"Punteggi aggiornati con successo per {updated_count} giocatore/i!",
                "success",
            )
        else:
            flash(request, "Nessun dato valido inserito.", "warning")

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
                "Punti non validi (i perdenti devono avere almeno 0 punti): "
                + ", ".join(dict.fromkeys(invalid)),
                "warning",
            )

        return redirect_to_index(request)

    return router
