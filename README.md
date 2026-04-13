# Ollama Router

A local proxy for [ollama.com](https://ollama.com) with automatic API key rotation, rate limit handling, and **Claude Code / OpenCode compatibility**.

Ollama.com provides free API keys with usage limits. Ollama Router pools multiple keys behind a single endpoint, automatically rotating on rate limits — so your tools never stop working.

## Features

- 🔄 **Automatic Key Rotation** — Seamlessly switches to the next available key on rate limit (429)
- ⏱️ **Cooldown Management** — Tracks session limits (configurable) and rate limits per key
- 🤖 **Claude Code Compatible** — Full Anthropic Messages API (`/v1/messages`) support with streaming, tool use, and model passthrough
- 📡 **OpenAI API Compatible** — Transparent proxy to `/v1/chat/completions` and all upstream endpoints
- 📊 **Admin Dashboard** — Web UI for key status, request history, real-time logs, and key management
- 🐳 **Docker Ready** — Complete Docker and docker-compose deployment with multi-stage build

## Quick Start

### Docker Compose (Recommended)

```bash
# 1. Clone and configure
git clone https://github.com/weisha1991/ollama_open_router.git
cd ollama_open_router
cp .env.example .env

# 2. Edit .env — add your ollama.com API keys
# OLLAMA_API_KEY_1=your-key-1
# OLLAMA_API_KEY_2=your-key-2

# 3. Start
docker compose up -d
```

Service runs at `http://127.0.0.1:11435`.

### Local Install

```bash
pip install -e .
cp config.yaml.example config.yaml
# Edit config.yaml to add keys
python -m ollama_router
```

## Usage

### With Claude Code

Edit `~/.claude/settings.json`:

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

> See [docs/CLAUDE_CODE_GUIDE.md](docs/CLAUDE_CODE_GUIDE.md) for detailed setup instructions.

### With OpenAI SDK

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

### With curl

```bash
# OpenAI Chat Completions
curl http://127.0.0.1:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-5.1", "messages": [{"role": "user", "content": "Hello"}]}'

# Anthropic Messages API (for Claude Code)
curl http://127.0.0.1:11435/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "glm-5.1", "max_tokens": 100, "messages": [{"role": "user", "content": "Hello"}]}'
```

## 快速开始

### 方式一：本地运行

```bash
# 1. 安装依赖
pip install -e .

# 2. 复制配置文件
cp config.yaml.example config.yaml

# 3. 编辑配置文件，添加 API Keys
# keys:
#   - "${OLLAMA_API_KEY_1}"
#   - "${OLLAMA_API_KEY_2}"

# 4. 设置环境变量
export OLLAMA_API_KEY_1=your-api-key-1
export OLLAMA_API_KEY_2=your-api-key-2

# 5. 启动服务
python -m ollama_router
```

服务将在 `http://127.0.0.1:11435` 启动。

### 方式二：Docker Compose（推荐）

```bash
# 1. 复制环境变量文件
cp .env.example .env

# 2. 编辑 .env 文件，添加 API Keys
# OLLAMA_API_KEY_1=your-api-key-1
# OLLAMA_API_KEY_2=your-api-key-2

# 3. 创建 config.docker.yaml 符号链接（或直接使用）
cp config.docker.yaml config.yaml

# 4. 启动服务
docker-compose up -d

# 5. 查看日志
docker-compose logs -f
```

### 方式三：Docker 单独构建

```bash
# 构建镜像
docker build -t ollama-router .

# 运行容器
docker run -d \
  --name ollama-router \
  -p 11435:11435 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --env-file .env \
  ollama-router
```

## Configuration

### config.yaml

```yaml
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"

# Optional proxy (for corporate networks)
proxy:
  http: "${http_proxy}"
  https: "${https_proxy}"
  no_proxy: "localhost,127.0.0.1"

keys:
  - "${OLLAMA_API_KEY_1}"
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

See [config.yaml.example](config.yaml.example) for a full example.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_API_KEY_1..N` | ollama.com API keys | Required |
| `ADMIN_PASSWORD` | Admin dashboard password | `changeme` |
| `ADMIN_SECRET` | Session signing secret | Random |
| `LOG_LEVEL` | Log level | `INFO` |
| `HTTP_PROXY` / `HTTPS_PROXY` | Outbound proxy | — |

## API Endpoints

### Proxy Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | Health check with key status |
| `GET /metrics` | GET | Prometheus-style metrics |
| `/{path:path}` | * | Proxy to ollama.com (OpenAI API) |

### Anthropic Compatible Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /v1/messages` | POST | Anthropic Messages API (streaming & non-streaming) |
| `POST /v1/messages/count_tokens` | POST | Token count estimation |

Claude model names (e.g. `claude-sonnet-4-20250514`) are automatically mapped to the default upstream model. To use a specific upstream model, set it via `ANTHROPIC_DEFAULT_*_MODEL` env vars on the client side.

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin` | GET | Admin dashboard |
| `POST /admin/login` | POST | Login |
| `GET /admin/api/keys` | GET | List all keys with status |
| `POST /admin/api/keys` | POST | Add a new key |
| `DELETE /admin/api/keys/{key_id}` | DELETE | Remove a key |
| `POST /admin/api/keys/{key_id}/disable` | POST | Disable a key |
| `POST /admin/api/keys/{key_id}/reset` | POST | Reset key cooldown |
| `GET /admin/api/history` | GET | Request history |
| `GET /admin/api/logs` | GET | Historical logs |
| `GET /admin/api/logs/stream` | GET | SSE real-time log stream |

## Admin Dashboard

Visit `http://127.0.0.1:11435/admin` for the management dashboard:

- **Dashboard** — Request stats and key overview
- **Keys** — View/manage key states (available, cooldown, disabled)
- **History** — Request history with latency and key info
- **Logs** — Real-time log stream and download

## How It Works

```
Claude Code / OpenCode / curl
        │
        ▼
  Ollama Router (127.0.0.1:11435)
   ┌────┴────┐
   │  Key    │  Round-robin selection
   │ Selector│  Skip keys in cooldown
   └────┬────┘
        │  Attach API key → forward
        ▼
   ollama.com/v1
        │
   429? ─┼─→ Mark cooldown, retry with next key (max 3)
   200? ─┼─→ Return response
        │
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (127 tests)
pytest

# Format
ruff format .
ruff check .
```

## Project Structure

```
ollama_router/
├── router.py              # FastAPI app, catch-all proxy route
├── config.py              # YAML config with env var expansion
├── proxy.py               # Upstream HTTP client
├── retry.py               # Retry with key rotation
├── handler.py             # Rate limit detection
├── state.py               # Key state management & persistence
├── request_context.py     # Request ID tracking (contextvars)
├── request_history.py     # In-memory request history
├── anthropic/             # Anthropic Messages API compatibility layer
│   ├── routes.py          # /v1/messages, /v1/messages/count_tokens
│   ├── converter.py       # Anthropic ↔ OpenAI format conversion
│   ├── stream.py          # SSE stream conversion
│   ├── models.py          # Pydantic models
│   └── model_map.py       # Claude model name handling
├── admin/                 # Admin UI
│   ├── routes.py          # REST API
│   ├── views.py           # Jinja2 templates
│   ├── auth.py            # HMAC session tokens
│   └── middleware.py      # Session validation
templates/admin/           # Jinja2 HTML templates
tests/                     # 127 tests
```

## License

MIT