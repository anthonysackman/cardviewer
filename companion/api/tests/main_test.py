from app.main import app


def test_ping():
    _, response = app.test_client.get("/ping")
    assert response.status == 200
    assert response.body == b"pong"
