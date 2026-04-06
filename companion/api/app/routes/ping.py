from sanic import Blueprint, text

ping_bp = Blueprint("ping", url_prefix="/ping")

@ping_bp.get("/")
async def ping(request):
    return text("pong")