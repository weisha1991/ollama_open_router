# Admin Desktop Polish Design

Date: 2026-06-11

## Overview

Polish the redesigned Ollama Router admin UI for desktop-first operations use. This is a focused follow-up to the broader admin redesign completed on 2026-06-10.

The goal is not to change product capabilities or rework navigation. The goal is to make the existing admin pages feel more like a mature desktop control console by tightening hierarchy, reducing decorative vertical space, and improving information density for table-heavy workflows.

## Relationship To Prior Work

This design builds on:

- `docs/superpowers/specs/2026-06-10-admin-ui-redesign-design.md`
- `docs/superpowers/plans/2026-06-10-admin-ui-redesign.md`

That earlier redesign established the shell, visual language, and page structure. This follow-up design is intentionally narrower:

- keep the new visual system
- preserve the existing routes and HTMX behavior
- improve desktop rhythm, scanability, and operational tone

## Approved Direction

The approved direction is the "recommended" middle path rather than a conservative micro-tune or an aggressive re-layout.

This means:

- compress page headers on desktop
- establish clearer primary vs secondary emphasis on the dashboard
- increase desktop information density modestly
- strengthen table and log scanning behavior
- keep mobile out of scope for this pass

## Goals

- Make the admin feel more like a production desktop console and less like a polished generic backend.
- Reduce above-the-fold vertical waste on `keys`, `history`, and `logs`.
- Create clearer information hierarchy on `dashboard` so the first screen has one obvious focal area.
- Improve readability and scanning efficiency for desktop tables and log surfaces.
- Tighten spacing, padding, and rhythm across admin pages so they feel like one system.
- Preserve all existing behaviors, endpoints, and server-rendered data flows.

## Non-Goals

- No mobile-specific improvements in this pass.
- No route changes or navigation restructuring.
- No backend data model changes.
- No new charts, metrics, or operational features.
- No redesign of login, authentication, or session behavior.
- No conversion away from Jinja2 + HTMX.

## Current State

The current redesign already solves the major visual problems of the original admin UI. The remaining issues are mostly at the desktop refinement level:

- `dashboard` still distributes emphasis too evenly across KPI cards and panels
- `keys`, `history`, and `logs` retain page headers that are slightly too tall and presentation-like for a dense console
- several desktop panels are still a little over-padded, which lowers information density
- table-heavy pages can scan faster with stronger row framing and more disciplined spacing
- `logs` is functional and attractive, but its tab/filter/stream combination can feel more like a specialized console surface

These are not usability blockers. They are maturity and efficiency issues.

## Design Principles

### 1. Lower The Header

Desktop operations pages should move the user into actionable content quickly. Large hero treatment is appropriate for first-pass redesign energy, but for day-to-day control-panel use it should step back.

### 2. Make The Hierarchy Obvious

Each page should have a dominant area and supporting areas. If every block has similar visual weight, the interface feels flatter and requires more cognitive sorting.

### 3. Increase Density Without Looking Cramped

This pass should trim excess space, not crush the UI. The target is "efficient and composed", not "maximal data on screen at any cost".

### 4. Optimize For Scanning

Desktop admin usage is mostly repeated monitoring and quick decision-making. Layout, row treatment, labels, and numeric alignment should all help the eye land quickly.

### 5. Preserve Existing Product Character

The current redesign's dark-console language is still correct. This pass should sharpen it, not replace it with a new visual concept.

## Page-Level Design

### Dashboard

`/admin/dashboard` should become the clearest expression of system status.

Changes:

- promote one primary panel area in the first screen so the page has a visible center of gravity
- slightly reduce the visual dominance of supporting KPI cards so they read as summary instruments rather than equal peers to the main panel
- tighten card padding and vertical gaps for desktop
- make supporting blocks feel subordinate through spacing, border weight, and title rhythm rather than by hiding information

Desired effect:

- a user can glance at the page and quickly understand current system condition
- the page feels composed rather than evenly tiled

### Keys

`/admin/keys` should feel like a key operations console.

Changes:

