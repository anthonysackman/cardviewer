#!/usr/bin/env python3
"""Generate include/ManaSprites.h: 1-bit mana pips for Adafruit drawBitmap.

Terrain labels (not Scryfall letters): P Plains, I Island, S Swamp, M Mountain, F Forest, C colorless.
Snow mana {S} uses glyph W (MANA_DISP_SNOW). Scryfall W/U/B/R/G map to those sprites in firmware.
"""

from __future__ import annotations

import math
from pathlib import Path

W = H = 22
CX = (W - 1) / 2.0
CY = (H - 1) / 2.0
BYTES_PER_ROW = (W + 7) // 8
# Adafruit drawBitmap: ceil(width/8) bytes per row, H rows
BMP_BYTES = BYTES_PER_ROW * H


def ring(pix: list[list[int]], cx: float, cy: float, r0: float, r1: float) -> None:
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - cx, y - cy)
            if r0 <= d <= r1:
                pix[y][x] = 1


def merge_glyph(pix: list[list[int]], ox: int, oy: int, g: list[list[int]]) -> None:
    for r in range(len(g)):
        for c in range(len(g[r])):
            if g[r][c]:
                x, y = ox + c, oy + r
                if 0 <= x < W and 0 <= y < H:
                    pix[y][x] = 1


def pix_to_rows(pix: list[list[int]]) -> list[tuple[int, ...]]:
    rows: list[tuple[int, ...]] = []
    for y in range(H):
        row: list[int] = []
        for bi in range(BYTES_PER_ROW):
            b = 0
            for bit in range(8):
                x = bi * 8 + bit
                if x < W and pix[y][x]:
                    b |= 128 >> bit
            row.append(b)
        rows.append(tuple(row))
    return rows


def str_to_glyph(rows: list[str]) -> list[list[int]]:
    return [[int(ch) for ch in row] for row in rows]


def scale_glyph_k(g: list[list[int]], k: int) -> list[list[int]]:
    """Nearest-neighbor upscale (5x7 source)."""
    if not g:
        return []
    h, w = len(g), len(g[0])
    out = [[0] * (w * k) for _ in range(h * k)]
    for r in range(h):
        for c in range(w):
            if g[r][c]:
                for dr in range(k):
                    for dc in range(k):
                        out[r * k + dr][c * k + dc] = 1
    return out


# Ring inner edge ~ W/2 - 1.1; scale glyph height to ~75% of inner diameter.
_INNER_R = W / 2 - 1.1
_INNER_D = 2 * _INNER_R
GLYPH_SCALE = max(1, min(4, int(round(_INNER_D * 0.75 / 7))))

# 5x7 glyphs — avoid a solid vertical spine in P/S (was mistaken for a split pip on e-paper).
PATTERNS: dict[str, list[str]] = {
    "P": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ],
    "I": [
        "01110",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ],
    "S": [
        "01110",
        "10001",
        "10000",
        "01110",
        "00001",
        "10001",
        "01110",
    ],
    "M": [
        "10001",
        "11011",
        "10101",
        "10101",
        "10101",
        "10101",
        "10101",
    ],
    "F": [
        "11111",
        "10000",
        "11100",
        "10000",
        "10000",
        "10000",
        "10000",
    ],
    "C": [
        "01110",
        "10101",
        "10100",
        "10100",
        "10100",
        "10101",
        "01110",
    ],
    "W": [
        "10001",
        "10001",
        "10101",
        "10101",
        "10101",
        "10101",
        "01110",
    ],
}

DIGITS: dict[str, list[str]] = {
    "0": ["011", "101", "101", "101", "101", "101", "011"],
    "1": ["010", "110", "010", "010", "010", "010", "010"],
    "2": ["011", "101", "001", "010", "100", "100", "111"],
    "3": ["111", "001", "010", "001", "001", "101", "110"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "110", "001", "001", "110"],
    "6": ["011", "100", "100", "111", "101", "101", "011"],
    "7": ["111", "001", "010", "010", "010", "010", "010"],
    "8": ["011", "101", "101", "011", "101", "101", "011"],
    "9": ["011", "101", "101", "011", "001", "001", "110"],
}

