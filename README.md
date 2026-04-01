# Ollama Router

本地代理服务，自动轮换 ollama.com API Key，支持速率限制处理。

## 功能特性

- 🔄 **自动 Key 轮换** - 当触发速率限制时自动切换到下一个可用 Key
- ⏱️ **冷却时间管理** - 支持 session 限制（72h）和 rate limit（4h）两种冷却时间
- 📊 **Admin 管理面板** - Web UI 查看请求历史、Key 状态管理
- 📡 **实时日志流** - SSE 支持的实时日志查看和下载
- 🐳 **Docker 支持** - 完整的 Docker 和 docker-compose 部署方案

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

## 配置说明

### config.yaml 配置项

```yaml
listen: "127.0.0.1:11435"          # 监听地址
upstream: "https://ollama.com/v1"   # 上游 API 地址

# 代理设置（可选，用于公司网络）
proxy:
  http: "${http_proxy}"
  https: "${https_proxy}"
  no_proxy: "localhost,127.0.0.1"

# API Keys（推荐使用环境变量）
keys:
  - "${OLLAMA_API_KEY_1}"
  - "${OLLAMA_API_KEY_2}"

# 冷却时间设置
cooldown:
  session_limit_hours: 72    # 会话限制冷却时间
  rate_limit_hours: 4         # 速率限制冷却时间

# 管理面板配置
admin:
  username: "admin"
  password: "${ADMIN_PASSWORD:-changeme}"
  session_secret: "${ADMIN_SECRET:-change-me-to-random-secret}"

# 日志配置
logging:
  level: info
  file: "logs/ollama_router.log"
  max_size_mb: 10
  backup_count: 5
```

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OLLAMA_API_KEY_1..N` | ollama.com API Keys | 必填 |
| `ADMIN_PASSWORD` | Admin 面板密码 | `changeme` |
| `ADMIN_SECRET` | Session 签名密钥 | 随机生成 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FILE` | 日志文件路径 | `logs/ollama_router.log` |
| `HTTP_PROXY` | HTTP 代理 | - |
| `HTTPS_PROXY` | HTTPS 代理 | - |

## 使用方式

### API 调用

将原来指向 `https://ollama.com/v1` 的请求改为指向 `http://127.0.0.1:11435`：

```bash
# 原始请求
curl https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2", "messages": [{"role": "user", "content": "Hello"}]}'

# 通过 Ollama Router
curl http://127.0.0.1:11435/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2", "messages": [{"role": "user", "content": "Hello"}]}'
```

**注意**：不需要提供 `Authorization` 头，Router 会自动添加可用的 API Key。

### 配置 OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11435/v1",
    api_key="not-needed"  # Router 会自动处理
)

response = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Admin 管理面板

访问 `http://127.0.0.1:11435/admin` 进入管理面板：

- **Dashboard** - 查看请求统计、Key 状态
- **Keys** - 管理和查看 API Key 状态
- **History** - 查看请求历史记录
- **Logs** - 实时日志流和历史日志下载

**默认登录**：
- 用户名：`admin`
- 密码：在配置文件中设置，默认 `changeme`

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /health` | GET | 健康检查及 Key 状态 |
| `GET /metrics` | GET | Prometheus 格式指标 |
| `/{path:path}` | * | 代理到 ollama.com |
| `GET /admin` | GET | 管理面板首页 |
| `POST /admin/login` | POST | 登录认证 |
| `GET /admin/api/keys` | GET | 获取所有 Key 状态 |
| `POST /admin/api/keys` | POST | 添加新 Key |
| `DELETE /admin/api/keys/{key_id}` | DELETE | 删除 Key |
| `GET /admin/api/history` | GET | 获取请求历史 |
| `GET /admin/api/logs` | GET | 获取历史日志 |
| `GET /admin/api/logs/stream` | GET | SSE 实时日志流 |

## Docker 端口映射

| 端口 | 说明 |
|------|------|
| 11435 | HTTP API 服务 |

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff format .
ruff check .
```

## 目录结构

```
ollama_open_router/
├── ollama_router/           # 主代码
│   ├── router.py            # FastAPI 路由
│   ├── config.py            # 配置管理
│   ├── state.py             # Key 状态管理
│   ├── proxy.py             # 上游代理
│   ├── handler.py           # 速率限制处理
│   ├── retry.py             # 重试逻辑
│   └── admin/               # Admin 面板
├── templates/admin/         # Jinja2 模板
├── tests/                   # 测试文件
├── config.yaml.example      # 配置示例
├── config.docker.yaml       # Docker 配置
├── .env.example             # 环境变量示例
├── docker-compose.yml       # Docker Compose 配置
├── Dockerfile               # Docker 镜像构建
└── pyproject.toml           # Python 项目配置
```

## License

MIT