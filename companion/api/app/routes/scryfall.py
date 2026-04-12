from typing import Any, cast
from urllib.parse import quote, urlparse

from sanic import Blueprint
from sanic.response import HTTPResponse, json, raw

from app.constants import ResponseFormat
from app.images import to_display_bw_jpeg, to_display_bw_packed, to_display_jpeg
from app.request import ValidatedRequest
from app.schemas.queries import RandomCardQuery
from app.serializers.compact_card import scryfall_card_to_compact
from app.validation.decorators import validate_query

skryfall_bp = Blueprint("scryfall", url_prefix="/scryfall")


def _pick_display_source(image: dict[str, Any]) -> str | None:
    # Prefer full-card assets (no art-only crops).
    for key in ("png", "large", "normal", "small", "art_crop", "border_crop"):
        val = image.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _build_display_proxy_url(request: ValidatedRequest, source_url: str) -> str:
    base = f"{request.scheme}://{request.host}"
    encoded = quote(source_url, safe="")
    # App is typically published behind nginx at /api/* (proxy strips prefix before Sanic).
    # Emit the public URL so firmware can fetch through the same origin path.
    return f"{base}/api/scryfall/images/display?src={encoded}"


def _build_display_bw_proxy_url(request: ValidatedRequest, source_url: str) -> str:
    base = f"{request.scheme}://{request.host}"
    encoded = quote(source_url, safe="")
    return f"{base}/api/scryfall/images/display_bw?src={encoded}&profile=hybrid"


def _build_display_bw_raw_proxy_url(request: ValidatedRequest, source_url: str) -> str:
    base = f"{request.scheme}://{request.host}"
    encoded = quote(source_url, safe="")
    return f"{base}/api/scryfall/images/display_bw_raw?src={encoded}&profile=hybrid"


def _is_allowed_source_url(source_url: str) -> bool:
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return False
    if parsed.scheme not in {"https"}:
        return False
    host = (parsed.hostname or "").lower()
    return bool(host) and host.endswith("scryfall.io")


@skryfall_bp.get("/cards/random")
@validate_query(RandomCardQuery)
async def get_random_card(request: ValidatedRequest) -> HTTPResponse:
    scryfall_client = request.app.ctx.scryfall_client
    card = await scryfall_client.get_random_card()
    query = cast(RandomCardQuery, request.validated_data)
    if query.format is ResponseFormat.COMPACT:
        compact = scryfall_card_to_compact(card)
        image_obj = compact.get("image")
        if isinstance(image_obj, dict) and image_obj.get("status") == "ok":
            src = _pick_display_source(image_obj)
            if src:
                image_obj["display"] = _build_display_proxy_url(request, src)
                image_obj["display_bw"] = _build_display_bw_proxy_url(request, src)
                image_obj["display_bw_raw"] = _build_display_bw_raw_proxy_url(request, src)
        return json(compact)
    return json({"card": card})


@skryfall_bp.get("/images/display")
async def get_display_image(request: ValidatedRequest) -> HTTPResponse:
    src = request.args.get("src")
    if not src:
        return json({"error": "validation_error", "detail": "missing src query parameter"}, status=400)
    if not _is_allowed_source_url(src):
        return json({"error": "validation_error", "detail": "src must be an https://*.scryfall.io URL"}, status=400)

    scryfall_client = request.app.ctx.scryfall_client
    try:
        source = await scryfall_client.get_binary(src)
        display_bytes = to_display_jpeg(source)
    except Exception:
        return json({"error": "upstream_error", "detail": "unable to fetch or transform image"}, status=502)

    headers = {"Cache-Control": "public, max-age=86400"}
    return raw(display_bytes, content_type="image/jpeg", headers=headers)


@skryfall_bp.get("/images/display_bw")
async def get_display_bw_image(request: ValidatedRequest) -> HTTPResponse:
    src = request.args.get("src")
    profile = request.args.get("profile", default="auto")
    if profile not in {"auto", "hybrid", "photo", "text"}:
        return json({"error": "validation_error", "detail": "profile must be auto|hybrid|photo|text"}, status=400)
    if not src:
        return json({"error": "validation_error", "detail": "missing src query parameter"}, status=400)
    if not _is_allowed_source_url(src):
        return json({"error": "validation_error", "detail": "src must be an https://*.scryfall.io URL"}, status=400)

    scryfall_client = request.app.ctx.scryfall_client
    try:
        source = await scryfall_client.get_binary(src)
        display_bytes = to_display_bw_jpeg(source, profile=profile)
    except Exception:
        return json({"error": "upstream_error", "detail": "unable to fetch or transform image"}, status=502)

    headers = {"Cache-Control": "public, max-age=86400"}
    return raw(display_bytes, content_type="image/jpeg", headers=headers)


@skryfall_bp.get("/images/display_bw_raw")
async def get_display_bw_raw_image(request: ValidatedRequest) -> HTTPResponse:
    src = request.args.get("src")
    profile = request.args.get("profile", default="auto")
    if profile not in {"auto", "hybrid", "photo", "text"}:
        return json({"error": "validation_error", "detail": "profile must be auto|hybrid|photo|text"}, status=400)
    if not src:
        return json({"error": "validation_error", "detail": "missing src query parameter"}, status=400)
    if not _is_allowed_source_url(src):
        return json({"error": "validation_error", "detail": "src must be an https://*.scryfall.io URL"}, status=400)

    scryfall_client = request.app.ctx.scryfall_client
    try:
        source = await scryfall_client.get_binary(src)
        packed = to_display_bw_packed(source, profile=profile)
    except Exception:
        return json({"error": "upstream_error", "detail": "unable to fetch or transform image"}, status=502)

    headers = {
        "Cache-Control": "public, max-age=86400",
        "X-Cardviewer-Width": "232",
        "X-Cardviewer-Height": "300",
        "X-Cardviewer-Row-Bytes": "29",
    }
    return raw(packed, content_type="application/octet-stream", headers=headers)
