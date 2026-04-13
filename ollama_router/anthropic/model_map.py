"""Model name pass-through for Anthropic API compatibility.

No server-side mapping is performed. The model name sent by the client
(e.g. via ANTHROPIC_DEFAULT_SONNET_MODEL env var) is passed through directly.
"""
