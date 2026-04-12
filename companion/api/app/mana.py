"""Parse Scryfall mana_cost strings into symbology tokens (e.g. {2}, {W/U}, {½})."""

from __future__ import annotations

# Display order for color_identity on clients (WUBRG + colorless)
COLOR_ORDER = ("W", "U", "B", "R", "G", "C")


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
