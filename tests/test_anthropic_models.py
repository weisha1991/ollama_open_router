import pytest
from ollama_router.anthropic import models as am


def test_parse_basic_request():
    payload = {
        "model": "claude-v2",
        "max_tokens": 365,
        "messages": [
            {"role": "user", "content": "Hello"},
        ],
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    assert isinstance(req, am.ClaudeMessagesRequest)  # type: ignore
    assert len(req.messages) == 1
    assert req.messages[0].role == "user"
    assert req.messages[0].content == "Hello"


def test_parse_request_with_system_string():
    payload = {
        "model": "claude-v2",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": "Hi"}],
        "system": "system text",
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    assert isinstance(req.system, str)
    assert req.system == "system text"


def test_parse_request_with_system_list():
    system_list = [{"type": "text", "text": "system text"}]
    payload = {
        "model": "claude-v2",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hello"}],
        "system": system_list,
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    assert isinstance(req.system, list)
    assert isinstance(req.system[0], am.ClaudeSystemContent)  # type: ignore
    assert req.system[0].text == "system text"  # type: ignore


def test_parse_request_with_tools():
    tools = [{"name": "tool1", "input_schema": {"param": "value"}}]
    payload = {
        "model": "claude-v2",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "hello"}],
        "tools": tools,
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    assert isinstance(req.tools, list)
    assert isinstance(req.tools[0], am.ClaudeTool)  # type: ignore
    assert req.tools[0].name == "tool1"  # type: ignore


def test_parse_request_with_multimodal_content():
    payload = {
        "model": "claude-v2",
        "max_tokens": 60,
        "messages": [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": [
                    {"type": "image", "source": {"url": "https://example.com/a.png"}}
                ],
            },
        ],
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    # second message content should be a list of ContentBlock items
    assert isinstance(req.messages[1].content, list)  # type: ignore
    first_block = req.messages[1].content[0]
    assert isinstance(first_block, am.ClaudeContentBlockImage)  # type: ignore
    assert first_block.type == "image"  # type: ignore


def test_parse_tool_use_message():
    payload = {
        "model": "claude-v2",
        "max_tokens": 60,
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool1",
                        "name": "TestTool",
                        "input": {"param": "value"},
                    }
                ],
            }
        ],
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    content = req.messages[0].content  # type: ignore
    assert isinstance(content, list)  # type: ignore
    block = content[0]
    assert isinstance(block, am.ClaudeContentBlockToolUse)  # type: ignore
    assert block.type == "tool_use"  # type: ignore
    assert block.id == "tool1"  # type: ignore


def test_parse_tool_result_message():
    payload = {
        "model": "claude-v2",
        "max_tokens": 60,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool1",
                        "content": "ok",
                    }
                ],
            }
        ],
    }
    req = am.ClaudeMessagesRequest.model_validate(payload)  # type: ignore
    content = req.messages[0].content  # type: ignore
    block = content[0]
    assert isinstance(block, am.ClaudeContentBlockToolResult)  # type: ignore
    assert block.type == "tool_result"  # type: ignore
    assert block.tool_use_id == "tool1"  # type: ignore


def test_parse_token_count_request():
    payload = {
        "model": "claude-token-count",
        "messages": [{"role": "user", "content": "hi"}],
        "system": "system string",
        "tools": [{"name": "tool1", "input_schema": {}}],
        "thinking": {"enabled": False},
        "tool_choice": {"tool1": True},
    }
    req = am.ClaudeTokenCountRequest.model_validate(payload)  # type: ignore
    assert isinstance(req, am.ClaudeTokenCountRequest)  # type: ignore
    assert isinstance(req.thinking, am.ClaudeThinkingConfig) or req.thinking is None  # type: ignore
    assert req.thinking is not None and req.thinking.enabled is False  # type: ignore
