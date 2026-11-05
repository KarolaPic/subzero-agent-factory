---
name: fix-bug
description: High-level orchestrator skill that reads issue/error/logs, reproduces first, writes failing tests, and fixes root causes using ce-debug and principle-fix-root-causes
---

# Fix Bug Orchestrator (`fix-bug`)

High-level bug fixing skill for autonomous defect triage, reproduction-first diagnosis, root-cause repair, and safe delivery.

---

## Workflow Overview

```
1. Intake: Read issue, reproduction steps, and error logs (short plan in thread)
     ↓
2. Reproduce First (Hard Gate)
     ├─ Cannot reproduce or open questions? → STOP immediately. Write in thread final message (NEVER comment on issue).
     └─ Reproduced & no questions! → Write "No questions, starting build" and proceed immediately to Phase 3.
3. Write Failing Test (Red Phase via tdd using configured builder model)
     ↓
4. Root Cause Fix (ce-debug + principle-fix-root-causes)
     ↓
5. Verification: All tests pass + run the application once
     ↓
6. Independent Audit (Configured auditor model from models.yml, must differ from builder)
     ↓ (If audit fails: rework with builder/planner distinct from auditor, max 2 retries)
7. PR & Squash Merge (Closes #N; green CI 'ci' + audit PASS; gh pr merge --squash without --delete-branch)
     ↓
8. Deploy Check (Deploy only if issue carries 'deploy' label, after green merge)
```

---

## Phase 1: Intake & Triage (Plan-Then-Build Protocol)

- **Trigger**: Issue carries labels `bug` + `agent` (and does NOT carry `epic`).
  - *Precedence Rule*: If an issue carries `epic` + `bug` + `agent`, **`plan-epic` takes precedence**.
- **Model Resolution (`models.yml`)**:
  - Read configured models from [`models.yml`](../../../models.yml).
  - **Model Not Available Rule**: If any required model is unavailable in the environment, **stop and tell the user immediately**. Do NOT use a fallback model, and do NOT retry.
- **Plan-Then-Build Protocol**:
  - Check the bug task card first; if **Goal** (or What happened/Expected), **Done when**, or **Don't touch** is missing, ambiguous, or incomplete, ask in the thread final message and stop immediately per `AGENTS.md` Section 2.
  - Every issue thread starts with a short plan directly in the thread (reproduction approach, files to inspect/modify, tests to author, verification).
- **GitHub Account & Identity Invariant**:
  - Every commit, push, and PR must use the GitHub account `cesarchavezcal`.
  - Check `gh auth status` first before any push or `gh` command; if not `cesarchavezcal`, remember the active account, switch using `gh auth switch --user cesarchavezcal`, and switch back when done.
  - Maintain git email `cesarchavezcal@gmail.com` via `includeIf`, and never change the global git email.
- Extract structured inputs from the bug issue form:
  - **What happened** (unexpected behavior or crash symptom)
  - **Expected behavior** (desired correct state)
  - **Steps to reproduce** (exact sequence of actions)
  - **Error messages / stack traces / logs**

---

## Phase 2: Mandatory Reproduction (Hard Gate)

- Before touching source code or modifying logic, **reproduce the bug**:
  - Run the steps in a local checkout or isolated test environment.
  - Confirm the exact error or failure symptom described in the issue.
- **Stop-and-Ask Rule**:
  - If the bug CANNOT be reproduced after attempting the provided steps and inspecting logs, or if ANY open question remains:
    - **DO NOT guess, assume, or apply speculative fixes.**
    - **NEVER comment on the GitHub/Linear issue or PR.**
    - Stop execution immediately without editing files.
    - Write the detailed reproduction obstacle and questions for César in the **thread final message**. The external dispatcher (**Grok Bot**) will relay it to César.
- **No Questions Gate (Immediate Build)**:
  - If the bug is reproduced and there are NO open questions:
    - Write `"No questions, starting build"`.
    - Continue immediately to the build (Phase 3 Failing Test & Phase 4 Root Cause Fix) in the same run without waiting for a separate build message.

---

## Phase 3: Failing Test (TDD Red Phase)

- Author a minimal automated reproduction test (unit, integration, or end-to-end seam test).
- Run the test and confirm:
  - The test fails consistently.
  - The failure output matches the reported defect or stack trace.
- Keep the test isolated, deterministic, and free of unnecessary dependencies.

---

## Phase 4: Root Cause Fix (`ce-debug` + `principle-fix-root-causes`)

Enforce root-cause engineering discipline directly in the fix:

### 1. `ce-debug` Causal Chain Protocol
- **Trace the full chain**: Map execution backwards from symptom $\to$ intermediate invalid state $\to$ root cause trigger.
- **No logical gaps**: Do not propose or write a fix until the complete causal chain can be explained without assumptions.
- **Form falsifiable predictions**: If multiple hypotheses exist, test alternate code paths or state values to eliminate side effects.
- **One variable at a time**: Make atomic, targeted changes. Never shotgun-debug multiple unrelated files or speculative modifications.

### 2. `principle-fix-root-causes` Directives
- **Zero Band-Aids**:
  - Resist adding fallback guards, null checks (`if (!x) return null`), or catch-all exception swallowers that merely suppress a crash without addressing where the invalid state originated.
  - If a variable is unexpectedly null/undefined, find where it was initialized, mutated, or passed incorrectly and fix the origin.
- **The Five Whys**:
  - Ask *why* iteratively until reaching the architectural, data-flow, or lifecycle flaw that allowed the bug to exist.
