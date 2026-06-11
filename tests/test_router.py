# pyright: reportMissingImports=false

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from ollama_router.config import Config, get_key_id
from ollama_router.router import create_app
from ollama_router.retry import RetryResult, StreamSetupResult
from ollama_router.state import KeyState


def test_router_health(tmp_path):
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
    )
    app = create_app(config, state_dir=str(tmp_path))
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


def test_openai_streaming_request_returns_streaming_response(tmp_path):
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
    )
    app = create_app(config, state_dir=str(tmp_path))

    async def remaining_chunks():
        yield b'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    stream_context = MagicMock()
    stream_context.__aexit__ = AsyncMock(return_value=False)
    prepared = StreamSetupResult(
        success=True,
        attempts=1,
        response=MagicMock(
            status_code=200,
            headers={
                "content-type": "text/event-stream",
                "transfer-encoding": "chunked",
            },
        ),
        stream_context=stream_context,
        selected_key=KeyState(key="test_key"),
        first_chunk=b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
        chunk_iterator=remaining_chunks(),
    )
    app.state.retry_manager.prepare_stream_with_retry = AsyncMock(return_value=prepared)
    app.state.retry_manager.record_stream_completion = MagicMock()

    client = TestClient(app)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "glm-4.7:cloud",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_raw())

    assert b'"content":"hi"' in body
    assert b'"content":" there"' in body
    app.state.retry_manager.prepare_stream_with_retry.assert_awaited_once()
    stream_context.__aexit__.assert_awaited_once()
    app.state.retry_manager.record_stream_completion.assert_called_once()
    assert (
        app.state.retry_manager.record_stream_completion.call_args.kwargs["request_id"]
        != "no-request"
    )


def test_non_streaming_request_still_uses_buffered_proxy_path(tmp_path):
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
    )
    app = create_app(config, state_dir=str(tmp_path))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"choices":[{"message":{"content":"ok"}}]}'
    mock_response.headers = {"content-type": "application/json"}
    app.state.retry_manager.execute_with_retry = AsyncMock(
        return_value=RetryResult(response=mock_response, success=True, attempts=1)
    )
    app.state.retry_manager.prepare_stream_with_retry = AsyncMock()

    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-4.7:cloud",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "ok"
    app.state.retry_manager.execute_with_retry.assert_awaited_once()
    app.state.retry_manager.prepare_stream_with_retry.assert_not_awaited()
