# Admin UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Ollama Router admin frontend so every admin page matches the approved dark dashboard prototype while preserving the current FastAPI + Jinja2 + HTMX behavior.

**Architecture:** Keep the existing server-rendered admin routes and enrich the view-layer data in `ollama_router/admin/views.py` so the templates can render richer dashboard sections, summaries, and activity panels. Rebuild the shared admin shell in `templates/admin/base.html`, then restyle the individual page templates and partials to use one coherent set of dark-console components, with lightweight SVG/CSS visuals instead of introducing a new frontend framework or heavy chart dependency.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, HTMX, Tailwind CSS (CDN), lightweight inline JavaScript, `fastapi.testclient.TestClient`

---

## References

- Spec: `docs/superpowers/specs/2026-06-10-admin-ui-redesign-design.md`
- Visual reference: `/data1/lzb/download/_https_github.com_weisha1991_ollamaopenrouter_UI_..png`
- Use `@superpowers:test-driven-development` for every code task.
- Use `@browser:control-in-app-browser` for final browser QA.

## File Structure

```
ollama_router/admin/
├── views.py                         # MODIFY: add dashboard view-model builders and richer summary helpers
└── routes.py                        # MODIFY: pass richer admin context into template partials

templates/admin/
├── base.html                        # MODIFY: replace shell, tokens, nav, topbar, shared component styling
├── login.html                       # MODIFY: redesign branded login experience
├── dashboard.html                   # MODIFY: keep live container, host upgraded dashboard partial
├── _stats_panel.html                # MODIFY: render full dashboard grid (cards, charts, recent panels)
├── keys.html                        # MODIFY: summary + add-key layout wrapper
├── _keys_table.html                 # MODIFY: upgraded keys table and action presentation
├── history.html                     # MODIFY: summary + history monitoring layout wrapper
├── _history_table.html              # MODIFY: upgraded history table styling and badges
├── logs.html                        # MODIFY: segmented mode switch and unified shell
├── _logs_table.html                 # MODIFY: redesigned historical log filters and results panel
└── _logs_stream.html                # MODIFY: redesigned realtime log console panel

tests/admin/
├── test_admin_views.py              # NEW: view-model helper tests for dashboard summaries/trends/activity
└── test_admin_pages.py              # NEW: authenticated page and fragment rendering tests
```

---

## Task 1: Add Dashboard View-Model Helpers

**Files:**
- Create: `tests/admin/test_admin_views.py`
- Modify: `ollama_router/admin/views.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/admin/test_admin_views.py
from datetime import datetime, timezone

from ollama_router.admin.views import (
    _build_dashboard_context,
    _build_keys,
    _build_requests,
)
from ollama_router.request_history import RequestHistory, RequestRecord
from ollama_router.state import KeySelector, KeyState, KeyStatus


def _make_history() -> RequestHistory:
    history = RequestHistory(max_size=20)
    history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc),
            request_id="req_a",
            method="POST",
            path="/v1/chat/completions",
            status_code=200,
            key_id="key-a",
            latency_ms=240,
        )
    )
    history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 11, 0, tzinfo=timezone.utc),
            request_id="req_b",
            method="POST",
            path="/v1/messages",
            status_code=429,
            key_id="key-b",
            latency_ms=820,
        )
    )
    return history


def test_build_dashboard_context_returns_cards_trend_distribution_and_lists():
    selector = KeySelector(
        [
            KeyState(key="alpha", status=KeyStatus.AVAILABLE),
            KeyState(key="beta", status=KeyStatus.COOLDOWN),
            KeyState(key="gamma", status=KeyStatus.DISABLED),
        ]
    )
    selector.last_used_key = "alpha"
    history = _make_history()

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["stats"]["total_keys"] == 3
    assert dashboard["distribution"]["available"] == 1
    assert dashboard["distribution"]["cooldown"] == 1
    assert dashboard["distribution"]["disabled"] == 1
    assert len(dashboard["request_overview"]) >= 1
    assert len(dashboard["recent_keys"]) == 3
    assert len(dashboard["recent_activity"]) == 2


def test_recent_activity_keeps_latest_requests_first():
    selector = KeySelector([KeyState(key="alpha")])
    history = _make_history()

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["recent_activity"][0]["request_id"] == "req_b"
    assert dashboard["recent_activity"][1]["request_id"] == "req_a"


def test_request_overview_buckets_history_without_empty_failure():
    selector = KeySelector([KeyState(key="alpha")])
    history = RequestHistory(max_size=20)

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["request_overview"] == []
    assert dashboard["recent_activity"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_views.py -v`  
