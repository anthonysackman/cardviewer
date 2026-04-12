from sanic import Blueprint
from sanic.request import Request
from sanic.response import HTTPResponse, json
    

skryfall_bp = Blueprint("scryfall", url_prefix="/scryfall")


@skryfall_bp.get("/cards/random")
async def get_random_card(request: Request) -> HTTPResponse:
    scryfall_client = request.app.ctx.scryfall_client
    card = await scryfall_client.get_random_card()
    return json({"card": card})
