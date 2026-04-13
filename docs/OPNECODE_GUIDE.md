# OpenCode 配置使用 Ollama Router 指导书

本文档指导如何在 OpenCode 中配置使用 Ollama Router 项目。

---

## 一、项目概述

**Ollama Router** 是一个本地代理服务，用于：
- 自动轮换 ollama.com API Key
- 处理速率限制（429）自动切换 Key
- 管理冷却时间（session limit 72h，rate limit 4h）
- 提供 Admin 管理面板监控 Key 状态

**服务地址**：`http://127.0.0.1:11435`

---

## 二、前置条件

### 1. 确保 Ollama Router 服务运行

检查服务状态：

```bash
curl http://127.0.0.1:11435/health
```

预期返回：

```json
{
  "status": "ok",
  "available_keys": 11,
  "total_keys": 12,
  ...
}
```

### 2. 确认 API Key 可用

访问 Admin 面板查看 Key 状态：

- 地址：`http://127.0.0.1:11435/admin`
- 用户名：`admin`
- 密码：`admin`（或你配置的密码）

---

## 三、配置步骤（推荐方案）

### 方案 A：修改 OpenCode 使用本地代理

#### 步骤 1：找到 OpenCode 配置文件

OpenCode 的模型配置通常在以下位置：

- **配置文件路径**：`~/.config/opencode/config.yaml` 或 `~/.opencode/config.yaml`
- **或环境变量**：`OPENAI_BASE_URL`

#### 步骤 2：修改 base_url 指向 Ollama Router

**方式一：环境变量（推荐）**

```bash
export OPENAI_BASE_URL="http://127.0.0.1:11435/v1"
export OPENAI_API_KEY="not-needed"  # Router 会自动处理
```

**方式二：配置文件**

编辑 `~/.config/opencode/config.yaml`：

```yaml
model:
  provider: openai
  base_url: "http://127.0.0.1:11435/v1"
  api_key: "not-needed"  # Router 会自动处理
  model: "glm-5"  # 或其他支持的模型
```

#### 步骤 3：测试连接

```bash
# 通过 OpenCode CLI 发送测试请求（如果支持）
# 或直接用 curl 测试
curl http://127.0.0.1:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

---

### 方案 B：在 OpenCode Session 中动态配置

如果 OpenCode 支持在对话中动态切换：

```
请使用以下配置：
- Base URL: http://127.0.0.1:11435/v1
- API Key: not-needed
- Model: glm-5
```

---

## 四、支持的模型

通过 Ollama Router 可以访问 ollama.com 上所有模型：

| 模型 | 说明 |
|------|------|
| `glm-5` | 默认模型，通用对话 |
| `glm-5.1` | 最新旗舰模型，长程任务更强 |
| `glm-4.7-flash` | 快速模型，免费 |
| 其他 | 查看 ollama.com 支持的模型列表 |

---

## 五、请求格式

Ollama Router 兼容 OpenAI API 格式：

### Chat Completions

```bash
curl http://127.0.0.1:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 100,
    "stream": false
  }'
```

### 流式响应

```bash
curl http://127.0.0.1:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5",
    "messages": [{"role": "user", "content": "Tell me a story"}],
    "stream": true
  }'
```

---

## 六、监控与调试

### 1. 查看 Key 使用情况

访问 Admin 面板：`http://127.0.0.1:11435/admin/keys`

可以看到：
- 当前可用的 Key 数量
- 正在使用的 Key（标记 `IN USE`）
- 冷却中的 Key 及剩余时间
- 禁用的 Key

### 2. 查看请求历史

访问：`http://127.0.0.1:11435/admin/history`

记录包含：
- 请求时间
- 使用的 Key ID
- 响应状态码
- 延迟时间

### 3. 实时日志

访问：`http://127.0.0.1:11435/admin/logs`

支持：
- 实时 SSE 日志流
- 按级别过滤（INFO/WARNING/ERROR）
- 下载历史日志

