# OpenAI Streaming Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add true streaming to the OpenAI-compatible proxy path while keeping retries limited to pre-start setup and making per-key streaming safe under concurrent multi-user load.

**Architecture:** Keep the existing FastAPI catch-all route and shared `httpx.AsyncClient`, but split streaming into its own setup flow. Add transient stream lease tracking to the selector, add a streaming setup/retry helper in the retry layer, and branch the router so `stream=true` requests return a real `StreamingResponse` backed by upstream byte iteration.

**Tech Stack:** Python 3.10+, FastAPI, Starlette `StreamingResponse`, httpx `AsyncClient`/`stream`, `fastapi.testclient.TestClient`, `pytest`, `unittest.mock`

---

## References

- Spec: `docs/superpowers/specs/2026-06-11-openai-streaming-concurrency-design.md`
- Existing Anthropic streaming path: `ollama_router/anthropic/routes.py`, `ollama_router/anthropic/stream.py`
- Existing generic proxy path: `ollama_router/router.py`
- Use `@superpowers:test-driven-development` for each implementation task.

## File Structure

```text
ollama_router/
├── state.py              # MODIFY: transient stream occupancy and bounded lease selection
├── proxy.py              # MODIFY: streaming request helper and explicit client limits
├── retry.py              # MODIFY: pre-start streaming setup/retry flow
└── router.py             # MODIFY: branch OpenAI-compatible stream=true requests to StreamingResponse

tests/
├── test_state.py         # MODIFY: stream lease and least-loaded selector tests
├── test_proxy.py         # MODIFY: streaming client helper tests
├── test_retry.py         # MODIFY: pre-start streaming retry tests
└── test_router.py        # MODIFY: OpenAI-compatible streaming route behavior tests
```

## File Responsibilities

- `ollama_router/state.py`
  - Own transient per-key stream occupancy.
  - Add bounded lease acquire/release behavior for streaming requests.
  - Keep persistent cooldown/disabled state unchanged.
- `ollama_router/proxy.py`
  - Add a streaming request entrypoint built on `httpx.AsyncClient.stream(...)`.
  - Configure connection-pool limits appropriate for concurrent long-lived streams.
- `ollama_router/retry.py`
  - Add a streaming setup helper that retries only before downstream bytes begin.
  - Reuse current cooldown/disable classification for pre-start failures.
- `ollama_router/router.py`
  - Detect `stream=true` JSON requests on the generic proxy path.
  - Return a real `StreamingResponse` with a prefetched first chunk and safe headers.
- `tests/test_state.py`
  - Lock in stream lease semantics and least-loaded selection.
- `tests/test_proxy.py`
  - Lock in the streaming helper surface.
- `tests/test_retry.py`
  - Lock in pre-start retry semantics.
- `tests/test_router.py`
  - Lock in the OpenAI-compatible streaming branch and non-stream regressions.

---

### Task 1: Add Selector Lease Tests

**Files:**
- Modify: `tests/test_state.py`
- Modify: `ollama_router/state.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_stream_lease_marks_key_busy_until_released():
    keys = [KeyState(key="key1"), KeyState(key="key2")]
    selector = KeySelector(keys=keys, max_concurrent_streams_per_key=2)

    lease = selector.acquire_stream_lease()

    assert lease is not None
    leased_key = lease.key
    assert selector.get_active_streams(leased_key) == 1

    selector.release_stream_lease(leased_key)
    assert selector.get_active_streams(leased_key) == 0


def test_stream_selection_skips_keys_at_capacity():
    keys = [KeyState(key="key1"), KeyState(key="key2")]
    selector = KeySelector(keys=keys, max_concurrent_streams_per_key=1)

    first = selector.acquire_stream_lease()
    second = selector.acquire_stream_lease()
    third = selector.acquire_stream_lease()

    assert first is not None
    assert second is not None
    assert first.key != second.key
    assert third is None


def test_stream_selection_prefers_lower_load():
    keys = [KeyState(key="key1"), KeyState(key="key2"), KeyState(key="key3")]
    selector = KeySelector(keys=keys, max_concurrent_streams_per_key=3)

    selector.acquire_stream_lease(preferred_key="key1")
    selector.acquire_stream_lease(preferred_key="key1")
    selector.acquire_stream_lease(preferred_key="key2")

    selected = selector.acquire_stream_lease()

    assert selected is not None
    assert selected.key == "key3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy python -m pytest tests/test_state.py -k "stream_lease or capacity or lower_load" -v`
Expected: FAIL because streaming lease APIs do not exist yet.

- [ ] **Step 3: Implement transient stream lease support in `state.py`**

Implementation notes:
- Keep `active_streams` transient only; do not persist it in `StateStore.save()`.
- Add explicit APIs for acquire/release/get-active-count instead of reusing `select()`.
- Preserve existing non-stream `select()` behavior for current callers.
- Use simple atomic mutation in selector methods; do not introduce distributed state.

- [ ] **Step 4: Run the focused state tests**

Run: `rtk proxy python -m pytest tests/test_state.py -k "stream_lease or capacity or lower_load" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add tests/test_state.py ollama_router/state.py
rtk git commit -m "test: cover streaming key lease selection"
```

