"""Entrypoint for the Card Game Score Tracker (FastAPI + uvicorn)."""

from __future__ import annotations
import uvicorn
from cardgame import create_app
from cardgame.const import DEV

app = create_app()

if __name__ == "__main__":
    # DEV=true enables uvicorn's auto-reloader on code changes.
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=DEV)
