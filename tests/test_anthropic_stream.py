"""Tests for OpenAI -> Anthropic SSE streaming conversion."""

import json

import pytest

from ollama_router.anthropic.stream import convert_openai_stream_to_anthropic
from ollama_router.anthropic.models import ClaudeMessagesRequest


def _make_openai_chunks(text_deltas, finish_reason="stop"):
    lines = []
    for delta in text_deltas:
        chunk = {
            "id": "chatcmpl-123",
            "choices": [{"delta": {"content": delta}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(chunk)}")
    if finish_reason:
        chunk = {
            "id": "chatcmpl-123",
            "choices": [{"delta": {}, "finish_reason": finish_reason}],
        }
        lines.append(f"data: {json.dumps(chunk)}")
    lines.append("data: [DONE]")
    return lines


def _collect_events(lines):
    req = ClaudeMessagesRequest.model_validate(
        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
        }
    )

    async def _stream():
        for line in lines:
            yield line

    async def _run():
        events = []
        async for event in convert_openai_stream_to_anthropic(_stream(), req):
            events.append(event)
        return events

    import asyncio

    return asyncio.get_event_loop().run_until_complete(_run())


def _extract_event_types(events):
    types = []
    for e in events:
        for line in e.split("\n"):
            if line.startswith("event: "):
                types.append(line[7:])
    return types


def _extract_event_data(events, event_type):
    results = []
    for e in events:
        lines = e.split("\n")
        if lines[0] == f"event: {event_type}" and len(lines) > 1:
            data_line = lines[1]
            if data_line.startswith("data: "):
                results.append(json.loads(data_line[6:]))
    return results


@pytest.mark.asyncio
async def test_basic_text_stream():
    openai_lines = _make_openai_chunks(["Hello", " there", "!"])
    req = ClaudeMessagesRequest.model_validate(
        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
        }
    )

    async def stream():
        for line in openai_lines:
            yield line

    events = []
    async for event in convert_openai_stream_to_anthropic(stream(), req):
        events.append(event)

    event_types = _extract_event_types(events)
    assert "message_start" in event_types
    assert "content_block_start" in event_types
    assert "ping" in event_types
    assert event_types.count("content_block_delta") == 3
    assert "content_block_stop" in event_types
    assert "message_delta" in event_types
    assert "message_stop" in event_types


@pytest.mark.asyncio
async def test_stream_ends_with_max_tokens():
    openai_lines = _make_openai_chunks(["Hi"], finish_reason="length")
    req = ClaudeMessagesRequest.model_validate(
        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello"}],
        }
    )

    async def stream():
        for line in openai_lines:
            yield line

    events = []
    async for event in convert_openai_stream_to_anthropic(stream(), req):
        events.append(event)

    delta_data = _extract_event_data(events, "message_delta")
    assert len(delta_data) == 1
    assert delta_data[0]["delta"]["stop_reason"] == "max_tokens"


@pytest.mark.asyncio
async def test_stream_with_tool_calls():
    lines = [
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":None},"finish_reason":null}]}',
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"get_weather","arguments":""}}]},"finish_reason":null}]}',
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"city\\": \\"SF\\"}"}}]},"finish_reason":null}]}',
        'data: {"id":"chatcmpl-1","choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
    ]
    req = ClaudeMessagesRequest.model_validate(
        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Check weather"}],
        }
    )

    async def stream():
        for line in lines:
            yield line

    events = []
    async for event in convert_openai_stream_to_anthropic(stream(), req):
        events.append(event)

    full_text = "".join(events)
    assert "tool_use" in full_text
    assert "get_weather" in full_text

    delta_data = _extract_event_data(events, "message_delta")
    assert len(delta_data) == 1
    assert delta_data[0]["delta"]["stop_reason"] == "tool_use"