---

### Task 2: Add Streaming Proxy And Retry Tests

**Files:**
- Modify: `tests/test_proxy.py`
- Modify: `tests/test_retry.py`
- Modify: `ollama_router/proxy.py`
- Modify: `ollama_router/retry.py`

- [ ] **Step 1: Write the failing proxy test**

```python
@pytest.mark.asyncio
async def test_proxy_stream_opens_httpx_stream(monkeypatch):
    client = ProxyClient(upstream="https://ollama.com/v1")

    class DummyContext:
        async def __aenter__(self):
            return "stream-response"
        async def __aexit__(self, exc_type, exc, tb):
            return False

    stream_mock = MagicMock(return_value=DummyContext())
    monkeypatch.setattr(client.client, "stream", stream_mock)

    ctx = client.forward_stream(
        method="POST",
        path="/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json_data={"stream": True},
    )

    async with ctx as response:
        assert response == "stream-response"
```

- [ ] **Step 2: Write the failing retry tests**

```python
@pytest.mark.asyncio
async def test_stream_setup_retries_before_first_chunk(...):
    ...
    assert result.selected_key_id == "second-key"
    assert result.first_chunk == b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'


@pytest.mark.asyncio
async def test_stream_setup_returns_non_retry_upstream_error_without_rotating(...):
    ...
    assert result.retryable_failure is False
    assert result.response.status_code == 500
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `rtk proxy python -m pytest tests/test_proxy.py tests/test_retry.py -k "stream" -v`
Expected: FAIL because the streaming proxy helper and retry setup helper do not exist yet.

- [ ] **Step 4: Implement `forward_stream()` and streaming setup retry flow**

Implementation notes:
- `ProxyClient.forward_stream()` should mirror URL/header handling from `forward()`.
- Configure explicit `httpx.Limits` on the shared async client.
- The retry layer should own pre-start retry classification so router logic stays thin.
- Release stream leases immediately on setup failure paths.
- Do not retry after a successful setup has produced the first chunk.

- [ ] **Step 5: Run focused tests**

Run: `rtk proxy python -m pytest tests/test_proxy.py tests/test_retry.py -k "stream" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
rtk git add tests/test_proxy.py tests/test_retry.py ollama_router/proxy.py ollama_router/retry.py
rtk git commit -m "feat: add streaming setup retry flow"
```

---

### Task 3: Add Router Streaming Tests

**Files:**
- Modify: `tests/test_router.py`
- Modify: `ollama_router/router.py`

- [ ] **Step 1: Write the failing route tests**

```python
def test_openai_streaming_request_returns_streaming_response(tmp_path):
    config = Config(...)
    app = create_app(config, state_dir=str(tmp_path))
    client = TestClient(app)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "glm-4.7:cloud",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_raw())
        assert b"data:" in body


def test_non_streaming_request_still_uses_buffered_proxy_path(tmp_path):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy python -m pytest tests/test_router.py -k "streaming_request or non_streaming_request" -v`
Expected: FAIL because the generic router still buffers all responses.

- [ ] **Step 3: Implement the streaming branch in `router.py`**

Implementation notes:
- Detect `body.get("stream") is True` only for JSON object request bodies.
- Keep current non-streaming path unchanged.
- Ask the retry layer to prepare the upstream stream before creating `StreamingResponse`.
- Prefetch and yield the first chunk so retries remain pre-start only.
- Ensure the stream lease is released in all termination paths.

- [ ] **Step 4: Run focused router tests**

Run: `rtk proxy python -m pytest tests/test_router.py -k "streaming_request or non_streaming_request" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add tests/test_router.py ollama_router/router.py
rtk git commit -m "feat: stream openai-compatible proxy responses"
```

---

### Task 4: Verify End To End

**Files:**
- Test: `tests/test_state.py`
- Test: `tests/test_proxy.py`
- Test: `tests/test_retry.py`
- Test: `tests/test_router.py`
- Test: full suite

- [ ] **Step 1: Run the targeted stream-related suite**

Run: `rtk proxy python -m pytest tests/test_state.py tests/test_proxy.py tests/test_retry.py tests/test_router.py -v`
Expected: PASS

- [ ] **Step 2: Run the full suite**

Run: `rtk proxy python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Manually sanity-check with a live streaming request if needed**

Suggested check:

```bash
curl -N http://127.0.0.1:11435/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "glm-4.7:cloud",
    "messages": [{"role": "user", "content": "hello"}],
    "stream": true
  }'
```

Expected: incremental `data:` events rather than a single buffered payload.

- [ ] **Step 4: Commit**

```bash
rtk git add ollama_router/state.py ollama_router/proxy.py ollama_router/retry.py ollama_router/router.py tests/test_state.py tests/test_proxy.py tests/test_retry.py tests/test_router.py docs/superpowers/specs/2026-06-11-openai-streaming-concurrency-design.md docs/superpowers/plans/2026-06-11-openai-streaming-concurrency.md
rtk git commit -m "feat: add bounded openai streaming proxy support"
```
