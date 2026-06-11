# Admin UI Redesign Design

Date: 2026-06-10

## Overview

Redesign the existing Ollama Router admin interface to match the provided dark operations-dashboard prototype while preserving the current FastAPI + Jinja2 + HTMX architecture and the existing admin routes.

The redesign should make the admin panel feel like one cohesive product rather than a collection of utility pages. `dashboard` is the visual anchor and should align most closely with the reference, while `login`, `keys`, `history`, and `logs` should inherit the same layout system, component language, and dark-console aesthetic.

## Reference Input

Approved visual reference:

- `/data1/lzb/download/_https_github.com_weisha1991_ollamaopenrouter_UI_..png`

The implementation should treat this image as the primary visual benchmark for shell styling, dashboard composition, panel treatment, and overall UI tone.

## Goals

- Match the reference prototype's overall visual language:
  - dark blue-black application shell
  - purple primary accent
  - green / amber / red semantic status colors
  - layered panels, restrained glow, and monitoring-console density
- Keep existing admin routes and server-side rendering model:
  - `/admin/login`
  - `/admin/dashboard`
  - `/admin/keys`
  - `/admin/history`
  - `/admin/logs`
- Improve visual consistency across all admin pages through a shared shell and reusable components.
- Reorganize existing data into a more polished dashboard-style presentation without inventing backend capabilities that do not exist.
- Preserve current operational workflows such as login, HTMX refreshes, key management actions, history viewing, and log streaming.

## Non-Goals

- No migration to React, Vue, or a separate SPA frontend.
- No admin authentication redesign or session model changes.
- No heavyweight charting library as a prerequisite for the redesign.
- No new backend business features outside what is needed to support the refreshed UI presentation.
- No fabricated metrics or fake data fields just to mimic the reference exactly.

## Current State

The current admin panel is a multi-page Jinja2 interface built on a shared base template:

- `templates/admin/base.html` provides the shell, sidebar, top bar, and global Tailwind setup.
- `templates/admin/dashboard.html` renders a simple stats block.
- `templates/admin/keys.html`, `history.html`, and `logs.html` each render functional but visually plain operations views.
- Admin data is prepared in:
  - `ollama_router/admin/views.py`
  - `ollama_router/admin/routes.py`

The existing system already has a good architectural boundary for a redesign because all pages share the same shell and data comes from stable server-side helpers.

## Design Direction

### Visual Tone

The redesigned admin should feel like a refined infrastructure console:

- deep navy background rather than flat black
- soft panel contrast and subtle border glow
- dense but readable information layout
- compact utility controls with a premium look
- dashboard-first information hierarchy

The reference image should guide layout rhythm, panel framing, spacing, and emphasis, but implementation should remain grounded in the real capabilities of this project.

### Product Character

The interface should feel:

- operational
- calm
- precise
- modern
- trustworthy

It should not feel like a generic CRUD backend, nor like a marketing page, nor like a neon-heavy gimmick UI.

## Page-Level Design

### 1. Login

`/admin/login` should become a branded dark entry screen that clearly belongs to the same admin product as the rest of the console.

Requirements:

- retain the existing username/password form and HTMX login flow
- redesign the container, typography, spacing, focus styling, and button treatment
- align color usage with the admin shell palette
- keep the form simple and fast to use
- keep error feedback clear and visible without adding extra workflow steps

### 2. Dashboard

`/admin/dashboard` is the highest-fidelity page relative to the prototype.

Target layout:

- top row of four stat cards
  - total keys
  - available keys
  - cooldown keys
  - total requests
- middle row with two panels
  - request overview / request trend on the left
  - key status distribution on the right
- bottom row with two panels
  - recent keys
  - recent activity

Behavior:

- continue periodic refresh using HTMX
- reorganize existing server data into richer visual sections
- use lightweight chart-like rendering appropriate to server-rendered templates

### 3. Keys

`/admin/keys` should feel like a dedicated key operations console rather than a plain form-plus-table page.

Target layout:

- top summary area derived from key status data
- prominent but compact add-key action panel
- upgraded table with emphasis on:
  - masked key identity
  - current status
  - cooldown information
  - reason
  - action controls
- clear highlighting for the currently in-use key

Behavior:

- preserve add / disable / reset / delete flows
- retain confirmation prompts for destructive or state-changing actions
- keep HTMX-driven refresh behavior

### 4. History

`/admin/history` should read as a monitoring view.

Target layout:

- top summary band or cards
- large, polished request table
- clear visual coding for method, status, and latency
- better scanning for timestamps and endpoints

Behavior:

- continue periodic refresh
- preserve existing history source and record semantics

### 5. Logs

`/admin/logs` should remain dual-mode but look substantially more integrated into the redesigned console.

Target layout:

- segmented or tabbed mode switch for:
  - historical logs
  - real-time logs
- history mode styled as a data inspection surface
- real-time mode styled like a console/stream panel

Behavior:

- keep current historical log and real-time stream capabilities
- preserve existing client-side tab switching and SSE behavior
- improve visual differentiation between passive history viewing and live stream monitoring

## Shared Layout System

The redesign should establish a stronger shared shell in `templates/admin/base.html`.

### Sidebar

The left sidebar should contain:

- product/brand area at the top
- primary navigation in the middle
- a bottom utility/status zone for system state and product version context

The selected nav item should be clearly active and visually aligned with the reference style.

### Top Bar

The top bar should become more intentional and product-like, with:

- page title and optional subtitle support
- room for lightweight utility controls or status affordances
- a better-integrated logout action

