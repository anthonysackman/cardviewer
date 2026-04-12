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


def to_display_bw_jpeg(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    quality: int = 96,
    profile: str = "auto",
) -> bytes:
    """Pre-binarize image server-side for more consistent e-ink rendering."""
    base = _fit_full_card_gray(source_bytes, width, height)
    tuned = ImageEnhance.Contrast(base).enhance(1.18)
    tuned = tuned.filter(ImageFilter.UnsharpMask(radius=1.1, percent=155, threshold=2))

    if profile == "auto":
        # Text-heavy / high-edge cards tend to become snowy with diffusion dithering.
        profile = "text" if _edge_density(tuned) > 0.16 else "photo"

    if profile == "photo":
        # Error diffusion preserves tones for painterly/low-contrast artwork.
        dither_enum = getattr(Image, "Dither", None)
        dither_mode = dither_enum.FLOYDSTEINBERG if dither_enum else Image.FLOYDSTEINBERG
        bw = tuned.convert("1", dither=dither_mode)
    else:
        # Text profile: stable threshold with tiny denoise first to reduce peppering.
        denoised = tuned.filter(ImageFilter.MedianFilter(size=3))
        t = _otsu_threshold(denoised)
        # Slightly bias toward white to avoid blown-out pepper on e-ink.
        t = int(fmean((t, 132)))
        bw = denoised.point(lambda p: 255 if p >= t else 0, mode="1")

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
