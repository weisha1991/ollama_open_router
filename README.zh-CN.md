<h1 align="center">Ollama Router</h1>

<p align="center">
  <strong>将多个 ollama.com API Key 汇聚到单一端点，自动轮换、永不中断。</strong>
</p>

<p align="center">
  <a href="https://github.com/weisha1991/ollama_open_router/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-127%20passing-brightgreen.svg" alt="127 Tests">
  <img src="https://img.shields.io/badge/API-OpenAI%20%7C%20Anthropic-purple.svg" alt="OpenAI & Anthropic API">
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#工具集成">工具集成</a> ·
  <a href="#配置说明">配置说明</a> ·
  <a href="#工作原理">工作原理</a> ·
  <a href="#管理面板">管理面板</a> ·
  <a href="#api-参考">API 参考</a>
</p>

<p align="center">
  🌐 <a href="README.md">English</a>
</p>

---

## 为什么需要 Ollama Router？

[ollama.com](https://ollama.com) 提供免费的 API Key，可以使用 GLM-5 等大语言模型。但每个 Key 都有使用限额——额度耗尽后，你的应用就会停止工作。

**Ollama Router 解决了这个问题**——它将多个 Key 汇聚到一个代理端点后面。当某个 Key 触发限额，自动切换到下一个——你的工具永远不会中断。

同时提供 **Anthropic Messages API 兼容层**，让 Claude Code、OpenCode 等工具可以直接通过代理连接。

## 功能特性

- **自动 Key 轮换** — 轮询选择 + 冷却追踪；遇到 429 自动切换下一个 Key
- **Anthropic + OpenAI 双 API** — 完整支持 `/v1/messages`（Anthropic）和 `/v1/chat/completions`（OpenAI），含流式传输
- **Claude Code 开箱即用** — 设置 `ANTHROPIC_BASE_URL` 即可连接
- **管理面板** — Web UI 监控 Key 状态、请求历史、实时日志
- **智能重试** — 失败时自动换 Key 重试，最多 3 次
- **Docker 优先** — 多阶段构建 + docker-compose，一条命令部署

## 快速开始

### Docker Compose（推荐）

```bash
git clone https://github.com/weisha1991/ollama_open_router.git
cd ollama_open_router
cp .env.example .env
# 编辑 .env 添加你的 ollama.com API Key
docker compose up -d
```

服务启动在 `http://127.0.0.1:11435`，无需其他配置。

### 从源码运行

```bash
git clone https://github.com/weisha1991/ollama_open_router.git
cd ollama_open_router
pip install -e .
cp config.yaml.example config.yaml
# 编辑 config.yaml 添加 API Key
python -m ollama_router
```

### 验证服务

```bash
curl http://127.0.0.1:11435/health
```

## 工具集成

### Claude Code

编辑 `~/.claude/settings.json`：

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

> 📖 详细配置见 [Claude Code 接入指南](docs/CLAUDE_CODE_GUIDE.md)。

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11435/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="glm-5.1",
    messages=[{"role": "user", "content": "你好"}]
)
```

### 其他 OpenAI 兼容工具

将工具的 `base_url` 指向 `http://127.0.0.1:11435/v1`，`api_key` 设置为任意非空字符串即可。路由器会自动处理 Key 选择。

## 配置说明

### config.yaml

```yaml
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"

proxy:                          # 可选 — 用于公司网络
  http: "${http_proxy}"
  https: "${https_proxy}"
  no_proxy: "localhost,127.0.0.1"

keys:
  - "${OLLAMA_API_KEY_1}"      # 建议使用环境变量
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

完整示例见 [config.yaml.example](config.yaml.example)。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OLLAMA_API_KEY_1..N` | ollama.com API Key | **必填** |
| `ADMIN_PASSWORD` | 管理面板密码 | `changeme` |
| `ADMIN_SECRET` | Session 签名密钥 | 随机生成 |
| `LOG_LEVEL` | 日志级别（`DEBUG`、`INFO`、`WARNING`、`ERROR`） | `INFO` |
| `HTTP_PROXY` / `HTTPS_PROXY` | 出站代理 | — |

### Docker 构建参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `BASE_IMAGE` | Python 基础镜像 | `python:3.10-slim` |
| `PIP_INDEX_URL` | pip 包索引 | `https://pypi.org/simple` |
| `HTTP_PROXY` / `HTTPS_PROXY` | 构建时代理 | — |

使用私有镜像仓库示例：

```bash
docker compose build \
  --build-arg BASE_IMAGE=registry.example.com/python:3.10-slim \
  --build-arg PIP_INDEX_URL=https://pypi.example.com/simple
```

## 工作原理

```
  Claude Code / OpenCode / SDK / curl
                 │
                 ▼
        Ollama Router (:11435)
         ┌───────┴───────┐
         │   Key Selector │  ← 轮询选择 + 冷却追踪
         └───────┬───────┘
                 │  绑定 Key，转发请求
                 ▼
           ollama.com/v1
                 │
       ┌──── 200 ────┐
       │              │
    返回响应      ┌─ 429 ──┐
    给客户端     │         │
              标记冷却   换 Key 重试（×3）
```

## 管理面板

访问 `http://127.0.0.1:11435/admin` 进入内置管理面板：

| 页面 | 说明 |
|------|------|
| **Dashboard** | 实时请求统计和 Key 健康概览 |
| **Keys** | 查看 Key 状态（可用 / 冷却中 / 已禁用），添加或移除 Key |
| **History** | 请求日志，含时间戳、Key ID、状态码、延迟 |
| **Logs** | 实时 SSE 日志流，支持级别过滤和日志下载 |

## API 参考

### 代理

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，含 Key 状态摘要 |
| `GET` | `/metrics` | Prometheus 格式指标 |
| `*` | `/{path:path}` | 透明代理到 ollama.com |

### Anthropic（Claude Code 兼容）

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/v1/messages` | Anthropic Messages API，支持流式和非流式 |
| `POST` | `/v1/messages/count_tokens` | Token 计数估算 |

Claude 模型名（如 `claude-sonnet-4-20250514`）会自动映射到默认上游模型。可通过客户端的 `ANTHROPIC_DEFAULT_*_MODEL` 环境变量覆盖。

### 管理

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/admin` | 管理面板 UI |
| `POST` | `/admin/login` | 登录认证 |
| `GET` | `/admin/api/keys` | 列出所有 Key 及状态 |
| `POST` | `/admin/api/keys` | 添加新 Key |
| `DELETE` | `/admin/api/keys/{key_id}` | 删除 Key |
| `POST` | `/admin/api/keys/{key_id}/disable` | 禁用 Key |
| `POST` | `/admin/api/keys/{key_id}/reset` | 重置 Key 冷却 |
| `GET` | `/admin/api/history` | 请求历史 |
| `GET` | `/admin/api/logs` | 历史日志 |
| `GET` | `/admin/api/logs/stream` | SSE 实时日志流 |

## 开发

```bash
pip install -e ".[dev]"
pytest                    # 127 个测试
ruff format .             # 格式化
ruff check .              # 代码检查
```

## 贡献

欢迎提交 [Issue](https://github.com/weisha1991/ollama_open_router/issues) 和 [Pull Request](https://github.com/weisha1991/ollama_open_router/pulls)。

## 许可证

[MIT](LICENSE) © DragonTensor