Expected: FAIL with `ImportError` or `AttributeError` because `_build_dashboard_context` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# ollama_router/admin/views.py
def _build_dashboard_context(selector: KeySelector, history) -> dict:
    stats = _build_stats(selector, history)
    keys = _build_keys(selector)
    requests = _build_requests(history)
    return {
        "stats": stats,
        "distribution": {
            "available": stats["available_keys"],
            "cooldown": stats["cooldown_keys"],
            "disabled": stats["disabled_keys"],
        },
        "request_overview": _build_request_overview(requests),
        "recent_keys": keys[:5],
        "recent_activity": requests[:5],
    }


def _build_request_overview(requests: list[dict]) -> list[dict]:
    buckets: dict[str, int] = {}
    for request in requests[:24]:
        hour_label = request["time"][11:16] if len(request["time"]) >= 16 else "--:--"
        buckets[hour_label] = buckets.get(hour_label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(buckets.items())]
```

Implementation notes:
- Build one new public-in-module helper: `_build_dashboard_context(selector, history)`.
- Keep `_build_stats`, `_build_keys`, and `_build_requests` as the base primitives.
- Add one small helper for request trend buckets rather than embedding chart prep inline.
- Keep the return shape template-friendly: lists/dicts only, no dataclass instances.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/admin/test_admin_views.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add tests/admin/test_admin_views.py ollama_router/admin/views.py
rtk git commit -m "feat: add admin dashboard view-model helpers"
```

---

## Task 2: Rebuild the Shared Admin Shell and Login Screen

**Files:**
- Create: `tests/admin/test_admin_pages.py`
- Modify: `templates/admin/base.html`
- Modify: `templates/admin/login.html`

- [ ] **Step 1: Write the failing tests**

```python
# tests/admin/test_admin_pages.py
from fastapi.testclient import TestClient

from ollama_router.config import Config
from ollama_router.router import create_app


def _make_client(tmp_path) -> TestClient:
    app = create_app(
        Config(
            listen="127.0.0.1:11435",
            upstream="https://ollama.com/v1",
            keys=["test_key"],
            admin_username="admin",
            admin_password="testpass",
            admin_session_secret="test-secret",
        ),
        state_dir=str(tmp_path),
    )
    return TestClient(app)


def _login(client: TestClient) -> None:
    response = client.post(
        "/admin/api/login",
        data={"username": "admin", "password": "testpass"},
    )
    assert response.status_code == 200


def test_login_page_renders_brand_shell(tmp_path):
    client = _make_client(tmp_path)

    response = client.get("/admin/login")

    assert response.status_code == 200
    html = response.text
    assert "Ollama Router" in html
    assert "Sign in" in html
    assert "admin-login-shell" in html


def test_dashboard_page_renders_new_shell_after_auth(tmp_path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "admin-shell" in html
    assert "Dashboard" in html
    assert "/admin/keys" in html
    assert "/admin/logs" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_pages.py -v`  
