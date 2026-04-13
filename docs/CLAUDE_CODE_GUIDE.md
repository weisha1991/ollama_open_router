# Claude Code 接入 Ollama Router 配置指南

本指南说明如何配置 Claude Code 通过 Ollama Router 使用 ollama.com 的免费 API Key。

## 前提条件

- Ollama Router 已部署并运行（默认 `http://127.0.0.1:11435`）
- 至少有一个可用的 ollama.com API Key

## 配置步骤

### 1. 编辑 `~/.claude/settings.json`

Claude Code 通过 `ANTHROPIC_DEFAULT_*_MODEL` 环境变量决定发送的模型名。设置这些变量后，模型名会直接透传到 ollama.com，无需服务端映射。

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-not-needed",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:11435",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "API_TIMEOUT_MS": "1800000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_ENABLE_TELEMETRY": "0"
  }
}
```

### 2. 跳过首次引导

编辑 `~/.claude.json`：

```json
{
  "hasCompletedOnboarding": true
}
```

### 3. 启动使用

```bash
cd your-project
claude
```

输入 `/status` 可以查看当前使用的模型。

## 环境变量说明

| 变量 | 值 | 说明 |
|------|------|------|
| `ANTHROPIC_AUTH_TOKEN` | `sk-not-needed` | 非空即可，代理自行管理真实 Key |
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:11435` | Ollama Router 地址 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `glm-5` | 轻量模型，用于后台任务 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `glm-5.1` | 主力编码模型 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `glm-5.1` | 高阶模型（Plan Mode 等） |
| `API_TIMEOUT_MS` | `1800000` | 30 分钟超时，编码任务需要 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | 禁用非必要网络请求 |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `0` | 关闭遥测 |

## 模型选择参考

| Claude Code 层级 | 推荐模型 | 说明 |
|---|---|---|
| Haiku | `glm-5` | 响应快，适合后台任务 |
| Sonnet | `glm-5.1` | 主力模型，编码/调试 |
| Opus | `glm-5.1` | 高阶推理（和 Sonnet 共用最强模型） |

其他 ollama.com 支持的模型也可以使用，如 `glm-4.7-flash`、`glm-4.5-air` 等。

## 验证代理是否工作

```bash
# 测试 Anthropic Messages API 端点
curl -X POST http://127.0.0.1:11435/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "glm-5.1",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 测试 Token 计数端点
curl -X POST http://127.0.0.1:11435/v1/messages/count_tokens \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.1",
    "messages": [{"role": "user", "content": "Hello world"}]
  }'
```

## 模型名处理规则

Ollama Router 对 Anthropic 请求的模型名处理如下：

1. **客户端映射的模型名**（如 `glm-5.1`）→ 直接透传到 ollama.com
2. **Claude 原始模型名**（如 `claude-sonnet-4-20250514`、`claude-sonnet-4.6`）→ 自动 fallback 到默认上游模型

建议始终通过 `ANTHROPIC_DEFAULT_*_MODEL` 设置目标模型，避免不必要的 fallback。

## 常见问题

### Claude Code 启动后一直转圈

- 检查 Ollama Router 是否运行：`curl http://127.0.0.1:11435/health`
- 检查 API Key 是否可用：在 Admin 面板 `http://127.0.0.1:11435/admin` 查看

### 模型响应很慢或超时

- 确认设置了 `API_TIMEOUT_MS: "1800000"`
- 检查 Admin 面板中 Key 是否进入 cooldown
- 尝试降低模型（如 Sonnet → Haiku）

### 配置修改后不生效

- 关闭所有 Claude Code 窗口
- 打开新的终端窗口重新启动 `claude`

### 如何查看实际使用的模型

在 Claude Code 中输入 `/status` 查看当前模型状态。
