"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .const import DEV

#: Absolute path shared by the production container and the dev container.
DATA_DIR: Final[Path] = Path("/app/data")
DATA_FILE_NAME: Final[str] = "scores.json"

DEFAULT_SECRET_KEY: Final[str] = "super-secret-default-key-change-this"
DEFAULT_ADMIN_PASSWORD: Final[str] = "changeme123"


@dataclass(frozen=True)
class Config:
    """Immutable application settings."""

    secret_key: str
    admin_password: str
    data_dir: Path
    data_file: Path
    dev_mode: bool

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