Expected: FAIL because `admin-login-shell` / `admin-shell` markers are not present.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- templates/admin/base.html -->
<body class="admin-shell min-h-screen bg-slate-950 text-slate-100">
  <aside class="admin-sidebar hidden w-72 shrink-0 border-r border-violet-500/10 bg-slate-950/90 md:flex md:flex-col">
    <div class="flex h-20 items-center px-7 text-xl font-semibold">Ollama Router</div>
    <nav class="flex-1 px-5 py-6">
      <a href="/admin/dashboard" class="flex items-center rounded-xl px-4 py-3 text-sm font-medium text-slate-200">Dashboard</a>
      <a href="/admin/keys" class="mt-2 flex items-center rounded-xl px-4 py-3 text-sm font-medium text-slate-400">Keys</a>
      <a href="/admin/history" class="mt-2 flex items-center rounded-xl px-4 py-3 text-sm font-medium text-slate-400">History</a>
      <a href="/admin/logs" class="mt-2 flex items-center rounded-xl px-4 py-3 text-sm font-medium text-slate-400">Logs</a>
    </nav>
    <div class="px-5 pb-6">
      <div class="rounded-2xl border border-emerald-500/15 bg-slate-900/90 p-4 text-sm">System Status</div>
    </div>
  </aside>
  <div class="admin-app flex min-h-screen flex-1 flex-col">
    <header class="admin-topbar flex h-20 items-center justify-between border-b border-white/5 px-6 lg:px-8">
      <div class="space-y-1">
        <h1 class="text-2xl font-semibold">{% block header_title %}Dashboard{% endblock %}</h1>
        <p class="text-sm text-slate-400">{% block header_subtitle %}{% endblock %}</p>
      </div>
      <div class="flex items-center gap-3">
        <form method="POST" action="/admin/api/logout"><button type="submit" class="rounded-full border border-violet-400/40 px-5 py-2 text-sm font-medium text-violet-200">Logout</button></form>
      </div>
    </header>
    <main class="admin-content flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      {% block content %}{% endblock %}
    </main>
  </div>
</body>

<!-- templates/admin/login.html -->
<body class="admin-login-shell min-h-screen bg-slate-950 text-slate-100">
  <section class="login-panel mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-6 py-12">
    <div class="w-full max-w-md rounded-2xl border border-violet-500/15 bg-slate-900/80 p-8 shadow-2xl shadow-violet-950/30">
      <h1 class="text-3xl font-semibold">Ollama Router</h1>
      <p class="mt-2 text-sm text-slate-400">Sign in to the admin console.</p>
      <form class="mt-8 space-y-4">
        <input type="text" name="username" class="w-full rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3" />
        <input type="password" name="password" class="w-full rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3" />
        <button type="submit" class="w-full rounded-xl bg-violet-500 px-4 py-3 font-medium text-white">Sign in</button>
      </form>
    </div>
  </section>
</body>
```

Implementation notes:
- Keep Tailwind CDN setup, but replace the old neutral-gray shell with a deep navy theme.
- Add stable class hooks like `admin-shell` and `admin-login-shell` so rendering tests can assert the new shell exists without depending on incidental wording.
- Preserve all existing login HTMX behavior and error handling.
- Keep the mobile sidebar toggle working after the redesign.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/admin/test_admin_pages.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add tests/admin/test_admin_pages.py templates/admin/base.html templates/admin/login.html
rtk git commit -m "feat: redesign admin shell and login page"
```

---

## Task 3: Rebuild the Dashboard Layout and Context Wiring

**Files:**
- Modify: `ollama_router/admin/routes.py`
- Modify: `templates/admin/dashboard.html`
- Modify: `templates/admin/_stats_panel.html`
- Modify: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Write the failing test**

```python
def test_dashboard_fragment_renders_cards_and_panels(tmp_path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/api/stats/panel")

    assert response.status_code == 200
    html = response.text
    assert "Total Keys" in html
    assert "Available Keys" in html
    assert "Cooldown Keys" in html
    assert "Total Requests" in html
    assert "Request Overview" in html
    assert "Key Status Distribution" in html
    assert "Recent Keys" in html
    assert "Recent Activity" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_pages.py::test_dashboard_fragment_renders_cards_and_panels -v`  
Expected: FAIL because the current fragment only renders the old stat cards.

- [ ] **Step 3: Write minimal implementation**

```python
# ollama_router/admin/routes.py
from ollama_router.admin.views import _build_dashboard_context

@router.get("/stats/panel", response_class=HTMLResponse)
async def stats_panel(request: Request, _: str = Depends(get_current_user)) -> Response:
    templates = request.app.state.templates
    selector: KeySelector = request.app.state.selector
    history = request.app.state.request_history
    dashboard = _build_dashboard_context(selector, history)
    return templates.TemplateResponse(
        request=request,
        name="admin/_stats_panel.html",
        context={"dashboard": dashboard, "stats": dashboard["stats"]},
    )
```

