---
name: fix-bug
description: High-level orchestrator skill that reads issue/error/logs, reproduces first, writes failing tests, and fixes root causes using ce-debug and principle-fix-root-causes
---

# Fix Bug Orchestrator (`fix-bug`)

High-level bug fixing skill for autonomous defect triage, reproduction-first diagnosis, root-cause repair, and safe delivery.

---

## Workflow Overview

```
1. Intake: Read issue, description, reproduction steps, and error logs
     ↓
2. Reproduce First (Hard Gate)
     ├─ Cannot reproduce? → STOP immediately. Write question in thread final message (NEVER comment on issue).
     └─ Reproduced! → Proceed to Phase 3.
3. Write Failing Test (Red Phase via tdd)
     ↓
4. Root Cause Fix (ce-debug + principle-fix-root-causes)
     ↓
5. Verification: All tests pass + run the application once
     ↓
6. Independent Adversarial Audit (Grok 4.7 High: GROK_AUDIT)
     ↓
7. Independent Security Audit (Grok 4.7 High: audit-security)
     ↓ (If audit fails: rework with Gemini 3.8 Flash High, max 2 retries)
8. PR & Squash Merge (Closes #N; green CI 'ci' + audits PASS; gh pr merge --squash without --delete-branch)
     ↓
9. Deploy Check (Deploy only if issue carries 'deploy' label, after green merge)
```

---

## Phase 1: Intake & Triage

- **Trigger**: Issue carries labels `bug` + `agent` (and does NOT carry `epic`).
  - *Precedence Rule*: If an issue carries `epic` + `bug` + `agent`, **`plan-epic` takes precedence**.
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
  - If the bug CANNOT be reproduced after attempting the provided steps and inspecting logs:
    - **DO NOT guess, assume, or apply speculative fixes.**
    - **NEVER comment on the GitHub/Linear issue or PR.**
    - Stop execution immediately.
    - Write the detailed reproduction obstacle and questions for César in the **thread final message**. The external dispatcher (**Grok Bot**) will relay it to César.

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

## Phase 6: Independent Audit, Security Audit & Rework

1. **Grok 4.7 Adversarial Audit**:
   - Model: `grok::grok-4.7` (`reasoningEffort: high`, `GROK_AUDIT`, [`.cursor/agents/interrogator-grok.md`](../../../.cursor/agents/interrogator-grok.md)).
   - Audit verifies that the fix addresses the true root cause rather than applying a symptom patch, and that the reproduction test proves correctness (`verdict: PASS`).
2. **Security Audit**:
   - Model: `grok::grok-4.7` (`reasoningEffort: high`, `GROK_AUDIT`, [`.cursor/agents/security-auditor.md`](../../../.cursor/agents/security-auditor.md)).
   - Skill: [`audit-security`](../audit-security/SKILL.md).
   - Audit verifies zero introduced security weaknesses, no exposed secrets, and no weakened authorization in the bug fix (`verdict: PASS`).
3. **Rework Rule**:
   - If adversarial audit or security audit fails, rework is assigned to **`antigravity::gemini-3.8-flash-high`** (effort: high).
   - Rework builder is strictly from a different model family from the Grok auditor.
   - **Max Retries**: Exactly **2 rework attempts** (`maxRetries: 2`). If still unresolved after 2 attempts, stop immediately and report the blocker in the thread final message.

---

## Phase 7: PR & Squash Merge

1. **Branch & PR**:
   - Create branch: `fix/<issue-number>-<short-description>`.
   - Commit as `cesarchavezcal` (`cesarchavezcal@gmail.com`).
   - PR body MUST include `Closes #N` so GitHub automatically closes the bug report upon merge. If the bug is the final deploy sub-issue of an epic, also include `Closes #<EPIC_NUMBER>`.
   - Include root-cause explanation, reproduction evidence, and test diff in the PR description.
2. **Squash Merge**:
   - Merge ONLY when required status check **`ci`** is green, Grok adversarial interrogation returns `PASS`, and Security audit returns `PASS`.
   - Merge command (never delete branches):
     ```bash
     gh pr merge <PR_NUMBER> --squash
     ```
   - **Strict Rule**: NEVER pass `--delete-branch`. Never delete branches.

---

## Phase 8: Epic Sub-Issue Deploy Rule

- **Deploy Check**:
  - Inspect the issue labels for the **`deploy`** label.
  - If the issue carries the **`deploy`** label:
    - This is the designated final sub-issue of an epic.
    - Execute deployment steps ONLY AFTER the PR has cleanly merged to `main` with green CI.
  - If the issue does NOT carry the `deploy` label:
    - **No deploy**. Complete the ticket without deploying.
