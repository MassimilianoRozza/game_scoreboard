"""Tests for POST /update (recording the result of one match)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from cardgame import create_app  # noqa: E402
from cardgame.config import Config  # noqa: E402
from cardgame.stats import WIN_POINTS  # noqa: E402


@pytest.fixture()
def data_file(tmp_path: Path) -> Path:
    return tmp_path / "scores.json"


@pytest.fixture()
def client(tmp_path: Path, data_file: Path) -> TestClient:
    """A client over a real app whose storage points at a temp file."""
    config = Config(
        secret_key="test-secret",
        admin_password="unused",
        data_dir=tmp_path,
        data_file=data_file,
        dev_mode=True,
    )
    return TestClient(create_app(config))


def histories(client: TestClient, data_file: Path) -> dict[str, list[float]]:
    """Follow the redirect (which renders the flashes) and read stored histories."""
    response = client.post(
        "/update",
        data={
            "player_name[]": ["Ana", "Bo", "Ci"],
            "player_points[]": ["5", "3", ""],
            "player_winner[]": ["0", "0", "1"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    return {name: entry["history"] for name, entry in raw.items()}


def post(client: TestClient, names: list[str], points: list[str], winners: list[str]):
    return client.post(
        "/update",
        data={
            "player_name[]": names,
            "player_points[]": points,
            "player_winner[]": winners,
        },
        follow_redirects=True,
    )


def test_stores_one_match_per_player(client: TestClient, data_file: Path) -> None:
    """A plain match records the entered points plus the fixed winning score."""
    assert histories(client, data_file) == {"Ana": [5.0], "Bo": [3.0], "Ci": [WIN_POINTS]}


def test_single_winner_gets_win_points(client: TestClient, data_file: Path) -> None:
    """Exactly one winner takes the fixed winning score."""
    post(client, ["Ana", "Bo"], ["4", ""], ["0", "1"])
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw["Bo"]["history"] == [WIN_POINTS]


def test_multiple_winners_score_zero(client: TestClient, data_file: Path) -> None:
    """When several players win together, each of them scores 0."""
    post(client, ["Ana", "Bo", "Ci"], ["", "", "7"], ["1", "1", "0"])
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw["Ana"]["history"] == [0.0]
    assert raw["Bo"]["history"] == [0.0]
    assert raw["Ci"]["history"] == [7.0]


def test_all_players_may_win(client: TestClient, data_file: Path) -> None:
    """Every row can be flagged as a winner at once."""
    post(client, ["Ana", "Bo"], ["", ""], ["1", "1"])
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw["Ana"]["history"] == [0.0]
    assert raw["Bo"]["history"] == [0.0]


def test_zero_points_for_loser_rejected(client: TestClient, data_file: Path) -> None:
    """Losers must score strictly more than zero."""
    response = post(client, ["Ana", "Bo", "Ci"], ["0", "5", "7"], ["0", "0", "0"])
    assert "maggiore di 0" in response.text
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw == {"Bo": {"history": [5.0]}, "Ci": {"history": [7.0]}}


def test_negative_points_for_loser_rejected(client: TestClient, data_file: Path) -> None:
    """Negative scores stay invalid for losers."""
    response = post(client, ["Ana", "Bo", "Ci"], ["-3", "5", "7"], ["0", "0", "0"])
    assert "maggiore di 0" in response.text
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw == {"Bo": {"history": [5.0]}, "Ci": {"history": [7.0]}}


def test_fractional_points_rejected(client: TestClient, data_file: Path) -> None:
    """Points must be whole numbers."""
    response = post(client, ["Ana", "Bo", "Ci"], ["4.5", "5", "7"], ["0", "0", "0"])
    assert "maggiore di 0" in response.text
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw == {"Bo": {"history": [5.0]}, "Ci": {"history": [7.0]}}


def test_match_without_winner_still_records(client: TestClient, data_file: Path) -> None:
    """A match with no flagged winner keeps the entered points."""
    post(client, ["Ana", "Bo"], ["6", "2"], ["0", "0"])
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw["Ana"]["history"] == [6.0]
    assert raw["Bo"]["history"] == [2.0]


def test_absent_player_gets_placeholder_and_means_unaffected(client: TestClient, data_file: Path) -> None:
    """Existing players not in a match get placeholder '-', means only count actual matches."""
    # Match 1: Ana and Bo play
    post(client, ["Ana", "Bo"], ["6", "2"], ["0", "0"])
    # Match 2: Bo and Ci play (Ana is absent)
    post(client, ["Bo", "Ci"], ["4", "8"], ["0", "0"])

    raw = json.loads(data_file.read_text(encoding="utf-8"))
    assert raw["Ana"]["history"] == [6.0, "-"]
    assert raw["Bo"]["history"] == [2.0, 4.0]
    assert raw["Ci"]["history"] == ["-", 8.0]

    # Check leaderboards & history view calculation
    from cardgame.storage import Storage
    from cardgame.stats import compute_global_stats, build_leaderboards, build_history_rows
    storage = Storage(data_file)
    data = storage.load()
    global_stats = compute_global_stats(data)
    # Total matches played across all: Ana: 1, Bo: 2, Ci: 1. Max matches = 2.
    # Total points: 6 + 2 + 4 + 8 = 20. Total played entries: 4. Mean = 5.0.
    assert global_stats.max_matches == 2
    assert global_stats.mean == 5.0

    leaderboards = build_leaderboards(data, global_stats)
    bo_row = next(r for r in leaderboards.raw if r.name == "Bo")
    ana_row = next(r for r in leaderboards.raw if r.name == "Ana")
    ci_row = next(r for r in leaderboards.raw if r.name == "Ci")

    assert bo_row.matches == 2
    assert bo_row.average == 3.0
    assert ana_row.matches == 1
    assert ana_row.average == 6.0
    assert ci_row.matches == 1
    assert ci_row.average == 8.0

    # History rows should have 2 global matches
    h_rows, max_m = build_history_rows(data)
    assert max_m == 2
    ana_h = next(r for r in h_rows if r.name == "Ana")
    assert ana_h.history == [6.0, "-"]
    # In chart payload, '-' is converted to None for Chart.js
    assert ana_h.to_json_dict()["history"] == [6.0, None]

