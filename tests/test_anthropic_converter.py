"""Tests for Anthropic <-> OpenAI format conversion."""

import json

from ollama_router.anthropic.converter import (
    convert_anthropic_to_openai,
    convert_openai_to_anthropic_response,
)
from ollama_router.anthropic.models import ClaudeMessagesRequest


def _make_request(**overrides):
    base = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }
    base.update(overrides)
    return ClaudeMessagesRequest.model_validate(base)


def test_basic_text_request():
    req = _make_request()
    result = convert_anthropic_to_openai(req)
    assert result["model"] == "claude-sonnet-4-20250514"
    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == "Hello"
    assert result["stream"] is False


def test_system_as_string():
    req = _make_request(system="Be helpful")
    result = convert_anthropic_to_openai(req)
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"] == "Be helpful"


def test_system_as_list():
    req = _make_request(
        system=[{"type": "text", "text": "Part 1"}, {"type": "text", "text": "Part 2"}]
    )
    result = convert_anthropic_to_openai(req)
    assert result["messages"][0]["role"] == "system"
    assert "Part 1" in result["messages"][0]["content"]
    assert "Part 2" in result["messages"][0]["content"]


def test_tool_conversion():
    req = _make_request(
        tools=[
            {
                "name": "get_weather",
                "description": "Get weather info",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            }
        ]
    )
    result = convert_anthropic_to_openai(req)
    assert "tools" in result
    assert len(result["tools"]) == 1
    assert result["tools"][0]["type"] == "function"
    assert result["tools"][0]["function"]["name"] == "get_weather"
    assert result["tools"][0]["function"]["parameters"]["type"] == "object"


def test_assistant_with_tool_use():
    req = _make_request(
        messages=[
            {"role": "user", "content": "Check weather"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "get_weather",
                        "input": {"city": "SF"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": "Sunny 72F",
                    },
                ],
            },
        ]
    )
    result = convert_anthropic_to_openai(req)
    assistants = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 1
    assert "tool_calls" in assistants[0]
    assert assistants[0]["tool_calls"][0]["function"]["name"] == "get_weather"
    tool_msgs = [m for m in result["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "toolu_123"


def test_basic_response_conversion():
    req = _make_request()
    openai_resp = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hi there!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    result = convert_openai_to_anthropic_response(openai_resp, req)
    assert result["type"] == "message"
    assert result["role"] == "assistant"
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"] == "Hi there!"
    assert result["stop_reason"] == "end_turn"
    assert result["model"] == "claude-sonnet-4-20250514"


def test_response_with_tool_calls():
    req = _make_request()
    openai_resp = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "SF"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    result = convert_openai_to_anthropic_response(openai_resp, req)
    assert result["stop_reason"] == "tool_use"
    tool_block = result["content"][0]
    assert tool_block["type"] == "tool_use"
    assert tool_block["name"] == "get_weather"
    assert tool_block["input"] == {"city": "SF"}


def test_stop_reason_mapping():
    req = _make_request()
    for openai_reason, expected_anthropic in [
        ("stop", "end_turn"),
        ("length", "max_tokens"),
        ("tool_calls", "tool_use"),
        ("function_call", "tool_use"),
    ]:
        resp = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "hi"},
                    "finish_reason": openai_reason,
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        result = convert_openai_to_anthropic_response(resp, req)
        assert result["stop_reason"] == expected_anthropic, (
            f"Failed for {openai_reason}"
        )
