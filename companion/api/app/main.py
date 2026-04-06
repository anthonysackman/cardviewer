from sanic import Sanic
from config import SanicConfig
from app.routes import ping_bp
from sanic_redis import SanicRedis

def create_app(config: SanicConfig = SanicConfig) -> Sanic:
    app = Sanic("Cardviewer_API")
    
    # Update Configuration
    app.update_config(config)
    
    # Register Blueprints
    app.blueprint(ping_bp)
    
    # Initialize Redis
    redis_main = SanicRedis(config_name="REDIS_MAIN_URL")
    redis_main.init_app(app)
    
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)