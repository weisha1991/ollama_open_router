"""Map Claude model names to ollama/upstream model names."""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger("ollama_router")

DEFAULT_MODEL_MAP: Dict[str, str] = {
    "claude-sonnet-4-20250514": "glm-5.1",
    "claude-sonnet-4-5-20250514": "glm-5.1",
    "claude-haiku-4-20250414": "glm-5",
    "claude-haiku-4-5-20250514": "glm-5",
    "claude-opus-4-20250514": "glm-5.1",
}


def map_model(
    claude_model: str,
    model_map: Optional[Dict[str, str]] = None,
    default: str = "glm-5.1",
) -> str:
    """Map a Claude model name to the upstream model name."""
    model_map = model_map or {}

    if claude_model in model_map:
        return model_map[claude_model]

    if claude_model in DEFAULT_MODEL_MAP:
        return DEFAULT_MODEL_MAP[claude_model]

    lower = claude_model.lower()
    if "haiku" in lower:
        return model_map.get("_haiku", "glm-5")
    if "sonnet" in lower:
        return model_map.get("_sonnet", "glm-5.1")
    if "opus" in lower:
        return model_map.get("_opus", "glm-5.1")

    logger.debug("model_map_fallback claude_model=%s default=%s", claude_model, default)
    return default