The implementation does not need to recreate every decorative control from the reference if it is not functionally relevant, but the top bar should feel equally structured.

### Content Grid

The main content area should use a consistent panel grid system:

- shared horizontal padding
- repeatable card and panel spacing
- consistent panel radii
- stable responsive collapse behavior

## Reusable Component System

The redesign should produce a small reusable visual system across templates.

At minimum, the following component patterns should be standardized:

- stat card
- section panel
- data table
- status badge
- action button
- segmented tabs
- empty state
- login form shell

These do not have to be Jinja macros if local patterns make includes/classes simpler, but the rendered result must be visually consistent and easy to maintain.

## Data Mapping Rules

The UI should map only to real existing data.

### Dashboard Stats

These should use the existing stats helper data from `ollama_router/admin/views.py`:

- `total_keys`
- `available_keys`
- `cooldown_keys`
- `total_requests`

### Recent Keys

Should use the existing key list representation and present:

- masked key value
- availability/disabled/cooldown state
- cooldown timing when relevant
- reason when relevant
- current in-use status when available

### Recent Activity

Should be derived from request history, but reformatted into a shorter dashboard activity list rather than a duplicate of the full history table.

### Request Overview

Should be built from request history using a lightweight aggregation strategy suitable for server-rendered presentation. Exact visualization may be approximate, but it should truthfully reflect recent traffic shape from available request history.

### Key Status Distribution

Should represent real status categories only. If the reference uses categories that do not exist in the current backend, the redesigned UI should adapt the visual rather than invent unsupported states.

## Interaction Rules

- Keep HTMX partial refresh where already used.
- Preserve existing add/reset/disable/delete key actions.
- Preserve current login and logout workflow.
- Preserve periodic refresh for dashboard, keys, and history, but ensure the refreshed UI does not feel jumpy or unstable.
- Preserve logs page historical and realtime behavior.
- Preserve confirmation prompts for risky actions.

The redesign may refine client-side presentation details, but should not degrade current operational speed.

## Responsive Behavior

Desktop is the primary target and should align most closely with the reference.

Responsive requirements:

- sidebar collapses cleanly on narrower screens
- dashboard multi-column panels collapse into single-column layouts without overlap
- tables remain readable through overflow handling and layout tuning
- no text clipping in buttons, badges, headers, or cards

## Accessibility and Usability

- preserve strong text contrast in the dark theme
- keep keyboard focus visible on all interactive controls
- maintain readable label sizes in dense tables and controls
- avoid relying only on color for status meaning where a label can reinforce it
- keep dangerous actions visually distinguishable from neutral actions

## Technical Approach

### Frontend Stack

Keep the current stack:

- Jinja2 templates
- Tailwind via CDN configuration already used in templates
- HTMX for partial updates
- existing inline JavaScript only where necessary

### Chart Strategy

Do not add a heavyweight frontend chart dependency as the foundation of the redesign.

Preferred options:

- lightweight SVG-based visualizations
- CSS-based chart-like decoration where sufficient
- minimal inline logic to render trends/distributions from server-provided data

The goal is believable, stable visuals that fit the design, not maximum chart interactivity.

### Backend Support

Backend changes should be minimal and targeted:

- expand view-layer context only as needed for richer presentation
- keep route contracts stable where possible
- avoid unnecessary new APIs when server-rendered templates can use existing data

## Files Likely in Scope

Primary template files:

- `templates/admin/base.html`
- `templates/admin/login.html`
- `templates/admin/dashboard.html`
- `templates/admin/keys.html`
- `templates/admin/history.html`
- `templates/admin/logs.html`
- partials such as:
  - `templates/admin/_stats_panel.html`
  - `templates/admin/_keys_table.html`
  - `templates/admin/_history_table.html`
  - `templates/admin/_logs_table.html`
  - `templates/admin/_logs_stream.html`

Primary backend files:

- `ollama_router/admin/views.py`
- `ollama_router/admin/routes.py`

Additional backend changes are acceptable only if needed to provide cleaner, real data for the redesigned dashboard and page summaries.

## Acceptance Criteria

The redesign is complete when:

1. All admin pages share a cohesive dark-console design system.
2. `dashboard` clearly reflects the reference prototype's layout hierarchy and visual tone.
3. `keys`, `history`, `logs`, and `login` visibly belong to the same product family as `dashboard`.
4. Existing admin functionality still works:
   - login/logout
   - dashboard refresh
   - key management actions
   - history viewing
   - log history
   - real-time log streaming
5. No unsupported or fake backend data is introduced.
6. Desktop and narrow-screen layouts remain usable and do not visibly break.

## Testing and Validation

### Functional Validation

- run existing automated tests relevant to admin behavior
- add or adjust focused tests if template/context changes require coverage
- verify no regressions in login, key management, history rendering, or log interfaces

### Visual Validation

Run the app locally and verify each page in the browser:

- `/admin/login`
- `/admin/dashboard`
- `/admin/keys`
- `/admin/history`
- `/admin/logs`

Check for:

- consistency of shell, spacing, and component styling
- accurate status color semantics
- readable tables and cards
- stable refresh behavior
- no overflow or layout collisions
- clear alignment with the approved prototype direction

## Implementation Boundaries

The implementation should stay focused on the admin redesign itself.

Allowed:

- template restructuring
- shared admin styling cleanup
- improved template partial organization
- minor view-layer data shaping to support visual sections

Out of scope:

- unrelated backend refactors
- new admin feature sets unrelated to presentation
- architecture migration to a client-rendered app
- speculative analytics systems beyond current request history capabilities
