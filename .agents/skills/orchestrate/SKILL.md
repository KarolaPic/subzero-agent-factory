---
name: orchestrate
description: Unified top-level orchestrator interface for all factory flows ($orchestrate [plan | bug | code | <request>]), routing to plan-epic, fix-bug, implement-ticket, or run-epic.
---

# Unified Orchestrator (`orchestrate`)

The single entry point for orchestrating software engineering lifecycles in the Grok Bot Agent Factory. Instead of having to remember multiple disconnected commands (`$run-epic`, `$plan-epic`, `$implement-ticket`, `$fix-bug`), you invoke **`$orchestrate`** with an optional subcommand.

---

## Command Routing Matrix

```
$orchestrate <subcommand> [args]
```

| Invocations | Target Intent | Delegated Skill | Core Discipline |
| :--- | :--- | :--- | :--- |
| **`$orchestrate plan <#N \| request>`** | **Planning Only (Initiative)** | [`plan-epic`](../plan-epic/SKILL.md) | Decomposes epic into vertical tracer-bullet sub-issues. Verifies `agent` on 100% and `deploy` on final. **Zero implementation code**. |
| **`$orchestrate bug <#N \| request>`** | **Defect Repair (Single)** | [`fix-bug`](../fix-bug/SKILL.md) | Reproduction-first hard gate (`ce-debug` causal chain) -> TDD failing test -> root cause fix -> changelog entry (`scripts/update_changelog.py`) -> verification -> Grok audit -> squash merge. |
| **`$orchestrate code <#N \| request>`** | **Feature Ticket (Single)** | [`implement-ticket`](../implement-ticket/SKILL.md) | Plan-then-build in thread (`wayfinder` + `grill-with-docs`) -> `poteto-mode` TDD build -> changelog entry (`scripts/update_changelog.py`) -> Grok audit -> reviewer agent approval -> squash merge. |
| **`$orchestrate <#N \| request>`**<br>*(Default with no subcommand)* | **Full Autonomous Initiative** | [`run-epic`](../run-epic/SKILL.md) | End-to-end loop: discovers/creates issue, auto-decomposes, iteratively executes each slice in dependency order, handles changelog updates, gates, deploys on final. |

---

## Subcommand Details

### 1. Plan Mode: `$orchestrate plan <#N | query>`
Use when you want to analyze an initiative, break it down, and file cleanly formatted GitHub sub-issues without building code yet.
- **Underlying Engine**: [`plan-epic`](../plan-epic/SKILL.md)
- **Model**: `epic_planner` from [`models.yml`](../../../models.yml)
- **Rules**:
  - Pure decomposition: modifies zero application files.
  - Every created sub-issue MUST receive the `agent` label.
  - Exactly one final sub-issue receives the `deploy` label.
  - Enforces mandatory post-creation verification gate before exiting.

### 2. Defect Mode: `$orchestrate bug <#N | query>`
Use when fixing a reported bug, crash, or regression.
- **Underlying Engine**: [`fix-bug`](../fix-bug/SKILL.md)
- **Models**: `builder` and `auditor` from [`models.yml`](../../../models.yml) (enforces `auditor != builder`)
- **Rules**:
  - **Reproduction-First Hard Gate**: Never write fixes without reproducing the symptom first. If unable to reproduce or questions remain, stops and asks in thread final message.
  - **TDD Red Phase**: Writes a failing automated test isolating the root cause before fixing.
  - **Zero Band-Aids**: Eliminates root causes via `ce-debug` rather than swallowing exceptions.

### 3. Code Mode: `$orchestrate code <#N | query>`
Use when building a single discrete feature or task.
- **Underlying Engine**: [`implement-ticket`](../implement-ticket/SKILL.md)
- **Models**: `planner`, `builder`, `auditor`, and `scorer` from [`models.yml`](../../../models.yml)
- **Rules**:
  - **Plan-Then-Build Protocol**: Thread plan first. If questions, stops and asks. If no questions, writes `"No questions, starting build"` and proceeds immediately.
  - Follows `poteto-mode` `autopilot-full` with TDD.
  - Autonomous Reviewer Agent gate (`scripts/review_pr.py`) + 3-tier risk policy (`scripts/classify_pr_risk.py`).

### 4. Default Mode: `$orchestrate <#N | query>`
Use when you want full autonomous execution of an entire epic or multi-step initiative from a single prompt.
- **Underlying Engine**: [`run-epic`](../run-epic/SKILL.md)
- **Rules**:
  - Accepts explicit `#N` or free text query.
  - Runs `scripts/find_or_create_issue.py` (searches open issues or creates new issue with task card & hidden marker `<!-- run-epic-request: ... -->`).
  - Reuses existing sub-issues or invokes `plan-epic` to generate them.
  - Executes sub-issues sequentially in dependency order, dispatching `fix-bug` for bug tickets and `implement-ticket` for features.
  - Handles PR review loop, merge gates, and final deployment.

---

## Backward Compatibility & Aliases

To preserve existing muscle memory and automated scripts, the legacy top-level skill names remain active as direct aliases to `$orchestrate`:
- `$plan-epic ...` $\to$ `$orchestrate plan ...`
- `$fix-bug ...` $\to$ `$orchestrate bug ...`
- `$implement-ticket ...` $\to$ `$orchestrate code ...`
- `$run-epic ...` $\to$ `$orchestrate ...`
