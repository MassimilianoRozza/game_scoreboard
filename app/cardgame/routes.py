"""HTTP routes for the card game tracker (FastAPI)."""

from __future__ import annotations

import hmac
from typing import Any, Final

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from .config import Config
from .models import PLACEHOLDER_ABSENT, PlayerStats
from .stats import (
    PENALTY_POINTS,
    WIN_POINTS,
    build_history_rows,
    build_leaderboards,
    compute_global_stats,
)
from .storage import Storage

#: Session key holding queued flash messages as (category, message) pairs.
FLASH_SESSION_KEY = "flashes"

#: Minimum number of players required to register a match (mirrors match-form.js).
MIN_PLAYERS_PER_MATCH = 2

#: Crown states a match row can carry (mirrors match-form.js).
#: - gold: the player who called Alfredo and won -> WIN_POINTS, points not applicable.
#: - silver: 0 points (or user-entered points when two golds collided).
#: - black: the failed Alfredo call -> editable penalty points, required.
CROWN_NONE: Final[str] = "none"
CROWN_GOLD: Final[str] = "gold"
CROWN_SILVER: Final[str] = "silver"
CROWN_BLACK: Final[str] = "black"
VALID_CROWNS: Final[frozenset[str]] = frozenset(
    {CROWN_NONE, CROWN_GOLD, CROWN_SILVER, CROWN_BLACK}
)


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
            "app_version": config.app_version,
            "github_url": config.github_url,
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
                "penalty_points": PENALTY_POINTS,
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
        crowns_list = _getlist(form, "player_crown[]")
        # Submissions without the crown field (older clients) count every row
        # as no crown instead of dropping the whole match.
        crowns_list += [CROWN_NONE] * (len(names) - len(crowns_list))

        def valid_points(pts_str: str) -> float | None:
            """Whole number of points strictly greater than zero, or None."""
            try:
                pts = float(pts_str)
            except ValueError:
                return None
            if pts <= 0 or not pts.is_integer():
                return None
            return pts

        # First pass: validate the entries. Crown states are counted here and
        # cross-checked against the match rules in a second pass.
        scored: list[tuple[str, float]] = []
        gold_count = 0
        black_count = 0
        seen: set[str] = set()
        duplicates: list[str] = []
        invalid: list[str] = []
        for name, pts_str, crown in zip(names, points_list, crowns_list):
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

            if crown not in VALID_CROWNS:
                crown = CROWN_NONE

            if crown == CROWN_GOLD:
                # The player who called Alfredo and won: fixed winning score.
                gold_count += 1
                scored.append((name, WIN_POINTS))
                continue

            if crown == CROWN_SILVER:
                # Double-click silver scores a fixed 0 (field hidden); a silver
                # born from a gold collision carries user-entered points.
                if pts_str == "":
                    scored.append((name, 0.0))
                    continue
                pts = valid_points(pts_str)
                if pts is None:
                    invalid.append(name)
                    continue
                scored.append((name, pts))
                continue

            if crown == CROWN_BLACK:
                # The failed Alfredo call: editable penalty points.
                pts = valid_points(pts_str)
                if pts is None:
                    invalid.append(name)
                    continue
                black_count += 1
                scored.append((name, pts))
                continue

            # No crown: plain loser, points required (mirrors the min="1"
            # step="1" input in index.html).
            pts = valid_points(pts_str)
            if pts is None:
                invalid.append(name)
                continue
            scored.append((name, pts))

        # Match-level crown rules (mirrors the client-side submit gate in
        # match-form.js):
        # - the gold crown (caller won) excludes the black crown (failed call);
        # - otherwise exactly one black crown must be assigned.
        crown_error: str | None = None
        if gold_count > 1:
            crown_error = (
                "Pi\u00f9 corone oro non sono valide: se vincono pi\u00f9 giocatori "
                "usate le corone argento."
            )
        elif gold_count == 1 and black_count > 0:
            crown_error = (
                "La corona oro (chi ha chiamato Alfredo e vinto) esclude la corona "
                "nera (chiamata fallita)."
            )
        elif gold_count == 0 and black_count != 1:
            crown_error = (
                "Serve esattamente una corona nera (la chiamata Alfredo fallita), "
                "a meno che non ci sia un solo vincitore con la corona oro."
            )

        updated_count = len(scored)

        if updated_count >= MIN_PLAYERS_PER_MATCH and crown_error is None:
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
        elif updated_count < MIN_PLAYERS_PER_MATCH:
            flash(
                request,
                f"Servono almeno {MIN_PLAYERS_PER_MATCH} giocatori per registrare una partita.",
                "warning",
            )
        else:
            flash(request, crown_error or "Corone non valide.", "warning")

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
