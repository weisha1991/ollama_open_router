"""Convert between Anthropic Messages API and OpenAI Chat Completions API formats.

Reference: fuergaosi233/claude-code-proxy src/conversion/
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from ollama_router.anthropic import models as anthropic_models

logger = logging.getLogger("ollama_router")


# ── Anthropic → OpenAI request conversion ──────────────────────────────────


def convert_anthropic_to_openai(
    request: anthropic_models.ClaudeMessagesRequest,
) -> Dict[str, Any]:
    """Convert an Anthropic Messages API request to OpenAI Chat Completions format."""
    openai_messages: List[Dict[str, Any]] = []

    # System message
    if request.system:
        system_text = _extract_system_text(request.system)
        if system_text.strip():
            openai_messages.append({"role": "system", "content": system_text.strip()})

    # Messages
    i = 0
    while i < len(request.messages):
        msg = request.messages[i]

        if msg.role == "user":
            if _is_tool_result_message(msg):
                openai_messages.extend(_convert_tool_results(msg))
            else:
                openai_messages.append(_convert_user_message(msg))
        elif msg.role == "assistant":
            openai_messages.append(_convert_assistant_message(msg))

        i += 1

    # Build OpenAI request
    openai_request: Dict[str, Any] = {
        "model": request.model,
        "messages": openai_messages,
        "max_tokens": request.max_tokens,
        "stream": request.stream,
    }

    if request.temperature is not None:
        openai_request["temperature"] = request.temperature
    if request.top_p is not None:
        openai_request["top_p"] = request.top_p
    if request.stop_sequences:
        openai_request["stop"] = request.stop_sequences

    # Convert tools
    if request.tools:
        openai_tools = []
        for tool in request.tools:
            if tool.name and tool.name.strip():
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                )
        if openai_tools:
            openai_request["tools"] = openai_tools

    # Convert tool choice
    if request.tool_choice:
        choice_type = request.tool_choice.get("type")
        if choice_type == "auto":
            openai_request["tool_choice"] = "auto"
        elif choice_type == "any":
            openai_request["tool_choice"] = "auto"
        elif choice_type == "tool" and "name" in request.tool_choice:
            openai_request["tool_choice"] = {
                "type": "function",
                "function": {"name": request.tool_choice["name"]},
            }
        else:
            openai_request["tool_choice"] = "auto"

    return openai_request


def _extract_system_text(
    system: Union[str, List[anthropic_models.ClaudeSystemContent]],
) -> str:
    """Extract text from system field (string or list of blocks)."""
    if isinstance(system, str):
        return system
    parts = []
    for block in system:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n\n".join(parts)


def _is_tool_result_message(msg: anthropic_models.ClaudeMessage) -> bool:
    """Check if a user message contains tool results."""
    if msg.role != "user" or isinstance(msg.content, str):
        return False
    return any(
        hasattr(block, "type") and block.type == "tool_result" for block in msg.content
    )


def _convert_user_message(msg: anthropic_models.ClaudeMessage) -> Dict[str, Any]:
    """Convert Anthropic user message to OpenAI format."""
    if msg.content is None:
        return {"role": "user", "content": ""}
    if isinstance(msg.content, str):
        return {"role": "user", "content": msg.content}

    openai_content = []
    for block in msg.content:
        if isinstance(block, anthropic_models.ClaudeContentBlockText):
            openai_content.append({"type": "text", "text": block.text})
        elif isinstance(block, anthropic_models.ClaudeContentBlockImage):
            if isinstance(block.source, dict) and block.source.get("type") == "base64":
                openai_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{block.source['media_type']};base64,{block.source['data']}"
                        },
                    }
                )

    if len(openai_content) == 1 and openai_content[0]["type"] == "text":
        return {"role": "user", "content": openai_content[0]["text"]}
    return {"role": "user", "content": openai_content}


def _convert_assistant_message(msg: anthropic_models.ClaudeMessage) -> Dict[str, Any]:
    """Convert Anthropic assistant message to OpenAI format."""
    if msg.content is None:
        return {"role": "assistant", "content": None}
    if isinstance(msg.content, str):
        return {"role": "assistant", "content": msg.content}

    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []

    for block in msg.content:
        if isinstance(block, anthropic_models.ClaudeContentBlockText):
            text_parts.append(block.text)
        elif isinstance(block, anthropic_models.ClaudeContentBlockToolUse):
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                }
            )

    result: Dict[str, Any] = {"role": "assistant"}
    result["content"] = "".join(text_parts) if text_parts else None
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def _convert_tool_results(msg: anthropic_models.ClaudeMessage) -> List[Dict[str, Any]]:
    """Convert Anthropic tool results to OpenAI tool messages."""
    results = []
    if isinstance(msg.content, list):
        for block in msg.content:
            if isinstance(block, anthropic_models.ClaudeContentBlockToolResult):
                content = _parse_tool_result_content(block.content)
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": content,
                    }
                )
    return results


def _parse_tool_result_content(content: Any) -> str:
    """Normalize tool result content to string."""
    if content is None:
        return "No content provided"
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


# ── OpenAI → Anthropic response conversion ──────────────────────────────────


def convert_openai_to_anthropic_response(
    openai_response: dict, original_request: anthropic_models.ClaudeMessagesRequest
) -> Dict[str, Any]:
    """Convert an OpenAI Chat Completions response to Anthropic Messages format."""
    choices = openai_response.get("choices", [])
    if not choices:
        raise ValueError("No choices in OpenAI response")

    choice = choices[0]
    message = choice.get("message", {})

    content_blocks: List[Dict[str, Any]] = []

    # Text content
    text_content = message.get("content")
    if text_content is not None:
        content_blocks.append({"type": "text", "text": text_content})

    # Tool calls
    for tool_call in message.get("tool_calls", []) or []:
        if tool_call.get("type") == "function":
            func = tool_call.get("function", {})
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {"raw_arguments": func.get("arguments", "")}
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tool_call.get("id", f"tool_{uuid.uuid4().hex[:8]}"),
                    "name": func.get("name", ""),
                    "input": arguments,
                }
            )

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    # Map finish reason
    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "function_call": "tool_use",
    }.get(finish_reason, "end_turn")

    usage = openai_response.get("usage", {})
    return {
        "id": openai_response.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "model": original_request.model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }
