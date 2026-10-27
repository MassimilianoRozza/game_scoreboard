"""Card game tracker application package."""

from __future__ import annotations

from flask import Flask

from .config import Config
from .routes import create_blueprint
from .storage import Storage

__all__ = ["create_app"]


def create_app(config: Config | None = None) -> Flask:
    """Application factory: config -> storage -> blueprint."""
    app_config = config if config is not None else Config.from_env()
    app_config.data_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.secret_key = app_config.secret_key
    app.register_blueprint(create_blueprint(Storage(app_config.data_file), app_config))
    return app
