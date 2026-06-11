# Admin Desktop Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the redesigned admin UI into a denser, clearer desktop control console without changing backend behavior or mobile scope.

**Architecture:** Keep the current FastAPI + Jinja2 + HTMX admin flow intact and do the polish almost entirely in the shared admin shell and page templates. Introduce a small set of reusable desktop-density classes in `templates/admin/base.html`, then apply them to the dashboard, keys, history, and logs templates so the whole console gains consistent hierarchy, tighter spacing, and stronger scanability.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, HTMX, Tailwind CSS (CDN), inline JavaScript, `fastapi.testclient.TestClient`

---

## References

- Spec: `docs/superpowers/specs/2026-06-11-admin-desktop-polish-design.md`
- Prior implementation plan: `docs/superpowers/plans/2026-06-10-admin-ui-redesign.md`
- Use `@superpowers:test-driven-development` for each implementation task.
- Use `@browser:control-in-app-browser` for final desktop QA after the code lands.

## File Structure

```text
templates/admin/
├── base.html                 # MODIFY: shared desktop density, header rhythm, table and console utility classes
├── _stats_panel.html         # MODIFY: dashboard primary/secondary hierarchy and denser desktop layout
├── keys.html                 # MODIFY: compress page intro and tighten action area
├── _keys_table.html          # MODIFY: stronger row scan rails and denser action cells
├── history.html              # MODIFY: compress monitoring summary band
├── _history_table.html       # MODIFY: stronger table framing and faster scan rhythm
├── logs.html                 # MODIFY: tighter header and stronger tab-strip framing
├── _logs_table.html          # MODIFY: console-like filter/query surface and historical results frame
└── _logs_stream.html         # MODIFY: sturdier live stream control bar and log console frame

tests/admin/
└── test_admin_pages.py       # MODIFY: assert new desktop polish markers and page-specific console shells
```

## File Responsibilities

- `templates/admin/base.html:40-272,425-458`
  - Own the shared visual system for desktop density.
  - Add reusable classes for compact headers, denser panels, table scan rails, and console framing.
- `templates/admin/_stats_panel.html:18-328`
  - Recompose the dashboard so the request overview is the dominant first-screen panel and supporting areas step back.
- `templates/admin/keys.html:8-65`
  - Turn the current tall hero block into a tighter desktop page intro and more compact action surface.
- `templates/admin/_keys_table.html:1-79`
  - Improve status/action scanability without changing key operations.
- `templates/admin/history.html:8-45`
  - Reduce intro height and push the request table higher.
- `templates/admin/_history_table.html:1-51`
  - Strengthen visual grouping for time, method, status, key, and latency.
- `templates/admin/logs.html:8-56`
  - Make the mode switch read like a control strip rather than a decorative tab.
- `templates/admin/_logs_table.html:1-212`
  - Treat historical log filters and results as a dedicated inspection surface.
- `templates/admin/_logs_stream.html:1-210`
  - Treat the live stream as a purpose-built console panel while preserving SSE behavior.
- `tests/admin/test_admin_pages.py:34-137`
  - Lock in stable render markers that prove the desktop polish landed on each page.

---

### Task 1: Add Desktop Polish Render Tests

