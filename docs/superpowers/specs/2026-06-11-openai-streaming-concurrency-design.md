# OpenAI Streaming Concurrency Design

Date: 2026-06-11

## Overview

Add true upstream streaming support to the OpenAI-compatible proxy path so `/v1/chat/completions` and similar catch-all OpenAI-style routes can stream bytes to the client as they arrive from upstream instead of buffering the full response first.

This change must also hold up under multi-user concurrent access. The proxy should preserve the existing multi-key routing behavior, but change its stream handling so long-lived streaming requests do not accidentally overload a single key or force all users into serialized access.

## Relationship To Current Behavior

Today the generic proxy route in `ollama_router/router.py` sends every request through `RetryManager.execute_with_retry()` and `ProxyClient.forward()`. `ProxyClient.forward()` uses `httpx.AsyncClient.request()`, which fully reads the upstream response before control returns to the router. The router then responds with `result.response.content`.

That means OpenAI-compatible requests with `"stream": true` are not truly streamed to downstream clients. They are buffered by the proxy first.

Anthropic compatibility is different. `/v1/messages` already has a dedicated streaming path that uses `proxy.client.stream(...)` and `StreamingResponse`, but that path is specific to Anthropic SSE conversion and does not solve OpenAI-compatible streaming.

## Approved Direction

The approved direction is:

- support true downstream streaming for the OpenAI-compatible catch-all proxy path
- allow automatic key retry only before any downstream response bytes are emitted
- once downstream streaming begins, pin the request to the selected key and upstream connection
- support multi-user concurrency by allowing a bounded number of concurrent streams per key rather than exclusive single-stream key locking

## Goals

- Make OpenAI-compatible `"stream": true` requests behave like real streamed proxy responses.
- Preserve the current non-streaming behavior for all existing requests.
- Keep automatic retry behavior for key rotation, but only during the setup window before the client response has started.
- Prevent a single key from attracting unbounded concurrent streams during multi-user load.
- Release stream occupancy promptly when a client disconnects, upstream fails, or a stream completes normally.
- Keep implementation low-risk and contained to the current FastAPI + httpx architecture.

## Non-Goals

- No changes to Anthropic SSE conversion behavior in `/v1/messages`.
- No attempt to migrate an already-started downstream stream onto a new key.
- No cross-request stream multiplexing or shared fan-out.
- No distributed locking across multiple Python processes or multiple hosts in this pass.
- No new admin UI for tuning streaming concurrency in this pass.

## Design Principles

### 1. Real Streaming Means Byte Forwarding

For OpenAI-compatible streaming, the proxy should forward upstream bytes as they arrive instead of rebuilding SSE events or buffering the full body. The proxy is a transport intermediary here, not a stream translator.

### 2. Retry Only Before Downstream Response Start

Once the downstream response begins, HTTP semantics make retrying on a different key unsafe. The retry window must close before the first downstream bytes are emitted.

### 3. Concurrency Should Be Bounded, Not Serialized

Exclusive one-stream-per-key leasing would create poor throughput and visible head-of-line blocking. The better compromise is a small bounded concurrency per key with least-loaded selection.

### 4. Stream Occupancy Is Runtime State

Cooldown/disabled status is persisted state. Active stream occupancy is transient runtime state and should not be written into `state/key_states.json`.

### 5. Failures Must Clean Up Leases

Any selected stream slot must be released in `finally` semantics, regardless of success, timeout, disconnect, or upstream exception.

## Proposed Runtime Model

### Request Classification

The generic proxy route should treat a request as stream-capable when:

- the HTTP method carries a JSON body
- the body is a JSON object
- `body.get("stream") is True`

This keeps the behavior generic for OpenAI-compatible endpoints rather than hard-coding only `/v1/chat/completions`.

### Per-Key Stream Capacity

Each key should expose a transient `active_streams` count. Selection for streaming requests should:

- ignore keys that are cooldown/disabled
- ignore keys whose `active_streams` already reached the configured per-key stream cap
- among the remaining keys, prefer the least-loaded keys
- still bias away from `last_failed_key` when multiple candidates are otherwise equivalent

For this pass, the recommended default per-key stream limit is `2`. It should live as an implementation constant so it can be tuned later without redesigning the model.

### Lease Lifecycle

The stream setup flow should be:

1. Acquire a transient stream lease from the selector.
2. Open the upstream streaming request using the leased key.
3. Evaluate whether the upstream setup succeeded before beginning the downstream response.
4. If the stream is accepted, keep the lease for the duration of the stream.
5. Release the lease immediately when the stream ends or setup fails.

