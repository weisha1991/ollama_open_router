"""FastAPI router for Anthropic Messages API compatible endpoints.

Provides /v1/messages and /v1/messages/count_tokens for Claude Code compatibility.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ollama_router.anthropic.converter import (
    convert_anthropic_to_openai,
    convert_openai_to_anthropic_response,
)
from ollama_router.anthropic.models import (
    ClaudeMessagesRequest,
    ClaudeTokenCountRequest,
)
from ollama_router.anthropic.stream import convert_openai_stream_to_anthropic

logger = logging.getLogger("ollama_router")


def create_anthropic_router() -> APIRouter:
    router = APIRouter()

    @router.post("/v1/messages")
    async def create_message(request: Request):
        body = await request.json()
        claude_request = ClaudeMessagesRequest.model_validate(body)

        logger.debug(
            "anthropic_headers x-api-key=%s authorization=%s",
            "present" if request.headers.get("x-api-key") else "absent",
            "present" if request.headers.get("authorization") else "absent",
        )

        retry_manager = request.app.state.retry_manager
        proxy = request.app.state.proxy

        target_model = claude_request.model
        if claude_request.model.startswith("claude-"):
            target_model = "glm-5.1"

        openai_request = convert_anthropic_to_openai(claude_request)
        openai_request["model"] = target_model

        logger.info(
            "anthropic_request model=%s->%s stream=%s",
            claude_request.model,
            target_model,
            claude_request.stream,
        )

        if claude_request.stream:
            return await _handle_streaming(
                request, claude_request, openai_request, proxy
            )
        else:
            return await _handle_non_streaming(
                request, claude_request, openai_request, retry_manager
            )

    async def _handle_non_streaming(
        request: Request,
        claude_request: ClaudeMessagesRequest,
        openai_request: dict,
        retry_manager,
    ) -> JSONResponse:
        from ollama_router.request_context import get_request_id

        request_id = get_request_id()
        headers: dict[str, str] = {}

        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers=headers,
            body=openai_request,
            proxy=request.app.state.proxy,
            request_id=request_id,
        )

        if not result.success:
            error_msg = result.last_error or "Proxy error"
            status = 502
            if result.last_error == "No available API keys":
                status = 503
            elif result.response:
                status = result.response.status_code
                try:
                    error_msg = result.response.json().get("error", error_msg)
                except Exception:
                    pass
            return JSONResponse(
                status_code=status,
                content={
                    "type": "error",
                    "error": {"type": "api_error", "message": str(error_msg)},
                },
            )

        assert result.response is not None

        if result.response.status_code != 200:
            try:
                error_body = result.response.json()
                error_msg = error_body.get("error", {}).get(
                    "message", f"Upstream returned {result.response.status_code}"
                )
            except Exception:
                error_msg = f"Upstream returned {result.response.status_code}"
            logger.error(
                "anthropic_upstream_error status=%d model=%s body=%s",
                result.response.status_code,
                claude_request.model,
                str(error_msg)[:200],
            )
            return JSONResponse(
                status_code=result.response.status_code,
                content={
                    "type": "error",
                    "error": {"type": "api_error", "message": error_msg},
                },
            )

        try:
            openai_response = result.response.json()
        except Exception:
            return JSONResponse(
                status_code=502,
                content={
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": "Invalid upstream response",
                    },
                },
            )

        claude_response = convert_openai_to_anthropic_response(
            openai_response, claude_request
        )
        return JSONResponse(content=claude_response)

    async def _handle_streaming(
        request: Request,
        claude_request: ClaudeMessagesRequest,
        openai_request: dict,
        proxy,
    ) -> StreamingResponse:
        from ollama_router.state import KeySelector

        selector: KeySelector = request.app.state.selector
        selected_key = selector.select()

        if selected_key is None:
            return JSONResponse(
                status_code=503,
                content={
                    "type": "error",
                    "error": {"type": "api_error", "message": "No available API keys"},
                },
            )

        headers = {"Authorization": f"Bearer {selected_key.key}"}
        upstream_url = f"{proxy.upstream}/chat/completions"
        openai_request["stream"] = True

        async def stream_generator():
            try:
                async with proxy.client.stream(
                    method="POST",
                    url=upstream_url,
                    headers=headers,
                    json=openai_request,
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(
                            "anthropic_stream_upstream_error status=%d body=%s",
                            response.status_code,
                            error_body[:200],
                        )
                        yield _sse_error(f"Upstream error: {response.status_code}")
                        return

                    async for event in convert_openai_stream_to_anthropic(
                        response.aiter_lines(),
                        claude_request,
                    ):
                        yield event
            except Exception as e:
                logger.error("anthropic_stream_error error=%s", e, exc_info=True)
                yield _sse_error(str(e))

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/v1/messages/count_tokens")
    async def count_tokens(request: Request):
        body = await request.json()
        token_request = ClaudeTokenCountRequest.model_validate(body)

        total_chars = 0

        if token_request.system:
            if isinstance(token_request.system, str):
                total_chars += len(token_request.system)
            elif isinstance(token_request.system, list):
                for block in token_request.system:
                    if hasattr(block, "text"):
                        total_chars += len(block.text)

        for msg in token_request.messages:
            if msg.content is None:
                continue
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if hasattr(block, "text") and block.text is not None:
                        total_chars += len(block.text)

        estimated = max(1, total_chars // 4)
        return {"input_tokens": estimated}

    return router


def _sse_error(message: str) -> str:
    return (
        f"event: error\ndata: "
        f"{json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': message}})}\n\n"
    )
