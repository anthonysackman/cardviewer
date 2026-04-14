"""Image helpers for ESP display-targeted art transforms."""

from __future__ import annotations

from io import BytesIO
from statistics import fmean

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

DISPLAY_ART_WIDTH = 232
DISPLAY_ART_HEIGHT = 300
DISPLAY_JPEG_QUALITY = 92


def to_display_jpeg(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    quality: int = DISPLAY_JPEG_QUALITY,
) -> bytes:
    """Resize full card with preserved aspect and sharpen for e-ink legibility."""
    with Image.open(BytesIO(source_bytes)) as img:
        gray = img.convert("L")
        contained = ImageOps.contain(
            gray,
            (width, height),
            method=Image.Resampling.LANCZOS,
        )
        # Keep full-card framing by letterboxing into the exact panel size.
        canvas = Image.new("L", (width, height), color=255)
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))

        # Mild contrast + unsharp mask to keep text edges readable after JPEG decode on ESP.
        tuned = ImageEnhance.Contrast(canvas).enhance(1.2)
        tuned = tuned.filter(ImageFilter.UnsharpMask(radius=1.2, percent=170, threshold=2))

        out = BytesIO()
        tuned.save(
            out,
            format="JPEG",
            quality=quality,
            optimize=False,
            progressive=False,
        )
        return out.getvalue()


def _fit_full_card_gray(source_bytes: bytes, width: int, height: int) -> Image.Image:
    with Image.open(BytesIO(source_bytes)) as img:
        gray = img.convert("L")
        contained = ImageOps.contain(
            gray,
            (width, height),
            method=Image.Resampling.LANCZOS,
        )
        canvas = Image.new("L", (width, height), color=255)
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))
        return canvas


def _otsu_threshold(img: Image.Image) -> int:
    hist = img.histogram()
    total = img.width * img.height
    sum_total = 0
    for i, h in enumerate(hist):
        sum_total += i * h

    sum_b = 0.0
    w_b = 0
    var_max = -1.0
    threshold = 128

    for t, h in enumerate(hist):
        w_b += h
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * h
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) * (m_b - m_f)
        if var_between > var_max:
            var_max = var_between
            threshold = t
    return threshold


def _edge_density(img: Image.Image) -> float:
    edges = img.filter(ImageFilter.FIND_EDGES)
    hist = edges.histogram()
    strong = sum(hist[160:])
    total = img.width * img.height
    return strong / total if total else 0.0


def _adaptive_tile_threshold(img: Image.Image, *, tile: int = 20, bias: int = 6) -> Image.Image:
    """Local threshold by tiles (stable text rendering vs single global threshold)."""
    w, h = img.size
    out = Image.new("L", (w, h), color=255)
    for y0 in range(0, h, tile):
        for x0 in range(0, w, tile):
            x1 = min(w, x0 + tile)
            y1 = min(h, y0 + tile)
            box = (x0, y0, x1, y1)
            block = img.crop(box)
            t = _otsu_threshold(block)
            t = max(0, min(255, t + bias))
            bw_block = block.point(lambda p, tt=t: 255 if p >= tt else 0, mode="L")
            out.paste(bw_block, box)
    return out.convert("1")


def _card_content_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    """Estimate non-letterbox card bounds after contain() placement."""
    mask = img.point(lambda p: 255 if p < 248 else 0, mode="1")
    bbox = mask.getbbox()
    if bbox is None:
        return (0, 0, img.width, img.height)
    return bbox


def to_display_bw_jpeg(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    quality: int = 96,
    profile: str = "auto",
) -> bytes:
    """Pre-binarize image server-side for more consistent e-ink rendering."""
    bw = to_display_bw_image(source_bytes, width=width, height=height, profile=profile)

    out = BytesIO()
    # Save as JPEG (for current ESP JPEG decoder pipeline), but force 4:4:4 subsampling.
    bw.convert("L").save(
        out,
        format="JPEG",
        quality=quality,
        subsampling=0,
        optimize=False,
        progressive=False,
    )
    return out.getvalue()


def to_display_bw_image(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    profile: str = "auto",
) -> Image.Image:
    """Convert source image to full-card 1-bit PIL image."""
    base = _fit_full_card_gray(source_bytes, width, height)
    tuned = ImageEnhance.Contrast(base).enhance(1.18)
    tuned = tuned.filter(ImageFilter.UnsharpMask(radius=1.1, percent=155, threshold=2))

    if profile == "auto":
        # Text-heavy / high-edge cards tend to become snowy with diffusion dithering.
        profile = "hybrid"

    if profile == "photo":
        # Error diffusion preserves tones for painterly/low-contrast artwork.
        dither_enum = getattr(Image, "Dither", None)
        dither_mode = dither_enum.FLOYDSTEINBERG if dither_enum else Image.FLOYDSTEINBERG
        return tuned.convert("1", dither=dither_mode)

    if profile == "hybrid":
        # Deterministic mixed-content strategy:
        # - start with local adaptive threshold for text stability
        # - replace art window with Floyd dithering for smoother gradients
        text_bw = _adaptive_tile_threshold(tuned, tile=18, bias=5).convert("L")
        dither_enum = getattr(Image, "Dither", None)
        dither_mode = dither_enum.FLOYDSTEINBERG if dither_enum else Image.FLOYDSTEINBERG
        art_bw = tuned.convert("1", dither=dither_mode).convert("L")

        x0, y0, x1, y1 = _card_content_bbox(base)
        cw = max(1, x1 - x0)
        ch = max(1, y1 - y0)
        art_box = (
            x0 + int(cw * 0.06),
            y0 + int(ch * 0.15),
            x0 + int(cw * 0.94),
            y0 + int(ch * 0.58),
        )
        text_bw.paste(art_bw.crop(art_box), art_box)
        return text_bw.convert("1")

    # Text profile: stable threshold with tiny denoise first to reduce peppering.
    denoised = tuned.filter(ImageFilter.MedianFilter(size=3))
    t = _otsu_threshold(denoised)
    # Slightly bias toward white to avoid blown-out pepper on e-ink.
    t = int(fmean((t, 132)))
    return denoised.point(lambda p: 255 if p >= t else 0, mode="1")


def to_display_bw_packed(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    profile: str = "auto",
) -> bytes:
    """Pack 1-bit image to row-major bytes (MSB first), black=1."""
    bw = to_display_bw_image(source_bytes, width=width, height=height, profile=profile).convert("1")
    pixels = bw.load()
    row_bytes = (width + 7) // 8
    out = bytearray(row_bytes * height)
    for y in range(height):
        row_offset = y * row_bytes
        for x in range(width):
            # PIL mode "1": 0 is black, 255 is white.
            if pixels[x, y] == 0:
                idx = row_offset + (x >> 3)
                out[idx] |= 1 << (7 - (x & 7))
    return bytes(out)