```html
<!-- templates/admin/dashboard.html -->
<div id="stats-container" hx-get="/admin/api/stats/panel" hx-trigger="load, every 30s" hx-swap="innerHTML">
  {% include "admin/_stats_panel.html" %}
</div>

<!-- templates/admin/_stats_panel.html -->
<section class="dashboard-grid grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,.95fr)]">
  <div class="xl:col-span-2 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
    <article class="rounded-2xl border border-sky-500/20 bg-slate-900/70 p-5">Total Keys</article>
    <article class="rounded-2xl border border-emerald-500/20 bg-slate-900/70 p-5">Available Keys</article>
    <article class="rounded-2xl border border-amber-500/20 bg-slate-900/70 p-5">Cooldown Keys</article>
    <article class="rounded-2xl border border-violet-500/20 bg-slate-900/70 p-5">Total Requests</article>
  </div>
  <section class="rounded-2xl border border-white/6 bg-slate-900/70 p-5">Request Overview</section>
  <section class="rounded-2xl border border-white/6 bg-slate-900/70 p-5">Key Status Distribution</section>
  <section class="rounded-2xl border border-white/6 bg-slate-900/70 p-5">Recent Keys</section>
  <section class="rounded-2xl border border-white/6 bg-slate-900/70 p-5">Recent Activity</section>
</section>
```

Implementation notes:
- Keep the single HTMX dashboard fragment pattern; just expand the fragment into the full dashboard body.
- Render request overview with lightweight inline SVG/CSS using `dashboard["request_overview"]`.
- Render the distribution panel from the real `available/cooldown/disabled` counts only.
- Map recent activity from request history into a short summary list instead of duplicating the full history table.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/admin/test_admin_pages.py::test_dashboard_fragment_renders_cards_and_panels -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add ollama_router/admin/routes.py templates/admin/dashboard.html templates/admin/_stats_panel.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: redesign admin dashboard layout"
```

---

## Task 4: Redesign the Keys and History Views

**Files:**
- Modify: `templates/admin/keys.html`
- Modify: `templates/admin/_keys_table.html`
- Modify: `templates/admin/history.html`
- Modify: `templates/admin/_history_table.html`
- Modify: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_keys_page_renders_summary_and_action_shell(tmp_path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/keys")

    assert response.status_code == 200
    html = response.text
    assert "Key Inventory" in html
    assert "Add API Key" in html
    assert "Key ID" in html


def test_history_page_renders_monitoring_summary(tmp_path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/history")

    assert response.status_code == 200
    html = response.text
    assert "Request History" in html
    assert "Recent Traffic" in html
    assert "Latency" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "keys_page or history_page" -v`  
Expected: FAIL because the new summary titles and monitoring shell are not present.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- templates/admin/keys.html -->
<section class="page-stack space-y-6">
  <header class="section-panel rounded-2xl border border-white/6 bg-slate-900/70 p-6">
    <h2>Key Inventory</h2>
    <p class="mt-2 text-sm text-slate-400">Monitor availability, cooldown state, and current routing usage.</p>
  </header>
  <section class="section-panel rounded-2xl border border-white/6 bg-slate-900/70 p-6">
    <h3>Add API Key</h3>
    <form id="add-key-form" class="mt-4 flex flex-col gap-3 lg:flex-row">
      <input type="text" name="key" placeholder="Enter API key" class="flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-slate-100" />
      <button type="submit" class="rounded-xl bg-violet-500 px-5 py-3 text-sm font-medium text-white">Add Key</button>
    </form>
  </section>
  <div id="keys-container" hx-get="/admin/api/keys/table" hx-trigger="load, every 30s, keyChanged from:body" hx-swap="innerHTML">
    {% include "admin/_keys_table.html" %}
  </div>
</section>

<!-- templates/admin/history.html -->
<section class="page-stack space-y-6">
  <header class="section-panel rounded-2xl border border-white/6 bg-slate-900/70 p-6">
    <h2>Recent Traffic</h2>
    <p class="mt-2 text-sm text-slate-400">Scan recent request outcomes, latency, and endpoint activity.</p>
  </header>
  <div id="history-container" hx-get="/admin/api/history/table" hx-trigger="load, every 30s" hx-swap="innerHTML">
    {% include "admin/_history_table.html" %}
  </div>
