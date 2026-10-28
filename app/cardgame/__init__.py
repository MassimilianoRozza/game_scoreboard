"""Card game tracker application package (FastAPI)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import Config
from .alfredo_routes import create_alfredo_router
from .routes import create_router
from .storage import Storage

__all__ = ["create_app"]

_PACKAGE_DIR: Path = Path(__file__).resolve().parent


def create_app(config: Config | None = None) -> FastAPI:
    """Application factory: config -> storage -> templates/static -> router."""
    app_config = config if config is not None else Config.from_env()
    app_config.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Card Game Tracker", docs_url=None, redoc_url=None)

    # Signed-cookie sessions back the flash messages.
    app.add_middleware(SessionMiddleware, secret_key=app_config.secret_key)

    templates = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(_PACKAGE_DIR / "static")), name="static")

    app.include_router(create_router(Storage(app_config.data_file), app_config, templates))
    app.include_router(create_alfredo_router(templates))
    return app