- **Anti-Pattern Awareness**:
  - Long defensive comment justifications are a code smell indicating architectural evasion. Fix the root mechanism instead.
- **Persistent State Checks**:
  - If a bug only manifests after a restart or in specific environments, check for stale caches, lockfiles, or serialized state before blaming runtime code.

---

## Phase 5: Verification

1. **Verify Failing Test**: Re-run the reproduction test and confirm it now passes cleanly.
2. **Regression Check**: Run the entire test suite (`npm test`, `pytest`, `go test`, or repo test harness) to verify zero regressions.
3. **Run the App Once**:
   - Start or execute the application runtime once (e.g., via [`verify-app`](../verify-app/SKILL.md) or application entrypoint check) to guarantee the application boots and serves without fatal crashes or startup regressions.

---

## Phase 6: Independent Audit & Rework

1. **Independent Audit**:
   - Model: Read `auditor` from [`models.yml`](../../../models.yml).
   - Invariant: Auditor MUST differ from the builder model.
   - Audit verifies that the fix addresses the true root cause rather than applying a symptom patch, and that the reproduction test proves correctness.
2. **Rework Rule**:
   - If audit fails, rework is assigned to the configured `planner` or `builder` model, strictly distinct from the `auditor`.
   - **Max Retries**: Exactly **2 rework attempts** (`maxRetries: 2`). If still unresolved after 2 attempts, stop immediately and report the blocker in the thread final message.

---

## Phase 7: PR, Reviewer Agent Gate & Squash Merge

1. **GitHub Account & Identity Rule**:
   - Every commit, push, and PR must use the GitHub account `cesarchavezcal`.
   - Run `gh auth status` first before any push or `gh` command. If the active account is not `cesarchavezcal`, remember the previous active account, switch using `gh auth switch --user cesarchavezcal`, and switch back to the earlier account when done.
   - Maintain the git email `cesarchavezcal@gmail.com` via `includeIf`, and never change the global git email.
2. **Branch & PR**:
   - Create branch: `fix/<issue-number>-<short-description>`.
   - Commit as `cesarchavezcal` (`cesarchavezcal@gmail.com`).
   - **T3 PR Scoring Rule (`scripts/score_pr.py`)**:
     - T3 scores each opened PR diff using the configured `scorer` model from `models.yml` (default `gemini-3.8-flash-low`, signed-in model session, zero paid API keys).
     - If the scorer model is unavailable, stop immediately and report in thread final message with zero fallback or retries.
     - The PR score (1–10 + concise rationale) is placed in the PR body under `## How it was tested` (`- **PR Score**: <score>/10 — <short reason> (scorer: <model>)`).
   - **PR Template Mandate**: PR body MUST strictly follow the short 4-section template (`.github/PULL_REQUEST_TEMPLATE.md`): `Why`, `What changed`, `How it was tested` (combining root-cause reproduction evidence, runtime verification, Grok audit verdict, and PR score, with models used read dynamically from `models.yml`), and `Closes #N`.
   - PR body MUST include `Closes #N` so GitHub automatically closes the bug report upon merge. If the bug is the final deploy sub-issue of an epic, also include `Closes #<EPIC_NUMBER>`.
3. **Autonomous Reviewer Agent Gate ([`review-pr`](../review-pr/SKILL.md))**:
   - After opening the PR, the builder dispatches the autonomous reviewer agent (`scripts/review_pr.py`):
     ```bash
     python3 scripts/review_pr.py --pr <PR_NUMBER> --issue <ISSUE_NUMBER>
     ```
   - Reviewer agent operates with `auditor` model from `models.yml` (differs from `builder`, Gemini with differing effort, zero Argon/Claude/GPT, no fallback).
   - Reviewer reads the PR diff, bug task card, and test evidence, then records its evaluation (`APPROVE` or `REQUEST_CHANGES`) directly in the PR body under `## Reviewer Agent` and in the run log.
   - **Review Loop (Max 3 Rounds)**:
     - If `REQUEST_CHANGES` is evaluated, builder addresses findings in up to 3 review rounds.
     - If not approved after 3 rounds, execution **halts immediately** and reports blocker to César in the thread final message.
4. **Three-Tier Risk Merge Policy (`scripts/classify_pr_risk.py`)**:
   - **`low-risk`**: Auto-merges upon green `ci` check.
   - **`normal`**: Auto-merges upon green `ci` check **AND** reviewer agent approval recorded in the PR body.
   - **`high-risk` / `needs-approval`**: **NEVER auto-merges autonomously**. Halts and reports "waiting for César" in the thread final message per ADR 0001.
5. **Merge Command & Run Log Recording**:
   - Execute squash merge:
     ```bash
     gh pr merge <PR_NUMBER> --squash
     ```
   - **Strict Rule**: NEVER pass `--delete-branch`. Never delete branches.
   - **No Bot Comments Invariant**: No bot comments on PRs or issues.
   - **Run Log Recording**: Record the run outcome with the evaluated PR score into `.factory/runs/runs.jsonl`:
     ```bash
     python3 scripts/run_log.py record --issue <ISSUE_NUMBER> --pr <PR_NUMBER> --result merged --score <SCORE>
     ```

---

## Phase 8: Epic Sub-Issue Deploy Rule

- **Deploy Check**:
  - Inspect the issue labels for the **`deploy`** label.
  - If the issue carries the **`deploy`** label:
    - This is the designated final sub-issue of an epic.
    - Execute deployment steps ONLY AFTER the PR has cleanly merged to `main` with green CI.
  - If the issue does NOT carry the `deploy` label:
    - **No deploy**. Complete the ticket without deploying.