</section>
```

Implementation notes:
- Reuse the shared card, badge, and table styles established in `base.html`.
- Keep the current key actions intact; only restyle the controls.
- Add real summary cards/totals where the data already exists instead of introducing new APIs.
- For history, make method, status, and latency visually scannable with badges and stronger typography.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "keys_page or history_page" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/keys.html templates/admin/_keys_table.html templates/admin/history.html templates/admin/_history_table.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: redesign admin keys and history views"
```

---

## Task 5: Redesign the Logs Experience

**Files:**
- Modify: `templates/admin/logs.html`
- Modify: `templates/admin/_logs_table.html`
- Modify: `templates/admin/_logs_stream.html`
- Modify: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_logs_page_renders_segmented_monitoring_layout(tmp_path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/logs")

    assert response.status_code == 200
    html = response.text
    assert "Historical Logs" in html
    assert "Realtime Logs" in html
    assert "log-console-shell" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_pages.py::test_logs_page_renders_segmented_monitoring_layout -v`  
Expected: FAIL because the old tab shell and class hooks are still in place.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- templates/admin/logs.html -->
<section class="page-stack log-console-shell space-y-6">
  <div class="segmented-control inline-flex rounded-xl border border-white/8 bg-slate-900/80 p-1">
    <button id="tab-historical" class="rounded-lg px-4 py-2 text-sm font-medium">Historical Logs</button>
    <button id="tab-realtime" class="rounded-lg px-4 py-2 text-sm font-medium">Realtime Logs</button>
  </div>
  <div id="content-historical" class="tab-content">
    {% include "admin/_logs_table.html" %}
  </div>
  <div id="content-realtime" class="tab-content hidden">
    {% include "admin/_logs_stream.html" %}
  </div>
</section>
```

Implementation notes:
- Update the labels to English to stay consistent with the rest of the admin UI unless the product owner explicitly wants bilingual UI.
- Preserve all existing JS behavior for preset filters, downloads, SSE connection, pause/resume, and clear logs.
- Restyle the historical filters and realtime console surface to match the new shell.
- Add one stable class hook (`log-console-shell`) so the page test can assert the redesign shape.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/admin/test_admin_pages.py::test_logs_page_renders_segmented_monitoring_layout -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/logs.html templates/admin/_logs_table.html templates/admin/_logs_stream.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: redesign admin logs experience"
```

---

## Task 6: Full Regression and Browser QA

**Files:**
- Modify: `docs/superpowers/plans/2026-06-10-admin-ui-redesign.md` (check off completed steps during execution only)
- Verify: `templates/admin/*.html`
- Verify: `ollama_router/admin/views.py`
- Verify: `ollama_router/admin/routes.py`
- Verify: `tests/admin/test_admin_views.py`
- Verify: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Run focused automated tests**

Run: `rtk pytest tests/admin/test_admin_views.py tests/admin/test_admin_pages.py tests/admin/test_log_routes.py tests/admin/test_logs.py -v`  
Expected: PASS

- [ ] **Step 2: Run the broader regression suite**

Run: `rtk pytest -v`  
Expected: PASS

- [ ] **Step 3: Start the app locally for manual verification**

Run: `rtk python -m ollama_router`  
Expected: Local server starts and serves admin routes from `config.yaml`

- [ ] **Step 4: Verify each admin page in the browser**

Using `@browser:control-in-app-browser`, inspect:
- `/admin/login`
- `/admin/dashboard`
- `/admin/keys`
- `/admin/history`
- `/admin/logs`

Check:
- shared shell consistency
- dashboard resemblance to the approved prototype
- readable tables and badges
- no overflow or broken mobile collapse
- live refresh behavior remains stable

- [ ] **Step 5: Commit the finished redesign**

```bash
rtk git add ollama_router/admin/views.py ollama_router/admin/routes.py templates/admin tests/admin
rtk git commit -m "feat: redesign admin interface"
```
