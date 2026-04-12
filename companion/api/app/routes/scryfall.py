from typing import cast

from sanic import Blueprint
from sanic.response import HTTPResponse, json

from app.constants import ResponseFormat
from app.request import ValidatedRequest
from app.schemas.queries import RandomCardQuery
from app.serializers.compact_card import scryfall_card_to_compact
from app.validation.decorators import validate_query

skryfall_bp = Blueprint("scryfall", url_prefix="/scryfall")


@skryfall_bp.get("/cards/random")
@validate_query(RandomCardQuery)
async def get_random_card(request: ValidatedRequest) -> HTTPResponse:
    scryfall_client = request.app.ctx.scryfall_client
    card = await scryfall_client.get_random_card()
    query = cast(RandomCardQuery, request.validated_data)
    if query.format is ResponseFormat.COMPACT:
        return json(scryfall_card_to_compact(card))
    return json({"card": card})
