"""Parse Scryfall mana_cost strings into symbology tokens (e.g. {2}, {W/U}, {½})."""

from __future__ import annotations

import re

# Display order for color_identity on clients (WUBRG + colorless)
COLOR_ORDER = ("W", "U", "B", "R", "G", "C")
_MANA_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_TEXT_SYMBOL_MAP = {
    # Match firmware's display letters used in mana sprites:
    # W->P (Plains), U->I (Island), B->S (Swamp), R->M (Mountain), G->F (Forest)
    "W": "P",
    "U": "I",
    "B": "S",
    "R": "M",
    "G": "F",
    "C": "C",
}


def parse_mana_cost(text: str | None) -> list[str]:
    """Split ``mana_cost`` into ordered ``{...}`` symbol strings. Empty/None → []."""
    if not text:
        return []
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        j = text.find("}", i + 1)
        if j == -1:
            break
        out.append(text[i : j + 1])
        i = j + 1
    return out


def sort_color_identity(colors: list[str] | None) -> list[str]:
    """Stable WUBRG+C order; ignores unknown entries."""
    if not colors:
        return []
    present = {c.upper() for c in colors}
    return [c for c in COLOR_ORDER if c in present]


def format_mana_symbols_for_text(text: str | None) -> str | None:
    """Replace mana-style {..} symbols in text with compact readable '(..)' tokens."""
    if text is None:
        return None

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip().upper()
        parts = [p.strip() for p in inner.split("/")]
        mapped = [_TEXT_SYMBOL_MAP.get(p, p) for p in parts]
        return f"({'/'.join(mapped)})"

    return _MANA_TOKEN_RE.sub(repl, text)
