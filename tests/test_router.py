# pyright: reportMissingImports=false

from fastapi.testclient import TestClient

from ollama_router.config import Config, get_key_id
from ollama_router.router import create_app


def test_router_health():
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
    )
    app = create_app(config)
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["available_keys"] == 1
    assert data["total_keys"] == 1
    assert data["keys"][0]["key_id"] == get_key_id("test_key")
    assert data["keys"][0]["status"] == "available"
    assert "key" not in data["keys"][0]
