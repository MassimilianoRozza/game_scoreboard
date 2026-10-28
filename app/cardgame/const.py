"""Process-wide constants read from the environment."""

from __future__ import annotations

import os
from typing import Final

#: Values of ``DEV`` that are considered truthy.
TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})

#: True when running in development mode: the admin password check is bypassed
#: and the server auto-reloads on code changes.
DEV: Final[bool] = os.environ.get("DEV", "").strip().lower() in TRUE_VALUES
