"""Tests for the /alfredo web route."""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from cardgame import create_app  # noqa: E402
from cardgame.config import Config  # noqa: E402
from cardgame.storage import Storage  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client over a real app whose storage points at a temp file."""
    config = Config(
        secret_key="test-secret",
        admin_password="unused",
        data_dir=tmp_path,
        data_file=tmp_path / "scores.json",
        dev_mode=True,
    )
    app = create_app(config)
    return TestClient(app)


def flat(response) -> str:
    """Response body with whitespace collapsed, so wrapped attributes match."""
    return " ".join(response.text.split())


def test_alfredo_page_renders_with_defaults(client: TestClient) -> None:
    """GET /alfredo with no parameters simulates a default match."""
    response = client.get("/alfredo")
    assert response.status_code == 200
    body = flat(response)
    assert "Alfredo" in body
    assert "Classifica finale" in body
    # 4 players by default, 5 rounds.
    assert 'name="players" min="2" max="8" value="4"' in body
    assert "Round 5" in body
    assert "Round 6" not in body


def test_alfredo_respects_query_parameters(client: TestClient) -> None:
    """players/rounds/style/seed flow through to the simulation."""
    response = client.get("/alfredo?players=6&rounds=2&seed=7&style=careful")
    assert response.status_code == 200
    body = flat(response)
    assert "6 giocatori" in body
    assert "2 mazzo/i" in body  # ceil(6/4) == 2 decks
    assert "seed 7" in body
    assert "Round 2" in body
    assert "Round 3" not in body
    assert "careful" in body


def test_same_seed_renders_identical_page(client: TestClient) -> None:
    """The permalink seed makes the rendered match reproducible."""
    first = client.get("/alfredo?players=4&rounds=3&seed=42").text
    second = client.get("/alfredo?players=4&rounds=3&seed=42").text
    assert first == second


def test_invalid_players_shows_error_without_simulation(client: TestClient) -> None:
    """Out-of-range player counts are rejected with a visible message."""
    response = client.get("/alfredo?players=99")
    assert response.status_code == 200
    assert "between 2 and 8 players" in response.text
    assert "Classifica finale" not in response.text


def test_non_numeric_input_shows_error(client: TestClient) -> None:
    """Garbage parameters produce an error instead of a 500."""
    response = client.get("/alfredo?players=abc")
    assert response.status_code == 200
    assert "not a whole number" in response.text


def test_unknown_style_falls_back_to_default(client: TestClient) -> None:
    """An unknown style is reported but still renders using the default."""
    response = client.get("/alfredo?style=silly&rounds=1")
    assert response.status_code == 200
    assert "Unknown bot style" in response.text


def test_route_never_touches_scores_file(client: TestClient, tmp_path) -> None:
    """The simulator page must not write to the score book."""
    storage = Storage(tmp_path / "scores.json")
    client.get("/alfredo?players=4&rounds=3&seed=1")
    assert storage.load() == {}


def test_nav_link_points_to_alfredo(client: TestClient) -> None:
    """The shared navigation exposes the new page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "/alfredo" in response.text
