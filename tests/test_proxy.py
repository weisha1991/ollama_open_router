# pyright: reportMissingImports=false

import pytest

from ollama_router.proxy import ProxyClient


@pytest.mark.asyncio
async def test_proxy_forwards_request(httpx_mock):
    httpx_mock.add_response(
        status_code=200,
        json={"choices": [{"message": {"content": "hello"}}]},
    )

    client = ProxyClient(upstream="https://ollama.com/v1")
    response = await client.forward(
        method="POST",
        path="/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json_data={
            "model": "glm-4.7:cloud",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"


@pytest.mark.asyncio
async def test_proxy_handles_429(httpx_mock):
    httpx_mock.add_response(
        status_code=429,
        json={"error": "rate limit exceeded"},
    )

    client = ProxyClient(upstream="https://ollama.com/v1")
    response = await client.forward(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        json_data={},
    )

    assert response.status_code == 429
    assert "rate limit" in response.json()["error"].lower()
