"""Compact card payload for ESP display (art + panel)."""

from __future__ import annotations

from typing import Any

from app.mana import parse_mana_cost, sort_color_identity

COMPACT_SCHEMA = 1


def _panel_field(panel: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if value == "":
        return
    if value == []:
        return
    panel[key] = value


def scryfall_card_to_compact(raw: dict) -> dict[str, Any]:
    """Map a Scryfall Card JSON object to compact ``schema`` / ``image`` / ``panel``."""
    image_uris = raw.get("image_uris")
    if isinstance(image_uris, dict):
        art_crop = image_uris.get("art_crop")
    else:
        art_crop = None

    if art_crop:
        image: dict[str, Any] = {"status": "ok", "art_crop": art_crop}
    else:
        image = {"status": "missing"}

    panel: dict[str, Any] = {
        "name": raw["name"],
        "mana_symbols": parse_mana_cost(raw.get("mana_cost")),
        "cmc": raw.get("cmc"),
        "type_line": raw.get("type_line") or "",
        "color_identity": sort_color_identity(raw.get("color_identity")),
    }

    _panel_field(panel, "oracle_text", raw.get("oracle_text"))
    _panel_field(panel, "power", raw.get("power"))
    _panel_field(panel, "toughness", raw.get("toughness"))
    _panel_field(panel, "loyalty", raw.get("loyalty"))
    _panel_field(panel, "flavor_text", raw.get("flavor_text"))

    keywords = raw.get("keywords")
    if isinstance(keywords, list) and keywords:
        panel["keywords"] = keywords

    _panel_field(panel, "set_code", raw.get("set"))
    _panel_field(panel, "set_name", raw.get("set_name"))
    _panel_field(panel, "collector_number", raw.get("collector_number"))
    _panel_field(panel, "rarity", raw.get("rarity"))

    return {
        "schema": COMPACT_SCHEMA,
        "id": raw["id"],
        "layout": raw.get("layout") or "normal",
        "image": image,
        "panel": panel,
    }
