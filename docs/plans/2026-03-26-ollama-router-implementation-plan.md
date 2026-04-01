# Ollama Router Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local proxy service that automatically rotates between multiple ollama.com API keys to handle rate limits and usage quotas.

**Architecture:** Python-based HTTP proxy that presents an OpenAI-compatible API endpoint, manages key rotation, handles 429 errors with cooldown tracking, and forwards requests through corporate proxies to ollama.com.

**Tech Stack:** Python 3.10+, FastAPI, httpx, PyYAML

---

## Task 1: Project Scaffolding

**Files:**
- Create: `ollama_router/__init__.py`
- Create: `ollama_router/config.py`
- Create: `ollama_router/state.py`
- Create: `ollama_router/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `tests/test_state.py`
- Create: `pyproject.toml`
- Create: `config.yaml.example`

**Step 1: Create project structure and pyproject.toml**

Run:
```bash
mkdir -p ollama_router tests state
touch ollama_router/__init__.py tests/__init__.py
```

Create `pyproject.toml`:
```toml
[project]
name = "ollama-router"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100.0",
    "httpx>=0.25.0",
    "pyyaml>=6.0",
    "uvicorn>=0.24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-httpx>=0.28.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 2: Create config.yaml.example**

```yaml
listen: "127.0.0.1:11435"

upstream: "https://ollama.com/v1"

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
```

**Step 3: Create tests/test_config.py**

```python
import os
import pytest
from ollama_router.config import Config, load_config

def test_config_dataclass():
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2"],
        cooldown_session_hours=72,
        cooldown_rate_hours=4,
    )
    assert config.listen == "127.0.0.1:11435"
    assert config.upstream == "https://ollama.com/v1"
    assert len(config.keys) == 2

def test_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - "test_key_1"
  - "test_key_2"
cooldown:
  session_limit_hours: 72
  rate_limit_hours: 4
""")
    config = load_config(str(config_file))
    assert config.listen == "127.0.0.1:11435"
    assert len(config.keys) == 2
```

