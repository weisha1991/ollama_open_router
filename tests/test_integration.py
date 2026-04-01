# pyright: reportMissingImports=false

from fastapi.testclient import TestClient

from ollama_router.config import Config
from ollama_router.router import create_app


def test_integration_key_rotation_with_retry(httpx_mock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    httpx_mock.add_response(
        status_code=429,
        json={"error": "rate limit exceeded"},
    )
    httpx_mock.add_response(
        status_code=200,
        json={"choices": [{"message": {"content": "success"}}]},
    )

    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2"],
        cooldown_rate_hours=4,
    )
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "model": "glm-4.7:cloud",
        "messages": [{"role": "user", "content": "hello"}],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "success"


def test_integration_all_keys_exhausted(httpx_mock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    for _ in range(2):
        httpx_mock.add_response(
            status_code=429,
            json={"error": "rate limit exceeded"},
        )

    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2"],
        cooldown_rate_hours=4,
    )
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "model": "glm-4.7:cloud",
        "messages": [{"role": "user", "content": "hello"}],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503


def test_integration_three_keys_retry(httpx_mock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    httpx_mock.add_response(status_code=429, json={"error": "rate limit exceeded"})
    httpx_mock.add_response(status_code=429, json={"error": "rate limit exceeded"})
    httpx_mock.add_response(
        status_code=200, json={"choices": [{"message": {"content": "ok"}}]}
    )

    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2", "key3"],
        cooldown_rate_hours=4,
    )
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "model": "glm-4.7:cloud",
        "messages": [{"role": "user", "content": "hello"}],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
