"""HTTP routes for the card game tracker."""

from __future__ import annotations

import hmac

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from .config import Config
from .models import PlayerStats
from .stats import build_history_rows, build_leaderboards, compute_global_stats
from .storage import Storage


def create_blueprint(storage: Storage, config: Config) -> Blueprint:
    """Build the application blueprint, closing over storage and config."""
    blueprint = Blueprint("main", __name__)

    def is_authorized(password: str) -> bool:
        """In dev mode the admin password check is bypassed."""
        if config.dev_mode:
            return True
        return hmac.compare_digest(password, config.admin_password)

    @blueprint.route("/")
    def index() -> str:
        data = storage.load()
        global_stats = compute_global_stats(data)
        leaderboards = build_leaderboards(data, global_stats)

        # Names ordered by official (Bayesian) rank, used by the quick-pick chips.
        known_players: list[str] = [row.name for row in leaderboards.bayesian]

        return render_template(
            "index.html",
            bayesian_leaderboard=leaderboards.bayesian,
            raw_leaderboard=leaderboards.raw,
            known_players=known_players,
            global_mean=round(global_stats.mean, 2),
            C=round(global_stats.c, 2),
            max_matches=global_stats.max_matches,
            active_tab="bayesian",
            dev_mode=config.dev_mode,
            require_password=not config.dev_mode,
        )

    @blueprint.route("/history")
    def history_view() -> str:
        data = storage.load()
        leaderboard, max_matches = build_history_rows(data)
        chart_rows: list[dict[str, object]] = [row.to_json_dict() for row in leaderboard]
        return render_template(
            "history.html",
            leaderboard=leaderboard,
            chart_rows=chart_rows,
            max_matches=max_matches,
            active_tab="history",
        )

    @blueprint.route("/update", methods=["POST"])
    def update_scores() -> Response:
        password = request.form.get("password", "")
        if not is_authorized(password):
            flash("Password non corretta!", "danger")
            return redirect(url_for("main.index"))

        data = storage.load()
        names = request.form.getlist("player_name[]")
        points_list = request.form.getlist("player_points[]")

        updated_count = 0
        seen: set[str] = set()
        duplicates: list[str] = []
        for name, pts_str in zip(names, points_list):
            name = name.strip()
            if not name:
                continue
            try:
                pts = float(pts_str)
            except ValueError:
                continue

            # A player can only play one match per submission (case-insensitive,
            # mirroring the client-side duplicate guard).
            key = name.lower()
            if key in seen:
                duplicates.append(name)
                continue
            seen.add(key)

            stats = data.get(name)
            if stats is None:
                stats = PlayerStats()
                data[name] = stats
            stats.history.append(pts)
            updated_count += 1

        if updated_count > 0:
            storage.save(data)
            flash(f"Punteggi aggiornati con successo per {updated_count} giocatore/i!", "success")
        else:
            flash("Nessun dato valido inserito.", "warning")

        if duplicates:
            flash(
                "Giocatore duplicato nella stessa partita (ignorato): "
                + ", ".join(dict.fromkeys(duplicates)),
                "warning",
            )

        return redirect(url_for("main.index"))

    return blueprint
