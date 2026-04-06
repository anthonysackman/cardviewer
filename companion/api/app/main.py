from sanic import Sanic
from config import SanicConfig
from app.routes import ping_bp

def create_app(config: SanicConfig = SanicConfig) -> Sanic:
    app = Sanic("Cardviewer_API")
    app.update_config(config)
    app.blueprint(ping_bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)