GLYPH_X = [
    [1, 0, 1, 0, 1],
    [1, 0, 1, 0, 1],
    [0, 1, 0, 1, 0],
    [0, 1, 0, 1, 0],
    [1, 0, 1, 0, 1],
    [1, 0, 1, 0, 1],
    [1, 0, 1, 0, 1],
]


def digit_glyph(ch: str) -> list[list[int]]:
    return str_to_glyph(DIGITS[ch])


def make_color_letter(display_letter: str) -> list[tuple[int, ...]]:
    pix = [[0] * W for _ in range(H)]
    ring(pix, CX, CY, W / 2 - 1.1, W / 2 - 0.15)
    g = scale_glyph_k(str_to_glyph(PATTERNS[display_letter]), GLYPH_SCALE)
    gh, gw = len(g), len(g[0])
    ox = (W - gw) // 2
    oy = (H - gh) // 2
    merge_glyph(pix, ox, oy, g)
    return pix_to_rows(pix)


def make_generic_numeric(num_str: str) -> list[tuple[int, ...]]:
    pix = [[0] * W for _ in range(H)]
    ring(pix, CX, CY, W / 2 - 1.1, W / 2 - 0.15)
    if len(num_str) == 1 and num_str in DIGITS:
        g = scale_glyph_k(digit_glyph(num_str[0]), GLYPH_SCALE)
        gh, gw = len(g), len(g[0])
        merge_glyph(pix, (W - gw) // 2, (H - gh) // 2, g)
    elif len(num_str) == 2 and all(c in DIGITS for c in num_str):
        g0 = scale_glyph_k(digit_glyph(num_str[0]), GLYPH_SCALE)
        g1 = scale_glyph_k(digit_glyph(num_str[1]), GLYPH_SCALE)
        gh = len(g0)
        gap = 2
        total_w = len(g0[0]) + gap + len(g1[0])
        ox0 = (W - total_w) // 2
        oy = (H - gh) // 2
        merge_glyph(pix, ox0, oy, g0)
        merge_glyph(pix, ox0 + len(g0[0]) + gap, oy, g1)
    return pix_to_rows(pix)


def c_array(name: str, rows: list[tuple[int, ...]]) -> str:
    flat: list[str] = []
    for tup in rows:
        for b in tup:
            flat.append(f"0x{b:02x}")
    lines = [f"static const uint8_t {name}[{len(flat)}] PROGMEM = {{"]
    for i in range(0, len(flat), 8):
        chunk = flat[i : i + 8]
        lines.append("  " + ", ".join(chunk) + ",")
    lines.append("};")
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out_path = root / "include" / "ManaSprites.h"
    out: list[str] = [
        "#pragma once",
        "// AUTO-GENERATED by scripts/gen_mana_sprites.py",
        "#include <Arduino.h>",
        "",
        f"static constexpr int MANA_BMP_W = {W};",
        f"static constexpr int MANA_BMP_H = {H};",
        f"static constexpr size_t MANA_BMP_BYTES = {BMP_BYTES};",
        "",
    ]
    for letter in ("P", "I", "S", "M", "F", "C"):
        out.append(c_array(f"MANA_DISP_{letter}", make_color_letter(letter)))
        out.append("")
    out.append(c_array("MANA_DISP_SNOW", make_color_letter("W")))
    out.append("")
    for n in range(0, 21):
        out.append(c_array(f"MANA_SPRITE_GEN_{n}", make_generic_numeric(str(n))))
        out.append("")
    pix_x = [[0] * W for _ in range(H)]
    ring(pix_x, CX, CY, W / 2 - 1.1, W / 2 - 0.15)
    gx = scale_glyph_k(GLYPH_X, GLYPH_SCALE)
    merge_glyph(pix_x, (W - len(gx[0])) // 2, (H - len(gx)) // 2, gx)
    out.append(c_array("MANA_SPRITE_GEN_X", pix_to_rows(pix_x)))
    out.append("")
    out_path.write_text("\n".join(out), encoding="utf-8")
    print("Wrote", out_path)


if __name__ == "__main__":
    main()
