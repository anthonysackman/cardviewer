"""Image helpers for ESP display-targeted art transforms."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

DISPLAY_ART_WIDTH = 232
DISPLAY_ART_HEIGHT = 300
DISPLAY_JPEG_QUALITY = 62


def to_display_jpeg(
    source_bytes: bytes,
    *,
    width: int = DISPLAY_ART_WIDTH,
    height: int = DISPLAY_ART_HEIGHT,
    quality: int = DISPLAY_JPEG_QUALITY,
) -> bytes:
    """Resize and grayscale source image into display-sized JPEG bytes."""
    with Image.open(BytesIO(source_bytes)) as img:
        gray = img.convert("L")
        fitted = ImageOps.fit(
            gray,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        out = BytesIO()
        fitted.save(
            out,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=False,
        )
        return out.getvalue()
