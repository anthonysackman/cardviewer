from unittest.mock import AsyncMock

from app.main import create_app
from tests.fixtures import SKY_RUIN_CARD


def test_random_compact_format():
    app = create_app()
    app.ctx.scryfall_client.get_random_card = AsyncMock(return_value=SKY_RUIN_CARD)
    _, response = app.test_client.get("/scryfall/cards/random?format=compact")
    assert response.status == 200
    j = response.json
    assert j["schema"] == 1
    assert j["panel"]["name"] == "Sky Ruin Drake"
    assert j["panel"]["mana_symbols"] == ["{4}", "{U}"]
    assert j["image"]["status"] == "ok"


def test_random_default_wraps_card():
    app = create_app()
    card = {"id": "abc", "name": "N"}
    app.ctx.scryfall_client.get_random_card = AsyncMock(return_value=card)
    _, response = app.test_client.get("/scryfall/cards/random")
    assert response.status == 200
    assert response.json == {"card": card}


def test_random_invalid_format_returns_422():
    app = create_app()
    app.ctx.scryfall_client.get_random_card = AsyncMock(return_value={})
    _, response = app.test_client.get("/scryfall/cards/random?format=nope")
    assert response.status == 422
    assert response.json["error"] == "validation_error"
