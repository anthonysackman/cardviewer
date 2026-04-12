from unittest.mock import AsyncMock
from urllib.parse import quote

from PIL import Image
from io import BytesIO

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
    assert "/api/scryfall/images/display?src=" in j["image"]["display"]
    assert "/api/scryfall/images/display_bw?src=" in j["image"]["display_bw"]
    assert "/api/scryfall/images/display_bw_raw?src=" in j["image"]["display_bw_raw"]


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


def test_display_image_requires_src():
    app = create_app()
    _, response = app.test_client.get("/scryfall/images/display")
    assert response.status == 400
    assert response.json["error"] == "validation_error"


def test_display_image_rejects_non_scryfall_host():
    app = create_app()
    bad = quote("https://example.com/image.jpg", safe="")
    _, response = app.test_client.get(f"/scryfall/images/display?src={bad}")
    assert response.status == 400
    assert response.json["error"] == "validation_error"


def test_display_image_transforms_to_jpeg():
    app = create_app()
    src_buf = BytesIO()
    Image.new("RGB", (600, 400), color=(220, 40, 90)).save(src_buf, format="PNG")
    app.ctx.scryfall_client.get_binary = AsyncMock(return_value=src_buf.getvalue())

    src = quote("https://cards.scryfall.io/normal/front/x.jpg", safe="")
    _, response = app.test_client.get(f"/scryfall/images/display?src={src}")

    assert response.status == 200
    assert response.headers.get("content-type", "").startswith("image/jpeg")
    assert response.headers.get("cache-control") == "public, max-age=86400"
    assert response.body[:2] == b"\xff\xd8"
    with Image.open(BytesIO(response.body)) as rendered:
        assert rendered.size == (232, 300)


def test_random_compact_prefers_full_card_for_display_proxy():
    app = create_app()
    app.ctx.scryfall_client.get_random_card = AsyncMock(return_value=SKY_RUIN_CARD)
    _, response = app.test_client.get("/scryfall/cards/random?format=compact")
    assert response.status == 200
    display = response.json["image"]["display"]
    assert "png" in display


def test_display_bw_image_transforms_to_jpeg():
    app = create_app()
    src_buf = BytesIO()
    Image.new("RGB", (600, 400), color=(220, 40, 90)).save(src_buf, format="PNG")
    app.ctx.scryfall_client.get_binary = AsyncMock(return_value=src_buf.getvalue())

    src = quote("https://cards.scryfall.io/normal/front/x.jpg", safe="")
    _, response = app.test_client.get(f"/scryfall/images/display_bw?src={src}&profile=auto")

    assert response.status == 200
    assert response.headers.get("content-type", "").startswith("image/jpeg")
    assert response.body[:2] == b"\xff\xd8"
    with Image.open(BytesIO(response.body)) as rendered:
        assert rendered.size == (232, 300)


def test_display_bw_image_rejects_bad_profile():
    app = create_app()
    src = quote("https://cards.scryfall.io/normal/front/x.jpg", safe="")
    _, response = app.test_client.get(f"/scryfall/images/display_bw?src={src}&profile=bad")
    assert response.status == 400
    assert response.json["error"] == "validation_error"


def test_display_bw_raw_image_returns_expected_payload_size():
    app = create_app()
    src_buf = BytesIO()
    Image.new("RGB", (600, 400), color=(220, 40, 90)).save(src_buf, format="PNG")
    app.ctx.scryfall_client.get_binary = AsyncMock(return_value=src_buf.getvalue())

    src = quote("https://cards.scryfall.io/normal/front/x.jpg", safe="")
    _, response = app.test_client.get(f"/scryfall/images/display_bw_raw?src={src}&profile=auto")

    assert response.status == 200
    assert response.headers.get("content-type", "").startswith("application/octet-stream")
    assert response.headers.get("x-cardviewer-width") == "232"
    assert response.headers.get("x-cardviewer-height") == "300"
    assert response.headers.get("x-cardviewer-row-bytes") == "29"
    assert len(response.body) == 29 * 300
