"""Entrypoint for the Card Game Score Tracker Flask app."""

from __future__ import annotations

from cardgame import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