### 4. Health Check

```bash
curl http://127.0.0.1:11435/health | jq
```

返回完整的 Key 状态信息。

---

## 七、常见问题

### Q1：OpenCode 报错 "Connection refused"

**检查**：
1. Ollama Router 是否运行：`docker ps | grep ollama-router`
2. 端口是否正确：默认为 `11435`
3. 防火墙是否阻止本地连接

### Q2：请求返回 503 "No available API keys"

**原因**：所有 Key 都在冷却中

**解决**：
1. 等待冷却结束（Admin 面板查看剩余时间）
2. 或在 Admin 面板 Enable 更多 Key

### Q3：Key 被 Rate Limit 后多久恢复？

- **Session limit**：72 小时
- **Rate limit**：4 小时
- **Admin 手动禁用**：永久，需要手动 Enable

### Q4：如何添加新 Key？

访问 Admin 面板 → Keys → 输入新 Key → Add

或通过 API：

```bash
curl -X POST http://127.0.0.1:11435/admin/api/keys \
  -u admin:admin \
  -d "key=your-new-api-key"
```

---

## 八、API 端点速查

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/chat/completions` | POST | Chat API（OpenAI 兼容） |
| `/v1/models` | GET | 模型列表 |
| `/admin` | GET | 管理面板 |
| `/admin/api/keys` | GET | Key 列表 |
| `/admin/api/keys` | POST | 添加 Key |
| `/admin/api/keys/{id}/reset` | POST | 重置 Key 状态 |
| `/admin/api/keys/{id}/disable` | POST | 禁用 Key |
| `/admin/api/history` | GET | 请求历史 |
| `/admin/api/logs/stream` | GET | SSE 实时日志 |

---

## 九、最佳实践

1. **保持多个 Key 可用**：建议 10+ Key 轮换，避免单点故障
2. **定期检查 Admin 面板**：监控 Key 健康状态和冷却情况
3. **设置告警**：当可用 Key < 3 时发送通知（需要自行实现）
4. **避免超大 Token 请求**：单次请求 `max_tokens` 设置合理值（如 2000 以内）
5. **使用流式响应**：长对话用 `stream: true` 避免 timeout

---

## 十、故障排查流程

```
请求失败
    │
    ├─► 检查服务状态: curl http://127.0.0.1:11435/health
    │   └─► 503 → 所有 Key 冷却，等待恢复或添加新 Key
    │
    ├─► 检查 Key 状态: Admin 面板 /admin/keys
    │   ├─► disabled → 手动 Enable
    │   ├─► cooldown → 查看剩余时间
    │   └─► available → 继续排查
    │
    ├─► 检查日志: Admin 面板 /admin/logs
    │   └─► 查看错误信息和 request_id
    │
    └─► 检查上游: curl https://ollama.com/v1/models
        └─► 上游服务问题，等待恢复
```

---

## 十一、附录：完整配置示例

### Docker Compose 配置 (`docker-compose.yml`)

```yaml
version: "3.8"
services:
  ollama-router:
    build: .
    ports:
      - "11435:11435"
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
      - ./config.yaml:/app/config.yaml:ro
    env_file:
      - .env
    restart: unless-stopped
```

### 环境变量文件 (`.env`)

```bash
# API Keys（必须）
OLLAMA_API_KEY_1=your-api-key-1
OLLAMA_API_KEY_2=your-api-key-2
OLLAMA_API_KEY_3=your-api-key-3
# ... 添加更多

# Admin 密码（可选）
ADMIN_PASSWORD=admin
ADMIN_SESSION_SECRET=your-random-secret-here

# 代理（可选，公司网络）
HTTP_PROXY=http://your-proxy:80
HTTPS_PROXY=http://your-proxy:80
NO_PROXY=localhost,127.0.0.1
```

---

**文档版本**：v1.1
**更新日期**：2026-04-13
**项目仓库**：https://github.com/weisha1991/ollama_open_router