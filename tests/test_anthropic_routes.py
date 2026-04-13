"""Integration tests for Anthropic API endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from ollama_router.config import Config
from ollama_router.router import create_app


def _make_config():
    return Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key_1", "test_key_2"],
    )


def test_messages_endpoint_exists(tmp_path):
    config = _make_config()
    app = create_app(config, state_dir=str(tmp_path))
    client = TestClient(app)

    resp = client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert resp.status_code != 404
    assert resp.status_code != 405


def test_count_tokens_endpoint_exists(tmp_path):
    config = _make_config()
    app = create_app(config, state_dir=str(tmp_path))
    client = TestClient(app)

    resp = client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello world"}],
        },
    )
    assert resp.status_code != 404
    assert resp.status_code != 405


def test_count_tokens_returns_tokens(tmp_path):
    config = _make_config()
    app = create_app(config, state_dir=str(tmp_path))
    client = TestClient(app)

    resp = client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello world"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "input_tokens" in data
    assert data["input_tokens"] > 0


def test_messages_with_mocked_upstream(tmp_path):
    config = _make_config()
    app = create_app(config, state_dir=str(tmp_path))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hello from GLM!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_response.content = json.dumps(mock_response.json.return_value).encode()

    from ollama_router.retry import RetryResult

    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            app.state.retry_manager,
            "execute_with_retry",
            AsyncMock(
                return_value=RetryResult(
                    response=mock_response, success=True, attempts=1
                )
            ),
        )
        client = TestClient(app)
        resp = client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert data["content"][0]["type"] == "text"
        assert "GLM" in data["content"][0]["text"]
        assert data["model"] == "claude-sonnet-4-20250514"


def test_existing_health_still_works(tmp_path):
    config = _make_config()
    app = create_app(config, state_dir=str(tmp_path))
    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
