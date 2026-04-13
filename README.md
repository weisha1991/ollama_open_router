<h1 align="center">Ollama Router</h1>

<p align="center">
  <strong>Pool multiple ollama.com API keys behind a single endpoint with automatic rotation.</strong>
</p>

<p align="center">
  <a href="https://github.com/weisha1991/ollama_open_router/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-127%20passing-brightgreen.svg" alt="127 Tests">
  <img src="https://img.shields.io/badge/API-OpenAI%20%7C%20Anthropic-purple.svg" alt="OpenAI & Anthropic API">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#integrations">Integrations</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#admin-dashboard">Admin Dashboard</a> ·
  <a href="#api-reference">API Reference</a>
</p>

---

## Why Ollama Router?

[ollama.com](https://ollama.com) provides free API keys for language models like GLM-5, but each key has usage limits. When you hit the limit, your application stops working.

**Ollama Router solves this** by pooling multiple keys behind a single proxy endpoint. When one key gets rate-limited, it automatically rotates to the next — your tools keep running without interruption.

It also provides an **Anthropic Messages API compatibility layer**, so you can connect tools like Claude Code and OpenCode directly through the proxy.

## Features

- **Automatic Key Rotation** — Round-robin selection with automatic cooldown tracking; switches keys on 429 responses
- **Anthropic + OpenAI Dual API** — Full `/v1/messages` (Anthropic) and `/v1/chat/completions` (OpenAI) support with streaming
- **Claude Code Ready** — Works with Claude Code out of the box via `ANTHROPIC_BASE_URL`
- **Admin Dashboard** — Web UI for monitoring key status, request history, and real-time logs
- **Smart Retry** — Up to 3 retry attempts with automatic key switching on failures
- **Docker First** — Multi-stage Docker build with docker-compose for one-command deployment

## Quick Start

### Docker Compose

```bash
git clone https://github.com/weisha1991/ollama_open_router.git
cd ollama_open_router
cp .env.example .env
# Edit .env to add your ollama.com API keys
docker compose up -d
```

The proxy starts at `http://127.0.0.1:11435`. That's it.

### From Source

```bash
git clone https://github.com/weisha1991/ollama_open_router.git
cd ollama_open_router
pip install -e .
cp config.yaml.example config.yaml
# Edit config.yaml to add your API keys
python -m ollama_router
```

### Verify

```bash
curl http://127.0.0.1:11435/health
```

## Integrations

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-not-needed",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:11435",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "API_TIMEOUT_MS": "1800000"
  }
}
```

> 📖 See [Claude Code Setup Guide](docs/CLAUDE_CODE_GUIDE.md) for detailed instructions.

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11435/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="glm-5.1",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Any OpenAI-Compatible Tool

Point your tool's `base_url` to `http://127.0.0.1:11435/v1` and set any non-empty `api_key`. The router handles key selection automatically.

## Configuration

### config.yaml

```yaml
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"

proxy:                          # Optional — for corporate networks
  http: "${http_proxy}"
  https: "${https_proxy}"
  no_proxy: "localhost,127.0.0.1"

keys:
  - "${OLLAMA_API_KEY_1}"      # Use env vars for security
  - "${OLLAMA_API_KEY_2}"

cooldown:
  session_limit_hours: 72
  rate_limit_hours: 4

admin:
  username: "admin"
  password: "${ADMIN_PASSWORD:-changeme}"
  session_secret: "${ADMIN_SECRET:-change-me-to-random-secret}"

logging:
  level: info
  file: "logs/ollama_router.log"
  max_size_mb: 10
  backup_count: 5
```

See [config.yaml.example](config.yaml.example) for the full template.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_API_KEY_1..N` | ollama.com API keys | **Required** |
| `ADMIN_PASSWORD` | Admin dashboard password | `changeme` |
| `ADMIN_SECRET` | Session signing secret | Random |
| `LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `HTTP_PROXY` / `HTTPS_PROXY` | Outbound proxy | — |

