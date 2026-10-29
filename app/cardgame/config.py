"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .const import DEV

#: Absolute path shared by the production container and the dev container.
DATA_DIR: Final[Path] = Path("/app/data")
DATA_FILE_NAME: Final[str] = "scores.json"

DEFAULT_SECRET_KEY: Final[str] = "super-secret-default-key-change-this"
DEFAULT_ADMIN_PASSWORD: Final[str] = "changeme123"

#: Public GitHub repository URL shown in the UI footer.
GITHUB_URL: Final[str] = "https://github.com/MassimilianoRozza/game_scoreboard"


def _detect_app_version() -> str:
    """Return the current git tag (e.g. ``v0.1.1``), or ``"dev"`` as fallback."""
    try:
        version = subprocess.check_output(
            ["git", "describe", "--tags", "--always"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return version if version else "dev"
    except Exception:
        return "dev"


@dataclass(frozen=True)
class Config:
    """Immutable application settings."""

    secret_key: str
    admin_password: str
    data_dir: Path
    data_file: Path
    dev_mode: bool
    app_version: str = field(default_factory=_detect_app_version)
    github_url: str = GITHUB_URL

    @classmethod
    def from_env(cls) -> "Config":
        """Build the configuration from ``SECRET_KEY``, ``ADMIN_PASSWORD`` and ``DEV``."""
        data_dir: Path = DATA_DIR
        return cls(
            secret_key=os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY),
            admin_password=os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD),
            data_dir=data_dir,
            data_file=data_dir / DATA_FILE_NAME,
            dev_mode=DEV,
        )