**Files:**
- Modify: `tests/admin/test_admin_pages.py:34-137`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_page_renders_desktop_console_shell(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "admin-shell" in html
    assert "admin-page-header-compact" in html
    assert "admin-content-dense" in html


def test_dashboard_fragment_renders_primary_and_secondary_desktop_panels(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/api/stats/panel")

    assert response.status_code == 200
    html = response.text
    assert "admin-dashboard-primary" in html
    assert "admin-kpi-secondary" in html


def test_keys_page_renders_compact_intro_and_dense_table(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/keys")

    assert response.status_code == 200
    html = response.text
    assert "admin-page-intro-compact" in html
    assert "admin-table-dense" in html


def test_logs_page_renders_console_framing_markers(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/logs")

    assert response.status_code == 200
    html = response.text
    assert "admin-tab-strip" in html
    assert "admin-console-frame" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/admin/test_admin_pages.py -v`  
Expected: FAIL because the new desktop polish marker classes are not rendered yet.

- [ ] **Step 3: Update the tests with the new assertions only**

Implementation notes:
- Extend the existing page render tests instead of creating a second admin page test file.
- Use stable CSS class markers as assertions so the tests verify the desktop polish directly.
- Keep assertions at the rendered HTML level; do not add brittle exact-whitespace checks.

- [ ] **Step 4: Run test to confirm only the new assertions are failing**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "desktop_console_shell or primary_and_secondary_desktop_panels or compact_intro or console_framing_markers" -v`  
Expected: FAIL on missing class markers and PASS on unrelated existing tests.

- [ ] **Step 5: Commit**

```bash
rtk git add tests/admin/test_admin_pages.py
rtk git commit -m "test: cover admin desktop polish render markers"
```

---

### Task 2: Tighten the Shared Desktop Shell

**Files:**
- Modify: `templates/admin/base.html:40-272`
- Modify: `templates/admin/base.html:425-458`
- Test: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Implement shared desktop density classes in the base template**

```html
<style>
    .admin-content-dense {
        display: grid;
        gap: 1.25rem;
    }

    .admin-page-intro-compact {
        gap: 1rem;
    }

    .admin-page-header-compact {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .admin-panel-dense {
        padding: 1rem;
    }

    .admin-table-dense thead th {
        padding: 0.72rem 0.9rem;
        letter-spacing: 0.04em;
    }

    .admin-table-dense tbody td {
        padding: 0.78rem 0.9rem;
    }

    .admin-console-frame {
        border: 1px solid rgba(151, 168, 197, 0.12);
        background: rgba(6, 11, 20, 0.82);
    }

    @media (min-width: 1280px) {
        .admin-page-header-compact .admin-page-title {
            font-size: 1.7rem;
        }
    }
</style>
```

- [ ] **Step 2: Apply the compact shell classes to the shared header and main content wrapper**

```html
<header class="admin-page-header-compact border-b border-white/6 bg-[rgba(8,15,27,0.72)] backdrop-blur-lg">
    <div class="mx-auto flex max-w-[1600px] flex-col gap-3 px-4 py-3 sm:px-6 lg:px-8 xl:flex-row xl:items-end xl:justify-between">
        ...
    </div>
</header>

<main class="flex-1 overflow-y-auto">
    <div class="admin-content-dense mx-auto max-w-[1600px] px-4 py-4 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </div>
</main>
```

- [ ] **Step 3: Keep behavior untouched while tightening only desktop rhythm**

Implementation notes:
- Do not change sidebar JS, logout flow, HTMX config, or mobile sidebar behavior.
- Keep existing shared tokens and fonts; just add utility classes and adjust spacing/line weight.
- Make density gains mostly via desktop-safe spacing changes rather than global font shrinkage.

- [ ] **Step 4: Run the page render tests**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "desktop_console_shell or login_page or dashboard_page" -v`  
Expected: PASS for the compact shell markers and no regressions on existing shell tests.

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/base.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: tighten shared admin desktop shell"
```

---

### Task 3: Rebalance Dashboard Hierarchy

**Files:**
- Modify: `templates/admin/_stats_panel.html:18-328`
- Test: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Make the dashboard test fail on the new hierarchy markers**

```python
def test_dashboard_fragment_renders_primary_and_secondary_desktop_panels(tmp_path: Path):
    ...
    assert "admin-dashboard-primary" in html
    assert "admin-kpi-secondary" in html
```

Run: `rtk pytest tests/admin/test_admin_pages.py -k primary_and_secondary_desktop_panels -v`  
Expected: FAIL until the fragment gets the new classes.

- [ ] **Step 2: Rebuild the dashboard fragment around a clear primary panel**

```html
<div class="space-y-4">
    <section class="grid gap-3 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
        <article class="admin-dashboard-primary admin-panel rounded-lg p-5">
            ...
        </article>
        <div class="grid gap-3">
            <article class="admin-kpi-secondary admin-panel-soft rounded-lg p-4">...</article>
            <article class="admin-kpi-secondary admin-panel-soft rounded-lg p-4">...</article>
            <article class="admin-kpi-secondary admin-panel-soft rounded-lg p-4">...</article>
        </div>
    </section>
```

- [ ] **Step 3: Tighten dashboard internals without hiding information**

Implementation notes:
- Keep all four KPI metrics, but visually demote the secondary ones through padding and framing.
- Reduce vertical gaps around `Request Overview`, `Key Status Distribution`, `Recent Keys`, and `Recent Activity`.
- Preserve the existing request chart, distribution donut, and empty/single-data states.
- Reuse `admin-table-dense` or equivalent row-tightening classes for the dashboard’s recent data tables.

- [ ] **Step 4: Run the dashboard-focused tests**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "dashboard_fragment or dashboard_page" -v`  
Expected: PASS with both the existing dashboard content assertions and the new hierarchy markers.

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/_stats_panel.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: sharpen admin dashboard desktop hierarchy"
```

---

### Task 4: Compress Keys and History Into Denser Table Workspaces

**Files:**
- Modify: `templates/admin/keys.html:8-65`
- Modify: `templates/admin/_keys_table.html:1-79`
- Modify: `templates/admin/history.html:8-45`
- Modify: `templates/admin/_history_table.html:1-51`
- Test: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Add failing assertions for compact intros and dense tables**

```python
def test_keys_page_renders_compact_intro_and_dense_table(tmp_path: Path):
    ...
    assert "admin-page-intro-compact" in html
    assert "admin-table-dense" in html


def test_history_page_renders_monitoring_summary(tmp_path: Path):
    ...
    assert "admin-page-intro-compact" in html
    assert "admin-table-dense" in html
```

- [ ] **Step 2: Tighten the keys page wrapper and key table**

```html
<section class="admin-page-intro-compact admin-panel rounded-lg p-4">
    ...
</section>

<table class="admin-table admin-table-dense">
    ...
</table>
```

Implementation notes:
- Reduce the keys page hero feel by shrinking the intro block and summary card padding.
- Keep the add-key form and operating notes visible above the fold on common desktop widths.
- Use denser action button spacing in the key table, but keep button labels unchanged.

- [ ] **Step 3: Tighten the history page wrapper and request ledger table**

```html
<section class="admin-page-intro-compact admin-panel rounded-lg p-4">
    ...
</section>

<table class="admin-table admin-table-dense">
    ...
</table>
```

Implementation notes:
- Make the request ledger the visual priority by reducing the summary block’s vertical footprint.
- Improve scanability of `Time`, `Method`, `Path`, `Status`, `Key ID`, and `Latency` with cleaner spacing and row framing.
- Do not change the request data shape or refresh behavior.

- [ ] **Step 4: Run the page tests for keys and history**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "keys_page or history_page" -v`  
Expected: PASS with the new compact-intro and dense-table assertions.

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/keys.html templates/admin/_keys_table.html templates/admin/history.html templates/admin/_history_table.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: densify admin keys and history pages"
```

---

### Task 5: Harden the Logs Page Into a Stronger Console Surface

**Files:**
- Modify: `templates/admin/logs.html:8-56`
- Modify: `templates/admin/_logs_table.html:1-212`
- Modify: `templates/admin/_logs_stream.html:1-210`
- Test: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Make the logs page test fail on the console markers**

```python
def test_logs_page_renders_console_framing_markers(tmp_path: Path):
    ...
    assert "admin-tab-strip" in html
    assert "admin-console-frame" in html
```

Run: `rtk pytest tests/admin/test_admin_pages.py -k logs_page_renders_console_framing_markers -v`  
Expected: FAIL until the logs templates adopt the new classes.

- [ ] **Step 2: Tighten the logs page header and tab strip**

```html
<div class="admin-page-intro-compact admin-panel rounded-lg p-4">
    ...
    <div class="admin-tab-strip inline-flex rounded-lg border border-white/8 bg-[rgba(255,255,255,0.03)] p-1">
        ...
    </div>
</div>
```

- [ ] **Step 3: Give both historical and live log surfaces a firmer console frame**

```html
<div class="admin-console-frame overflow-hidden rounded-lg">
    <div id="logs-table-container">...</div>
</div>

<div class="admin-console-frame overflow-hidden rounded-lg shadow-inner shadow-black/40">
    <div id="log-stream-container" class="h-[30rem] overflow-y-auto p-4 font-mono text-sm leading-6">
        ...
    </div>
</div>
```

Implementation notes:
- Keep `switchTab()`, `loadLogs()`, `downloadLogs()`, `startLogStream()`, and `stopLogStream()` behavior unchanged.
- Do not rename DOM ids used by the existing JavaScript.
- Tighten filter/control spacing and make the tab/header controls feel more like an operator toolbar.

- [ ] **Step 4: Run logs-focused tests**

Run: `rtk pytest tests/admin/test_admin_pages.py -k "logs_page or console_framing_markers" -v`  
Expected: PASS with the new tab-strip and console-frame assertions, plus the older content assertions.

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/logs.html templates/admin/_logs_table.html templates/admin/_logs_stream.html tests/admin/test_admin_pages.py
rtk git commit -m "feat: polish admin logs desktop console"
```

---

### Task 6: Verify Desktop Polish End-to-End

**Files:**
- Verify: `templates/admin/base.html`
- Verify: `templates/admin/_stats_panel.html`
- Verify: `templates/admin/keys.html`
- Verify: `templates/admin/_keys_table.html`
- Verify: `templates/admin/history.html`
- Verify: `templates/admin/_history_table.html`
- Verify: `templates/admin/logs.html`
- Verify: `templates/admin/_logs_table.html`
- Verify: `templates/admin/_logs_stream.html`
- Verify: `tests/admin/test_admin_pages.py`

- [ ] **Step 1: Run the focused admin page tests**

Run: `rtk pytest tests/admin/test_admin_pages.py -v`  
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `rtk proxy python -m pytest -q`  
Expected: PASS for the full repository test suite.

- [ ] **Step 3: Run desktop browser QA**

Run `@browser:control-in-app-browser` against:
- `http://127.0.0.1:18765/admin/dashboard`
- `http://127.0.0.1:18765/admin/keys`
- `http://127.0.0.1:18765/admin/history`
- `http://127.0.0.1:18765/admin/logs`

Check:
- headers are visibly shorter on desktop
- dashboard has a clear primary panel and subordinate support panels
- keys/history tables show more rows sooner without looking cramped
- logs tabs, filters, table, and stream feel like one console surface
- tab switching and live log stream still work

- [ ] **Step 4: Capture follow-up fixes if browser QA finds issues**

Implementation notes:
- If QA finds a visual regression, fix only the smallest affected template/style block.
- Re-run the narrowest relevant test first, then re-run `tests/admin/test_admin_pages.py`.

- [ ] **Step 5: Commit**

```bash
rtk git add templates/admin/base.html templates/admin/_stats_panel.html templates/admin/keys.html templates/admin/_keys_table.html templates/admin/history.html templates/admin/_history_table.html templates/admin/logs.html templates/admin/_logs_table.html templates/admin/_logs_stream.html tests/admin/test_admin_pages.py
rtk git commit -m "fix: finish admin desktop polish verification"
```

---

## Plan Review

Subagent review is normally required by the skill, but the current tool policy only allows delegation when the user explicitly asks for subagents. For this run, perform a local review against the same checklist from `plan-document-reviewer-prompt.md` before executing:

- Completeness: no placeholder markers remain and every task has executable steps
- Spec Alignment: only desktop hierarchy, density, and console-framing work is included
- Task Decomposition: shared shell, dashboard, table pages, logs, and verification are separated cleanly
- Buildability: each task names exact files, expected markers, and test commands
