"""JSON persistence for player scores, with validation and atomic writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import PlayerStats, ScoreData


def _as_float(value: object) -> float | None:
    """Return ``value`` as a float, rejecting bools and non-numeric types."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_history(entry: dict[str, object]) -> list[float]:
    """Extract a valid ``history`` list from one raw JSON player entry."""
    raw_history = entry.get("history")
    if isinstance(raw_history, list):
        history: list[float] = []
        for item in raw_history:
            points = _as_float(item)
            if points is not None:
                history.append(points)
        return history

    # Legacy shape: {"matches": int, "total_points": float} -> synthetic history.
    matches = _as_float(entry.get("matches"))
    total_points = _as_float(entry.get("total_points"))
    if matches is not None and total_points is not None and matches > 0 and total_points != 0:
        avg_val = round(total_points / matches, 2)
        return [avg_val] * int(matches)
    return []


class Storage:
    """Reads and writes ``scores.json`` for one data file."""

    def __init__(self, data_file: Path) -> None:
        self._data_file = data_file

    def load(self) -> ScoreData:
        """Load the score book; missing or corrupt files yield an empty book."""
        if not self._data_file.exists():
            return {}
        try:
            with self._data_file.open("r", encoding="utf-8") as f:
                raw: Any = json.load(f)
        except json.JSONDecodeError:
            return {}

        if not isinstance(raw, dict):
            return {}

        data: ScoreData = {}
        for player, entry in raw.items():
            if not isinstance(player, str) or not isinstance(entry, dict):
                continue
            data[player] = PlayerStats(history=_normalize_history(entry))
        return data

    def save(self, data: ScoreData) -> None:
        """Persist the score book atomically (temp file + rename)."""
        payload: dict[str, dict[str, object]] = {
            player: stats.to_json_dict() for player, stats in data.items()
        }
        tmp_file = self._data_file.with_name(f"{self._data_file.name}.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, self._data_file)
