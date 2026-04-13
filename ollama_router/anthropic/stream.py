"""Convert OpenAI SSE streaming to Anthropic SSE streaming format.

Reference: fuergaosi233/claude-code-proxy src/conversion/response_converter.py
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator, Dict

from ollama_router.anthropic import models as anthropic_models

logger = logging.getLogger("ollama_router")


def _sse(event_type: str, data: Dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def convert_openai_stream_to_anthropic(
    openai_stream: AsyncIterator[str],
    original_request: anthropic_models.ClaudeMessagesRequest,
) -> AsyncIterator[str]:
    """Convert OpenAI SSE streaming response to Anthropic SSE format."""
    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    yield _sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": original_request.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )

    text_block_index = 0
    yield _sse(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": text_block_index,
            "content_block": {"type": "text", "text": ""},
        },
    )

    yield _sse("ping", {"type": "ping"})

    tool_block_counter = 0
    current_tool_calls: Dict[int, Dict[str, Any]] = {}
    final_stop_reason = "end_turn"
    usage_data: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    try:
        async for line in openai_stream:
            if not line or not line.strip():
                continue
            if not line.startswith("data: "):
                continue

            chunk_data = line[6:]
            if chunk_data.strip() == "[DONE]":
                break

            try:
                chunk = json.loads(chunk_data)
            except json.JSONDecodeError:
                logger.warning("stream_parse_error data=%s", chunk_data[:100])
                continue

            usage = chunk.get("usage")
            if usage:
                prompt_details = usage.get("prompt_tokens_details", {})
                cache_read = (
                    prompt_details.get("cached_tokens", 0) if prompt_details else 0
                )
                usage_data = {
                    "input_tokens": usage.get(
                        "prompt_tokens", usage_data.get("input_tokens", 0)
                    ),
                    "output_tokens": usage.get(
                        "completion_tokens", usage_data.get("output_tokens", 0)
                    ),
                    "cache_read_input_tokens": cache_read,
                }

            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")

            if delta and "content" in delta and delta["content"] is not None:
                yield _sse(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": text_block_index,
                        "delta": {"type": "text_delta", "text": delta["content"]},
                    },
                )

            if "tool_calls" in delta and delta["tool_calls"]:
                for tc_delta in delta["tool_calls"]:
                    tc_index = tc_delta.get("index", 0)

                    if tc_index not in current_tool_calls:
                        current_tool_calls[tc_index] = {
                            "id": None,
                            "name": None,
                            "args_buffer": "",
                            "started": False,
                            "claude_index": None,
                        }

                    tool_call = current_tool_calls[tc_index]

                    if tc_delta.get("id"):
                        tool_call["id"] = tc_delta["id"]

                    func_data = tc_delta.get("function", {})
                    if func_data.get("name"):
                        tool_call["name"] = func_data["name"]

                    if (
                        tool_call["id"]
                        and tool_call["name"]
                        and not tool_call["started"]
                    ):
                        tool_block_counter += 1
                        claude_index = text_block_index + tool_block_counter
                        tool_call["claude_index"] = claude_index
                        tool_call["started"] = True

                        yield _sse(
                            "content_block_start",
                            {
                                "type": "content_block_start",
                                "index": claude_index,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tool_call["id"],
                                    "name": tool_call["name"],
                                    "input": {},
                                },
                            },
                        )

                    if (
                        "arguments" in func_data
                        and tool_call["started"]
                        and func_data["arguments"] is not None
                    ):
                        tool_call["args_buffer"] += func_data["arguments"]
                        yield _sse(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": tool_call["claude_index"],
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": func_data["arguments"],
                                },
                            },
                        )

            if finish_reason:
                final_stop_reason = {
                    "stop": "end_turn",
                    "length": "max_tokens",
                    "tool_calls": "tool_use",
                    "function_call": "tool_use",
                }.get(finish_reason, "end_turn")

    except Exception as e:
        logger.error("stream_conversion_error error=%s", e, exc_info=True)
        yield _sse(
            "error",
            {
                "type": "error",
                "error": {"type": "api_error", "message": f"Streaming error: {e}"},
            },
        )
        return

    yield _sse(
        "content_block_stop",
        {
            "type": "content_block_stop",
            "index": text_block_index,
        },
    )

    for tool_data in current_tool_calls.values():
        if tool_data.get("started") and tool_data.get("claude_index") is not None:
            yield _sse(
                "content_block_stop",
                {
                    "type": "content_block_stop",
                    "index": tool_data["claude_index"],
                },
            )

    yield _sse(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": final_stop_reason, "stop_sequence": None},
            "usage": usage_data,
        },
    )

    yield _sse("message_stop", {"type": "message_stop"})
