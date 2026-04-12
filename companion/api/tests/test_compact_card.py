from tests.fixtures import SKY_RUIN_CARD

from app.serializers.compact_card import COMPACT_SCHEMA, scryfall_card_to_compact


def test_compact_sky_ruin_drake():
    c = scryfall_card_to_compact(SKY_RUIN_CARD)
    assert c["schema"] == COMPACT_SCHEMA
    assert c["id"] == "2bdb5850-df1e-4d8a-af7a-15cab080fb8f"
    assert c["layout"] == "normal"
    assert c["image"]["status"] == "ok"
    assert c["image"]["art_crop"].endswith(".jpg")
    p = c["panel"]
    assert p["name"] == "Sky Ruin Drake"
    assert p["mana_symbols"] == ["{4}", "{U}"]
    assert p["cmc"] == 5.0
    assert p["type_line"] == "Creature — Drake"
    assert p["oracle_text"] == "Flying"
    assert p["power"] == "2"
    assert p["toughness"] == "5"
    assert p["color_identity"] == ["U"]
    assert p["keywords"] == ["Flying"]
    assert p["set_code"] == "zen"
    assert p["set_name"] == "Zendikar"
    assert p["collector_number"] == "66"
    assert p["rarity"] == "common"
    assert p["flavor_text"] == "Hold up."


def test_compact_missing_image():
    raw = {**SKY_RUIN_CARD}
    del raw["image_uris"]
    c = scryfall_card_to_compact(raw)
    assert c["image"] == {"status": "missing"}