- compress the page intro/header so the add-key form and table start higher on the screen
- tighten spacing between the summary area, action panel, and table container
- improve table scanning through clearer header framing, row separation, and compact but readable cell padding
- keep status badges prominent while reducing decorative whitespace around them

Desired effect:

- faster scanning of key status, cooldown state, and available actions
- less page height consumed before the main table begins

### History

`/admin/history` should read as a monitoring table first.

Changes:

- reduce the vertical footprint of the title/summary area
- make the request table the visual priority
- strengthen tabular scan cues for status, method, path, and latency
- tighten row rhythm and panel padding on desktop

Desired effect:

- quicker logbook-style reading
- less sensation of reading a "sectioned landing page"

### Logs

`/admin/logs` should feel the most specialized and console-like page in the admin.

Changes:

- compress the page header
- give the tab switcher/filter area stronger structure so mode selection feels deliberate
- make the historical log table and live stream panel feel like purpose-built surfaces rather than generic cards
- tune spacing, framing, and typography so live log monitoring feels stable and technical

Desired effect:

- clearer separation between historical inspection and live monitoring
- stronger operator-console personality

## Shared Desktop System Changes

The polish work should primarily land in `templates/admin/base.html` and shared admin partials.

### Header Rhythm

- reduce desktop-only top section padding
- tighten the gap between title, subtitle, and action row
- avoid large hero-like breathing room on data pages

### Panel Density

- modestly reduce panel padding on desktop
- rebalance internal spacing so titles, toolbars, and content blocks feel grouped
- preserve generous spacing only where it improves comprehension

### Table Language

- strengthen visual distinction between table head and body
- make row boundaries easier to follow without becoming noisy
- improve numeric and status scanability
- ensure compact rows remain comfortably readable

### Console Framing

- give specialized surfaces such as logs a slightly firmer visual frame
- use border, background layering, and spacing to imply purpose rather than adding new decorative elements

### Cross-Page Consistency

- align title scale and subtitle behavior across `dashboard`, `keys`, `history`, and `logs`
- normalize button sizing and toolbar spacing
- keep consistent radius, border intensity, and shadow treatment across panels

## Files Expected To Change

- `templates/admin/base.html`
- `templates/admin/_stats_panel.html`
- `templates/admin/keys.html`
- `templates/admin/history.html`
- `templates/admin/logs.html`
- supporting table/log partials as needed:
  - `templates/admin/_keys_table.html`
  - `templates/admin/_history_table.html`
  - `templates/admin/_logs_table.html`
  - `templates/admin/_logs_stream.html`

## Implementation Notes

- Prefer desktop-targeted CSS adjustments rather than broad structural rewrites.
- Reuse the existing component language and class system wherever possible.
- Do not change HTMX endpoints, polling behavior, or SSE behavior unless required for a visual container fix.
- Keep the work incremental and low risk: polish should emerge from spacing, hierarchy, and framing rather than a new layout paradigm.

## Testing And Verification

Verification for this pass should include:

- desktop visual QA on:
  - `/admin/dashboard`
  - `/admin/keys`
  - `/admin/history`
  - `/admin/logs`
- confirmation that existing HTMX refresh areas still render correctly
- confirmation that logs tab switching and live stream view still work
- regression testing with the existing admin test suite
- ideally full `pytest -q` for repo-wide confidence after the UI polish

## Risks

- over-tightening density could make the interface feel cramped instead of efficient
- dashboard hierarchy changes could accidentally weaken useful summary visibility
- shared spacing changes in `base.html` could create uneven effects on pages not explicitly targeted

The implementation should therefore favor small, legible shifts over aggressive compression.

## Success Criteria

This pass is successful if:

- desktop pages show more data sooner without looking crowded
- `dashboard` has a clearer focal structure
- `keys`, `history`, and `logs` feel more tool-like and less hero-driven
- table-heavy views scan faster and feel more deliberate
- the admin remains visually cohesive with the redesign from 2026-06-10
- all existing admin behaviors continue to work unchanged
