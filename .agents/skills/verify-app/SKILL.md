---
name: verify-app
description: Stub verification skill. Copy to .agents/skills/verify-<app> when initializing a project. Drive the real user surface, capture runtime evidence, and clean up without deleting proof.
---

# Verify app (template)

Replace every placeholder before using this as runtime proof. Read `features/README.md` first.

**App:** `<app>`  
**Surface:** `<web | cli | api>`  
**Harness:** `<playwright | curl | pty>`

## Launch

Exact command that starts a disposable instance on an isolated port/data directory, and the ready signal (log line or health URL). Include teardown.

```bash
# TODO: disposable launch command (isolated port / data dir)
```

## Doctor

Read-only check: process up, expected URL or binary, data dir owned by this run. Refuse to drive a shared or unknown instance.

```bash
# TODO: doctor command
```

## Drive

Stable handles only (ARIA roles/labels, data attributes, CLI flags, HTTP routes). Pair each user action with a command and an observable result. Feature recipes live in `features/`.

## Evidence

Write `artifacts/<work-item-id>/`. Capture the action and the resulting state:
- **UI / Frontend**:
  - ARIA snapshot + screenshot across all interactive states.
  - **Mandatory `break-ui` Stress-Test**: Feed worst-case data (long unbreakable strings, zero items, 1-item boundary, extreme counts, non-Latin/emoji text) to ensure layout resilience without clipping or text overlap. Output findings to `artifacts/<work-item-id>/break-ui.json`.
  - **Mandatory `match` Visual Parity**: When modifying or implementing UI components against a design reference or spec, perform a side-by-side comparison using `match`. Verify computed styles, spacing, typography tokens, and multi-state parity (hover, focus, disabled, empty, error). Record comparisons in `artifacts/<work-item-id>/match-report.md`.
- **CLI / API / Backend**: stdout, stderr, HTTP status, and exit code (`0`).
- **Mutations**: a second read-only check proving persisted state.

## Pass / Fail Criteria & Exit Codes

Phase 4a verification strictly passes only when:
1. The verification runner terminates cleanly with **`exitCode === 0`**.
2. For UI changes:
   - `break-ui` reports zero unhandled regressions, container blowouts, or text collisions.
   - `match` reports zero unresolved visual differences against the target specification.
3. Proof artifacts are written to `artifacts/<work-item-id>/` before opening or updating a PR.

## Cleanup

Kill only the PID or process this run started. Remove temporary fixture data. **Keep `artifacts/<work-item-id>/`.**

