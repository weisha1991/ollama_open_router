# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ollama Router is a FastAPI-based local proxy for automatic ollama.com API key rotation with rate limit handling. It proxies requests to ollama.com and automatically rotates between multiple API keys when rate limits are hit.

## Commands

### Running the Server
```bash
python -m ollama_router
```

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_router.py

# Run a specific test function
pytest tests/test_router.py::test_router_health
```

### Installing Dependencies
```bash
# Production dependencies
pip install -e .

# Development dependencies (includes pytest)
pip install -e ".[dev]"
```

## Architecture

### Core Request Flow
1. **router.py** (`create_app`): Entry point that creates the FastAPI app
2. **KeySelector** (state.py): Selects the next available key using round-robin with cooldown tracking
3. **ProxyClient** (proxy.py): Forwards requests to upstream (ollama.com)
4. **RateLimitHandler** (handler.py): Detects rate limit responses and returns cooldown duration
5. **StateStore** (state.py): Persists key states to `state/key_states.json`

### Key Components

- **router.py**: Main FastAPI application with catch-all route `/{path:path}` that:
  - Selects an available key from KeySelector
  - Proxies the request upstream via ProxyClient
  - Handles rate limit detection and key cooldown
  - Retries with different keys on rate limit (max 3 retries)
  - Maintains in-memory request history for admin dashboard

- **state.py**: Manages key lifecycle:
  - `KeyState`: Tracks key status, cooldown expiry, and reason
  - `KeySelector`: Round-robin selection that skips keys in cooldown
  - `StateStore`: File-based persistence to `state/key_states.json`

- **handler.py**: Rate limit detection:
  - Detects 429 responses and specific error messages
  - Returns `CooldownInfo` with hours and reason
  - Distinguishes between session usage limits (72h default) and rate limits (4h default)

- **config.py**: YAML configuration with environment variable expansion:
  - Supports `${VAR_NAME}` syntax for secure key injection
  - Validates keys and warns on hardcoded values
  - `get_key_id()` hashes keys to 8-char IDs for logging

- **request_context.py**: Request ID tracking via contextvars:
  - `request_id_var`: Context variable for async-safe request ID propagation
  - `generate_request_id()`: Creates unique `req_XXXXXXXX` format IDs
  - `RequestIdFilter`: Logging filter that injects request_id into LogRecord

- **request_history.py**: In-memory request history for admin dashboard:
  - `RequestRecord`: Dataclass storing timestamp, request_id, method, path, status, key_id, latency
  - `RequestHistory`: Deque-based storage with configurable max size (default 1000)

- **retry.py**: Retry management with key switching:
  - `RetryResult`: Dataclass with response, success flag, attempts count, and error info
  - `RetryManager`: Handles retry loop (max 3 attempts) with automatic key rotation on rate limits

- **admin/**: Admin UI with session-based authentication:
  - `routes.py`: REST API for key management (add/remove/reset)
  - `views.py`: Jinja2 templates for dashboard/keys/history
  - `auth.py`: HMAC-based session tokens
  - `middleware.py`: Session validation dependency

### Configuration Structure (config.yaml)
```yaml
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - ${OLLAMA_API_KEY_1}  # Use env vars for security
  - ${OLLAMA_API_KEY_2}
cooldown:
  session_limit_hours: 72
  rate_limit_hours: 4
admin:
  username: "admin"
  password: "changeme"
  session_secret: "change-me-to-random-secret"
logging:
  level: info
  file: "logs/ollama_router.log"
  max_size_mb: 10
  backup_count: 5
```

### App State Pattern
The FastAPI app stores shared state on `app.state`:
- `app.state.config`: Config object
- `app.state.selector`: KeySelector instance
- `app.state.state_store`: StateStore instance
- `app.state.proxy`: ProxyClient instance
- `app.state.templates`: Jinja2Templates
- `app.state.request_history`: RequestHistory instance (Deque-based, max 1000 records)
- `app.state.retry_manager`: RetryManager instance for retry logic

### Endpoints
- `GET /health`: Health check with key status
- `GET /metrics`: Prometheus-style metrics
- `/{path:path}`: Catch-all proxy to upstream
- `/admin/*`: Admin UI (requires authentication)
- `/admin/api/*`: Admin REST API

## Testing Notes

Tests use `fastapi.testclient.TestClient` and mock configurations with test keys. The pytest configuration uses `asyncio_mode = "auto"`.
