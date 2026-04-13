"""Compact card payload for ESP display (art + panel)."""

from __future__ import annotations

from typing import Any

from app.mana import format_mana_symbols_for_text, parse_mana_cost, sort_color_identity

COMPACT_SCHEMA = 1


def _panel_field(panel: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if value == "":
        return
    if value == []:
        return
    panel[key] = value


def _resolve_image_uris(raw: dict) -> dict[str, str] | None:
    """Scryfall: single-face cards use ``image_uris``; double-faced use ``card_faces[].image_uris``."""
    top = raw.get("image_uris")
    if isinstance(top, dict) and top:
        return {str(k): str(v) for k, v in top.items() if isinstance(v, str)}
    faces = raw.get("card_faces")
    if isinstance(faces, list):
        for face in faces:
            if not isinstance(face, dict):
                continue
            u = face.get("image_uris")
            if isinstance(u, dict) and u:
                return {str(k): str(v) for k, v in u.items() if isinstance(v, str)}
    return None


def scryfall_card_to_compact(raw: dict) -> dict[str, Any]:
    """Map a Scryfall Card JSON object to compact ``schema`` / ``image`` / ``panel``.

    ``panel`` holds display text (name, types, oracle, P/T, set line, etc.).

    ``image`` includes ``status`` and, when present, the same URL keys Scryfall uses under
    ``image_uris``: ``small``, ``normal``, ``large``, ``png``, ``art_crop``, ``border_crop``.
    Clients can pick one (e.g. ``normal`` or ``png`` for full frame; ``art_crop`` for square art).
    """
    uris = _resolve_image_uris(raw)

    if not uris:
        image: dict[str, Any] = {"status": "missing"}
    else:
        image = {"status": "ok", **uris}

    panel: dict[str, Any] = {
        "name": raw["name"],
        "mana_symbols": parse_mana_cost(raw.get("mana_cost")),
        "cmc": raw.get("cmc"),
        "type_line": raw.get("type_line") or "",
        "color_identity": sort_color_identity(raw.get("color_identity")),
    }

    _panel_field(panel, "oracle_text", format_mana_symbols_for_text(raw.get("oracle_text")))
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
    _panel_field(panel, "released_at", raw.get("released_at"))

    prices = raw.get("prices")
    if isinstance(prices, dict):
        _panel_field(panel, "price_usd", prices.get("usd"))
        _panel_field(panel, "price_usd_foil", prices.get("usd_foil"))

    return {
        "schema": COMPACT_SCHEMA,
        "id": raw["id"],
        "layout": raw.get("layout") or "normal",
        "image": image,
        "panel": panel,
    }
