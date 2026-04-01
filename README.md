# Ollama Router

Local proxy for automatic ollama.com API key rotation with rate limit handling.

## Setup

1. Copy `config.yaml.example` to `config.yaml`
2. Add your API keys to `config.yaml`
3. Update OpenCode config: `~/.config/opencode/opencode.json`

## Running

```bash
python -m ollama_router
```

## Configuration

See `config.yaml.example` for all options.
