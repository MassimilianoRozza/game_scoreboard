"""Tests for POST /update (recording the result of one match).

Crown rules under test (mirrors match-form.js):
- gold: the player who called Alfredo and won -> WIN_POINTS, points ignored;
- silver: 0 points when the field is empty, user-entered points after a gold
  collision;
- black: the failed Alfredo call -> editable whole points greater than zero;
- a match needs exactly one black crown, except when exactly one gold is
  assigned (then no black is allowed).
"""

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


def stored(data_file: Path) -> dict[str, list[float]]:
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    return {name: entry["history"] for name, entry in raw.items()}


def histories(client: TestClient, data_file: Path) -> dict[str, list[float]]:
    """Post a canonical valid match (one gold winner + losers) and read histories."""
    response = post(client, ["Ana", "Bo", "Ci"], ["5", "3", ""], ["none", "none", "gold"])
    assert response.status_code == 200
    return stored(data_file)


def post(
    client: TestClient,
    names: list[str],
    points: list[str],
    crowns: list[str],
):
    return client.post(
        "/update",
        data={
            "player_name[]": names,
            "player_points[]": points,
            "player_crown[]": crowns,
        },
        follow_redirects=True,
    )


def test_stores_one_match_per_player(client: TestClient, data_file: Path) -> None:
    """A plain match records the entered points plus the fixed winning score."""
    assert histories(client, data_file) == {"Ana": [5.0], "Bo": [3.0], "Ci": [WIN_POINTS]}


def test_single_gold_gets_win_points(client: TestClient, data_file: Path) -> None:
    """Exactly one gold crown takes the fixed winning score."""
    post(client, ["Ana", "Bo"], ["4", ""], ["none", "gold"])
    assert stored(data_file)["Bo"] == [WIN_POINTS]


def test_gold_ignores_entered_points(client: TestClient, data_file: Path) -> None:
    """A gold row's points field is not applicable: the value is ignored."""
    post(client, ["Ana", "Bo"], ["4", "99"], ["none", "gold"])
    assert stored(data_file)["Bo"] == [WIN_POINTS]


def test_silver_without_points_scores_zero(client: TestClient, data_file: Path) -> None:
    """A double-click silver (empty field) records a fixed 0."""
    post(client, ["Ana", "Bo", "Ci"], ["", "7", "10"], ["silver", "none", "black"])
    assert stored(data_file) == {"Ana": [0.0], "Bo": [7.0], "Ci": [10.0]}


def test_silver_with_points_records_them(client: TestClient, data_file: Path) -> None:
    """A collision silver carries user-entered points (like a loser)."""
    post(client, ["Ana", "Bo", "Ci"], ["3", "7", "10"], ["silver", "silver", "black"])
    assert stored(data_file) == {"Ana": [3.0], "Bo": [7.0], "Ci": [10.0]}


def test_silver_with_invalid_points_rejected(client: TestClient, data_file: Path) -> None:
    """Collision silvers must carry whole points greater than zero."""
    response = post(client, ["Ana", "Bo", "Ci"], ["0", "7", "10"], ["silver", "none", "black"])
    assert "maggiore di 0" in response.text
    assert stored(data_file) == {"Bo": [7.0], "Ci": [10.0]}


def test_black_crown_records_penalty(client: TestClient, data_file: Path) -> None:
    """The black crown records its editable penalty points."""
    post(client, ["Ana", "Bo", "Ci"], ["15", "5", "7"], ["black", "none", "none"])
    assert stored(data_file) == {"Ana": [15.0], "Bo": [5.0], "Ci": [7.0]}


def test_black_without_points_rejected(client: TestClient, data_file: Path) -> None:
    """The black crown needs explicit points: the +10 default is client-side."""
    response = post(client, ["Ana", "Bo"], ["", "5"], ["black", "none"])
    assert "maggiore di 0" in response.text
    assert not data_file.exists()


def test_black_with_invalid_points_rejected(client: TestClient, data_file: Path) -> None:
    """Black crown points must be whole and positive.

    The invalid row drops the only black crown, so the match-level invariant
    also fails and nothing is recorded.
    """
    response = post(client, ["Ana", "Bo", "Ci"], ["-3", "5", "7"], ["black", "none", "none"])
    assert "maggiore di 0" in response.text
    assert "corona nera" in response.text
    assert not data_file.exists()


# ------------------------------------------------------- match-level invariants


def test_two_golds_rejected(client: TestClient, data_file: Path) -> None:
    """Two gold crowns are invalid: the client flips them to silver instead."""
    response = post(client, ["Ana", "Bo", "Ci"], ["", "", "7"], ["gold", "gold", "none"])
    assert "corone oro" in response.text
    assert not data_file.exists()


def test_gold_excludes_black(client: TestClient, data_file: Path) -> None:
    """The caller won (gold), so a failed-call penalty (black) cannot coexist."""
    response = post(client, ["Ana", "Bo"], ["", "10"], ["gold", "black"])
    assert "esclude" in response.text
    assert not data_file.exists()