**Step 4: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: ImportError (modules don't exist yet)

**Step 5: Implement minimal config.py**

```python
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Config:
    listen: str
    upstream: str
    keys: list[str]
    cooldown_session_hours: int = 72
    cooldown_rate_hours: int = 4
    proxy_http: str | None = None
    proxy_https: str | None = None
    proxy_no_proxy: str | None = None

def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    
    keys = data.get("keys", [])
    keys = [k for k in keys if k]  # Filter None/empty
    
    return Config(
        listen=data.get("listen", "127.0.0.1:11435"),
        upstream=data.get("upstream", "https://ollama.com/v1"),
        keys=keys,
        cooldown_session_hours=data.get("cooldown", {}).get("session_limit_hours", 72),
        cooldown_rate_hours=data.get("cooldown", {}).get("rate_limit_hours", 4),
    )
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding with config module"
```

---

## Task 2: State Management

**Files:**
- Create: `ollama_router/state.py`
- Create: `tests/test_state.py`

**Step 1: Write failing test for KeyState dataclass**

```python
from ollama_router.state import KeyState, KeyStatus, StateStore

def test_key_state_available():
    state = KeyState(
        key="test_key",
        status=KeyStatus.AVAILABLE,
        cooldown_until=None,
        reason=None
    )
    assert state.status == KeyStatus.AVAILABLE
    assert state.is_available() is True

def test_key_state_cooldown():
    from datetime import datetime, timezone, timedelta
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    state = KeyState(
        key="test_key",
        status=KeyStatus.COOLDOWN,
        cooldown_until=future,
        reason="session_usage_limit"
    )
    assert state.status == KeyStatus.COOLDOWN
    assert state.is_available() is False

def test_state_store_persistence(tmp_path):
    store = StateStore(state_dir=str(tmp_path))
    store.keys = [
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(key="key2", status=KeyStatus.COOLDOWN, cooldown_until=datetime.now(timezone.utc) + timedelta(hours=1), reason="rate_limit"),
    ]
    store.save()
    
    store2 = StateStore(state_dir=str(tmp_path))
    store2.load()
    assert len(store2.keys) == 2
    assert store2.keys[1].status == KeyStatus.COOLDOWN
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: ImportError (state module doesn't exist)

**Step 3: Implement state.py**

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path

class KeyStatus(Enum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"

@dataclass
class KeyState:
    key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    cooldown_until: datetime | None = None
    reason: str | None = None
    
    def is_available(self) -> bool:
        if self.status == KeyStatus.AVAILABLE:
            return True
        if self.cooldown_until and datetime.now(timezone.utc) > self.cooldown_until:
            self.status = KeyStatus.AVAILABLE
            self.cooldown_until = None
            return True
        return False

@dataclass
class StateStore:
    state_dir: str
    keys: list[KeyState] = field(default_factory=list)
    current_index: int = 0
    
    def save(self):
        path = Path(self.state_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "keys": [
                {
                    "key": k.key,
                    "status": k.status.value,
                    "cooldown_until": k.cooldown_until.isoformat() if k.cooldown_until else None,
                    "reason": k.reason,
                }
                for k in self.keys
            ],
            "current_index": self.current_index,
        }
        
        with open(path / "key_states.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def load(self):
        path = Path(self.state_dir) / "key_states.json"
        if not path.exists():
            return
        
        with open(path) as f:
            data = json.load(f)
        
        self.keys = [
            KeyState(
                key=k["key"],
                status=KeyStatus(k["status"]),
                cooldown_until=datetime.fromisoformat(k["cooldown_until"]) if k["cooldown_until"] else None,
                reason=k.get("reason"),
            )
            for k in data.get("keys", [])
        ]
        self.current_index = data.get("current_index", 0)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add state management module"
```

---

## Task 3: Key Selector

**Files:**
- Modify: `ollama_router/state.py` (add KeySelector class)
- Create: `tests/test_selector.py`

**Step 1: Write failing test**

```python
from ollama_router.state import KeySelector, KeyState, KeyStatus

def test_selector_polling():
    selector = KeySelector([
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
        KeyState(key="key3", status=KeyStatus.AVAILABLE),
    ])
    
    assert selector.select().key == "key1"
    assert selector.select().key == "key2"
    assert selector.select().key == "key3"
    assert selector.select().key == "key1"  # Wraps around

def test_selector_skips_cooldown():
    from datetime import datetime, timezone, timedelta
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    
    selector = KeySelector([
        KeyState(key="key1", status=KeyStatus.COOLDOWN, cooldown_until=future, reason="rate_limit"),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
    ])
    
    result = selector.select()
    assert result.key == "key2"

def test_selector_all_cooldown_returns_none():
    from datetime import datetime, timezone, timedelta
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    
    selector = KeySelector([
        KeyState(key="key1", status=KeyStatus.COOLDOWN, cooldown_until=future, reason="rate_limit"),
    ])
    
    result = selector.select()
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_selector.py -v`
Expected: ImportError (KeySelector doesn't exist)

**Step 3: Implement KeySelector in state.py**

```python
class KeySelector:
    def __init__(self, keys: list[KeyState]):
        self.keys = keys
        self.index = 0
    
    def select(self) -> KeyState | None:
        if not self.keys:
            return None
        
        available_keys = [k for k in self.keys if k.is_available()]
        if not available_keys:
            return None
        
        start_index = self.index % len(self.keys)
        for i in range(len(self.keys)):
            idx = (start_index + i) % len(self.keys)
            if self.keys[idx].is_available():
                self.index = idx
                return self.keys[idx]
        
        return None
    
    def mark_cooldown(self, key: str, cooldown_hours: int, reason: str):
        from datetime import timedelta
        for k in self.keys:
            if k.key == key:
                k.status = KeyStatus.COOLDOWN
                k.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)
                k.reason = reason
                break
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_selector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add key selector with polling"
```

---

## Task 4: Request Proxy

**Files:**
- Create: `ollama_router/proxy.py`
- Create: `tests/test_proxy.py`

**Step 1: Write failing test**

```python
import httpx
import pytest
from ollama_router.proxy import ProxyClient

@pytest.mark.asyncio
async def test_proxy_forwards_request(httpx_mock):
    httpx_mock.add_response(
        status_code=200,
        json={"choices": [{"message": {"content": "hello"}}]}
    )
    
    client = ProxyClient(upstream="https://ollama.com/v1")
    response = await client.forward(
        method="POST",
        path="/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json_data={"model": "glm-4.7:cloud", "messages": [{"role": "user", "content": "hi"}]}
    )
    
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"

@pytest.mark.asyncio
async def test_proxy_handles_429(httpx_mock):
    httpx_mock.add_response(
        status_code=429,
        json={"error": "rate limit exceeded"}
    )
    
    client = ProxyClient(upstream="https://ollama.com/v1")
    response = await client.forward(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        json_data={}
    )
    
    assert response.status_code == 429
    assert "rate limit" in response.json()["error"].lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_proxy.py -v`
Expected: ImportError (ProxyClient doesn't exist)

**Step 3: Implement proxy.py**

```python
import httpx
from typing import Any

class ProxyClient:
    def __init__(
        self,
        upstream: str,
        proxy_http: str | None = None,
        proxy_https: str | None = None,
    ):
        self.upstream = upstream
        self.client = httpx.AsyncClient(
            proxy=proxy_https or proxy_http,
            timeout=60.0,
        )
    
    async def forward(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        json_data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self.upstream}{path}"
        return await self.client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
        )
    
    async def close(self):
        await self.client.aclose()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_proxy.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add request proxy client"
```

---

## Task 5: Rate Limit Handler

**Files:**
- Create: `ollama_router/handler.py`
- Create: `tests/test_handler.py`

**Step 1: Write failing test**

```python
import httpx
from ollama_router.handler import RateLimitHandler

def test_detect_session_limit():
    handler = RateLimitHandler(
        cooldown_session_hours=72,
        cooldown_rate_hours=4
    )
    
    response = httpx.Response(
        429,
        json={"error": "you (user) have reached your session usage limit..."}
    )
    
    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 72
    assert cooldown.reason == "session_usage_limit"

def test_detect_rate_limit():
    handler = RateLimitHandler(
        cooldown_session_hours=72,
        cooldown_rate_hours=4
    )
    
    response = httpx.Response(
        429,
        json={"error": "too many requests, rate limit exceeded"}
    )
    
    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 4
    assert cooldown.reason == "rate_limit"

def test_no_cooldown_on_success():
    handler = RateLimitHandler()
    
    response = httpx.Response(200, json={"choices": []})
    
    cooldown = handler.detect_cooldown(response)
    assert cooldown is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_handler.py -v`
Expected: ImportError

**Step 3: Implement handler.py**

```python
from dataclasses import dataclass
import httpx

@dataclass
class CooldownInfo:
    hours: int
    reason: str

class RateLimitHandler:
    def __init__(self, cooldown_session_hours: int = 72, cooldown_rate_hours: int = 4):
        self.cooldown_session_hours = cooldown_session_hours
        self.cooldown_rate_hours = cooldown_rate_hours
    
    def detect_cooldown(self, response: httpx.Response) -> CooldownInfo | None:
        if response.status_code != 429:
            return None
        
        try:
            error_data = response.json()
            error_message = error_data.get("error", "")
        except Exception:
            error_message = ""
        
        error_lower = error_message.lower()
        
        if "session usage limit" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_session_hours,
                reason="session_usage_limit"
            )
        
        if "rate limit" in error_lower or "too many requests" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_rate_hours,
                reason="rate_limit"
            )
        
        return CooldownInfo(hours=self.cooldown_session_hours, reason="unknown")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_handler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add rate limit handler"
```

---

## Task 6: Main Router Application

**Files:**
- Create: `ollama_router/router.py`
- Create: `tests/test_router.py`

**Step 1: Write failing test**

```python
import pytest
from fastapi.testclient import TestClient
from ollama_router.router import create_app
from ollama_router.config import Config

def test_router_health():
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
    )
    app = create_app(config)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router.py -v`
Expected: ImportError

**Step 3: Implement router.py**

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import httpx

from ollama_router.config import Config
from ollama_router.handler import RateLimitHandler
from ollama_router.proxy import ProxyClient
from ollama_router.state import KeySelector, KeyState, KeyStatus, StateStore

def create_app(config: Config) -> FastAPI:
    app = FastAPI()
    
    state_store = StateStore(state_dir="state")
    state_store.keys = [KeyState(key=k) for k in config.keys]
    state_store.load()
    
    selector = KeySelector(state_store.keys)
    handler = RateLimitHandler(
        cooldown_session_hours=config.cooldown_session_hours,
        cooldown_rate_hours=config.cooldown_rate_hours,
    )
    proxy = ProxyClient(
        upstream=config.upstream,
        proxy_http=config.proxy_http,
        proxy_https=config.proxy_https,
    )
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "available_keys": sum(1 for k in selector.keys if k.is_available())}
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    async def proxy_chat(path: str, request: Request):
        selected_key = selector.select()
        if selected_key is None:
            return JSONResponse(
                status_code=503,
                content={"error": "No available API keys. All keys are in cooldown."}
            )
        
        headers = dict(request.headers)
        headers["Authorization"] = f"Bearer {selected_key.key}"
        
        body = await request.json()
        
        response = await proxy.forward(
            method=request.method,
            path=f"/{path}",
            headers=headers,
            json_data=body,
        )
        
        cooldown_info = handler.detect_cooldown(response)
        if cooldown_info:
            selector.mark_cooldown(selected_key.key, cooldown_info.hours, cooldown_info.reason)
            state_store.save()
            return JSONResponse(
                status_code=429,
                content=response.json()
            )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    
    @app.on_event("shutdown")
    async def shutdown():
        state_store.save()
        await proxy.close()
    
    return app

def main():
    import uvicorn
    from ollama_router.config import load_config
    
    config = load_config("config.yaml")
    uvicorn.run(create_app(config), host="127.0.0.1", port=11435)

if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add main router application"
```

---

## Task 7: CLI Entry Point

**Files:**
- Create: `ollama_router/__main__.py`
- Create: `scripts/run.sh` (optional helper)

**Step 1: Create __main__.py**

```python
from ollama_router.router import main

if __name__ == "__main__":
    main()
```

**Step 2: Test CLI**

Run: `python -m ollama_router --help` (or implement argparser)
Expected: Help output

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: add CLI entry point"
```

---

## Task 8: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test with mocked ollama.com**

```python
import pytest
from fastapi.testclient import TestClient
from ollama_router.router import create_app
from ollama_router.config import Config

def test_integration_key_rotation(httpx_mock):
    httpx_mock.add_response(
        status_code=429,
        json={"error": "rate limit exceeded"}
    )
    httpx_mock.add_response(
        status_code=200,
        json={"choices": [{"message": {"content": "success"}}]}
    )
    
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2"],
        cooldown_rate_hours=4,
    )
    app = create_app(config)
    client = TestClient(app)
    
    response1 = client.post("/v1/chat/completions", json={
        "model": "glm-4.7:cloud",
        "messages": [{"role": "user", "content": "hello"}]
    })
    
    assert response1.status_code == 429
```

**Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`

**Step 3: Commit**

```bash
git add -A && git commit -m "test: add integration tests"
```

---

## Task 9: Documentation

**Files:**
- Create: `README.md`

**Step 1: Create README**

```markdown
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
```

**Step 2: Commit**

```bash
git add -A && git commit -m "docs: add README"
```

---

## Execution Options

**Plan complete and saved to `docs/plans/2026-03-26-ollama-router-implementation-plan.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
