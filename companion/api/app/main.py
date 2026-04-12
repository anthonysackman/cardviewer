from sanic import Sanic, Blueprint
from config import SanicConfig
from app.routes import ping_bp
from sanic_redis import SanicRedis
from app.routes.scryfall import skryfall_bp
from app.clients.scryfall import ScryfallClient

def initialize_clients(app: Sanic) -> Sanic:
    scryfall_client = ScryfallClient()
    app.ctx.scryfall_client = scryfall_client
    return app

def create_app(config: SanicConfig = SanicConfig) -> Sanic:
    app = Sanic("Cardviewer_API")
    
    # Update Configuration
    app.update_config(config)

    api_bps = Blueprint.group(ping_bp, skryfall_bp)
    
    # Initialize Clients
    app = initialize_clients(app)
    
    # Register Blueprints
    app.blueprint(api_bps)
    
    # Initialize Redis
    redis_main = SanicRedis(config_name="REDIS_MAIN_URL")
    redis_main.init_app(app)
    
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)