def test_black_required_without_gold(client: TestClient, data_file: Path) -> None:
    """Without a gold winner, exactly one black crown must be assigned."""
    response = post(client, ["Ana", "Bo", "Ci"], ["5", "3", "7"], ["none", "none", "silver"])
    assert "corona nera" in response.text
    assert not data_file.exists()


def test_only_one_black_allowed(client: TestClient, data_file: Path) -> None:
    """Two black crowns violate the exactly-one rule."""
    response = post(client, ["Ana", "Bo"], ["10", "20"], ["black", "black"])
    assert "esattamente una corona nera" in response.text
    assert not data_file.exists()


def test_unknown_crown_treated_as_none(client: TestClient, data_file: Path) -> None:
    """A crown value the server does not know is handled as no crown."""
    post(client, ["Ana", "Bo", "Ci"], ["5", "3", "10"], ["bronze", "none", "black"])
    assert stored(data_file) == {"Ana": [5.0], "Bo": [3.0], "Ci": [10.0]}


def test_missing_crown_field_treated_as_none(client: TestClient, data_file: Path) -> None:
    """Submissions without player_crown[] keep working: rows count as no crown."""
    response = client.post(
        "/update",
        data={"player_name[]": ["Ana", "Bo"], "player_points[]": ["5", "3"]},
        follow_redirects=True,
    )
    assert "corona nera" in response.text  # invariant still enforced
    assert not data_file.exists()


# ------------------------------------------------------------ loser validation


def test_zero_points_for_loser_rejected(client: TestClient, data_file: Path) -> None:
    """Losers must score strictly more than zero."""
    response = post(client, ["Ana", "Bo", "Ci"], ["0", "5", "7"], ["none", "none", "black"])
    assert "maggiore di 0" in response.text
    assert stored(data_file) == {"Bo": [5.0], "Ci": [7.0]}


def test_negative_points_for_loser_rejected(client: TestClient, data_file: Path) -> None:
    """Negative scores stay invalid for losers."""
    response = post(client, ["Ana", "Bo", "Ci"], ["-3", "5", "7"], ["none", "none", "black"])
    assert "maggiore di 0" in response.text
    assert stored(data_file) == {"Bo": [5.0], "Ci": [7.0]}


def test_fractional_points_rejected(client: TestClient, data_file: Path) -> None:
    """Points must be whole numbers."""
    response = post(client, ["Ana", "Bo", "Ci"], ["4.5", "5", "7"], ["none", "none", "black"])
    assert "maggiore di 0" in response.text
    assert stored(data_file) == {"Bo": [5.0], "Ci": [7.0]}


def test_absent_player_gets_placeholder_and_means_unaffected(client: TestClient, data_file: Path) -> None:
    """Existing players not in a match get placeholder '-', means only count actual matches."""
    # Match 1: Ana and Bo play (gold winner: Ana called Alfredo and won)
    post(client, ["Ana", "Bo"], ["", "2"], ["gold", "none"])
    # Match 2: Bo and Ci play, Ana absent (black crown: Bo failed the call)
    post(client, ["Bo", "Ci"], ["4", "8"], ["black", "none"])

    raw = stored(data_file)
    assert raw["Ana"] == [WIN_POINTS, "-"]
    assert raw["Bo"] == [2.0, 4.0]
    assert raw["Ci"] == ["-", 8.0]

    # Check leaderboards & history view calculation
    from cardgame.storage import Storage
    from cardgame.stats import compute_global_stats, build_leaderboards, build_history_rows
    storage = Storage(data_file)
    data = storage.load()
    global_stats = compute_global_stats(data)
    # Total matches played across all: Ana: 1, Bo: 2, Ci: 1. Max matches = 2.
    # Total points: -10 + 2 + 4 + 8 = 4. Total played entries: 4. Mean = 1.0.
    assert global_stats.max_matches == 2
    assert global_stats.mean == 1.0

    leaderboards = build_leaderboards(data, global_stats)
    bo_row = next(r for r in leaderboards.raw if r.name == "Bo")
    ana_row = next(r for r in leaderboards.raw if r.name == "Ana")
    ci_row = next(r for r in leaderboards.raw if r.name == "Ci")

    assert bo_row.matches == 2
    assert bo_row.average == 3.0
    assert ana_row.matches == 1
    assert ana_row.average == WIN_POINTS
    assert ci_row.matches == 1
    assert ci_row.average == 8.0

    # History rows should have 2 global matches
    h_rows, max_m = build_history_rows(data)
    assert max_m == 2
    ana_h = next(r for r in h_rows if r.name == "Ana")
    assert ana_h.history == [WIN_POINTS, "-"]
    # In chart payload, '-' is converted to None for Chart.js
    assert ana_h.to_json_dict()["history"] == [WIN_POINTS, None]