### Docker Build Args

| Arg | Description | Default |
|-----|-------------|---------|
| `BASE_IMAGE` | Python base image | `python:3.10-slim` |
| `PIP_INDEX_URL` | pip package index | `https://pypi.org/simple` |
| `HTTP_PROXY` / `HTTPS_PROXY` | Build-time proxy | — |

Example with a private registry:

```bash
docker compose build \
  --build-arg BASE_IMAGE=registry.example.com/python:3.10-slim \
  --build-arg PIP_INDEX_URL=https://pypi.example.com/simple
```

## How It Works

```
  Claude Code / OpenCode / SDK / curl
                 │
                 ▼
        Ollama Router (:11435)
         ┌───────┴───────┐
         │   Key Selector │  ← Round-robin with cooldown tracking
         └───────┬───────┘
                 │  Attach key, forward request
                 ▼
           ollama.com/v1
                 │
       ┌──── 200 ────┐
       │              │
    Response      ┌─ 429 ──┐
    to client     │         │
              Mark key    Retry with
              cooldown    next key (×3)
```

## Admin Dashboard

Visit `http://127.0.0.1:11435/admin` to access the built-in management dashboard:

| Page | Description |
|------|-------------|
| **Dashboard** | Real-time request stats and key health overview |
| **Keys** | View key states (available / cooldown / disabled), add or remove keys |
| **History** | Request log with timestamps, key IDs, status codes, and latency |
| **Logs** | Real-time SSE log stream with level filtering and log download |

## API Reference

### Proxy

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check with key status summary |
| `GET` | `/metrics` | Prometheus-style metrics |
| `*` | `/{path:path}` | Transparent proxy to ollama.com |

### Anthropic (Claude Code Compatible)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/messages` | Anthropic Messages API — streaming and non-streaming |
| `POST` | `/v1/messages/count_tokens` | Token count estimation |

Claude model names (e.g. `claude-sonnet-4-20250514`) are automatically mapped to the default upstream model. Override with `ANTHROPIC_DEFAULT_*_MODEL` env vars on the client.

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin` | Dashboard UI |
| `POST` | `/admin/login` | Session login |
| `GET` | `/admin/api/keys` | List all keys with status |
| `POST` | `/admin/api/keys` | Add a new key |
| `DELETE` | `/admin/api/keys/{key_id}` | Remove a key |
| `POST` | `/admin/api/keys/{key_id}/disable` | Disable a key |
| `POST` | `/admin/api/keys/{key_id}/reset` | Reset key cooldown |
| `GET` | `/admin/api/history` | Request history |
| `GET` | `/admin/api/logs` | Historical logs |
| `GET` | `/admin/api/logs/stream` | SSE real-time log stream |

## Development

```bash
pip install -e ".[dev]"
pytest                    # 127 tests
ruff format .             # Format
ruff check .              # Lint
```

## Project Structure

```
ollama_router/
├── router.py              # FastAPI app, catch-all proxy route
├── config.py              # YAML config with env var expansion
├── proxy.py               # Upstream HTTP client (30min timeout)
├── retry.py               # Retry manager with key rotation
├── handler.py             # Rate limit detection
├── state.py               # Key state, cooldown, persistence
├── anthropic/             # Anthropic Messages API layer
│   ├── routes.py          #   /v1/messages endpoints
│   ├── converter.py       #   Anthropic ↔ OpenAI conversion
│   ├── stream.py          #   SSE stream conversion
│   ├── models.py          #   Pydantic models
│   └── model_map.py       #   Model name handling
├── admin/                 # Admin dashboard
│   ├── routes.py          #   REST API
│   ├── views.py           #   Jinja2 templates
│   ├── auth.py            #   HMAC session tokens
│   └── middleware.py      #   Session validation
└── templates/admin/       # HTML templates
```

## Contributing

Issues and pull requests are welcome at [GitHub](https://github.com/weisha1991/ollama_open_router).

## License

[MIT](LICENSE) © DragonTensor