### Retry Window

Retries remain allowed only during setup, before the downstream response is started.

Retry-safe cases include:

- no key available under current capacity constraints
- upstream connection failure before downstream response start
- upstream `401`, `402`, `403`, `429`, or `502` detected before streaming begins

Once the stream begins emitting downstream bytes, retries stop permanently for that request. Any later upstream failure becomes a stream termination/error, not a key rotation event.

## Router And Proxy Flow

### Non-Streaming Requests

Non-streaming requests stay on the current path:

- router catch-all
- `RetryManager.execute_with_retry()`
- `ProxyClient.forward()`
- buffered `Response`

### Streaming Requests

Streaming requests should use a dedicated setup path that:

- prepares an upstream streaming response through the retry manager
- resolves retry-worthy setup failures before the downstream response starts
- returns a FastAPI `StreamingResponse`
- yields a prefetched first chunk followed by the remaining upstream chunks

Prefetching the first upstream chunk is intentional. It slightly delays the downstream start, but it lets the proxy honor the approved "retry before any downstream bytes" contract.

### Header Handling

The proxy should continue using the existing safe header filtering to strip hop-by-hop headers such as:

- `connection`
- `transfer-encoding`
- `content-length`
- `content-encoding`

For successful streams, downstream headers should preserve upstream metadata that remains valid, such as `content-type`, while still adding anti-buffering headers where appropriate.

## Concurrency Behavior

### Within One Process

The proxy should make stream lease acquisition and release atomic at the selector level so concurrent requests in the same process cannot over-allocate a key.

The current code has no transient occupancy tracking, so multiple simultaneous streams can easily choose the same available key. This design fixes that by making stream selection capacity-aware.

### Across Multiple Processes

This pass is intentionally single-process scoped. If the deployment later uses multiple Uvicorn workers or multiple containers sharing the same key pool, stream occupancy will not be globally coordinated. That is acceptable for this pass because:

- the current persisted state already does not provide distributed locking
- the requested improvement is primarily about user-visible streaming behavior and in-process concurrency safety
- a distributed lease system would be a separate architectural feature

## Resource Management

The shared `httpx.AsyncClient` should be given explicit connection pool limits suitable for many simultaneous long-lived streams.

The goal is not to create a complicated queue. The goal is to prevent unbounded connection growth under concurrent streaming load while still allowing enough open upstream connections for normal usage.

Recommended implementation shape:

- configure explicit `httpx.Limits`
- keep one shared async client on app state as today
- use `client.stream(...)` for streaming setup
- ensure response objects are closed when setup fails before the downstream response starts

## Error Handling

### Retry-Worthy Setup Errors

If the upstream returns a retry-worthy status before the stream starts:

- mark cooldown/disabled exactly as today
- release the stream lease
- try another key if retries remain

### Non-Retry Setup Errors

If the upstream returns a non-retry status before streaming begins:

- do not rotate keys automatically
- return the upstream error body/status downstream
- release the lease immediately

### Mid-Stream Failures

If the upstream fails after downstream bytes have begun:

- log the failure
- release the lease
- terminate the stream

No key rotation should happen at that point.

## Testing Strategy

Verification should cover three layers:

### Selector / State Tests

- stream lease acquisition increments transient occupancy
- stream lease release decrements occupancy
- least-loaded selection prefers keys with fewer active streams
- keys at capacity are skipped for streaming selection

### Retry / Setup Tests

- setup retries on retry-worthy upstream failures before streaming starts
- setup stops retrying after success and keeps the chosen lease until stream completion
- non-retry upstream setup errors are returned directly

### Router / Integration Tests

- OpenAI-compatible `"stream": true` requests return a `StreamingResponse`
- downstream receives upstream stream payload incrementally instead of buffered final content
- non-streaming requests preserve existing behavior
- stream leases are released after completion

## Risks

- prefetching the first upstream chunk delays the downstream response start compared with naive header-first streaming
- capacity-aware selection introduces more statefulness into `KeySelector`
- long-lived streams make cleanup bugs more expensive, so `finally` paths must be tested carefully

## Success Criteria

This work is successful if:

- OpenAI-compatible `stream=true` requests behave as true streamed responses
- retries only happen before the downstream response starts
- multiple concurrent users can stream without globally serializing access to one key at a time
- stream occupancy is bounded per key and released correctly
- non-streaming proxy behavior stays unchanged
