---
name: implement-ticket
description: High-level orchestrator skill that takes an issue ticket through plan, build, audit, PR, and merge
---

# Implement Ticket Orchestrator (`implement-ticket`)

High-level orchestrator skill designed for autonomous feature tickets and issue-driven development following the Grok Bot Agent Factory model.

---

## Workflow Overview

```
1. Intake & Context Scout (Gemini 3.8 Flash Low)
     ↓
2. Planning & Grilling (Gemini 3.8 Flash High: wayfinder + grill-with-docs)
     ↓ (If clarification needed: stop and write questions in thread final message; NEVER comment on issue)
3. Build (Gemini 3.8 Flash Medium / Grok 4.7 Fast: poteto-mode + tdd)
     ↓
4. Verification (Gemini 3.8 Flash Medium: verify-app)
     ↓
5. Independent Adversarial Audit (Grok 4.7 High: GROK_AUDIT)
     ↓
6. Independent Security Audit (Grok 4.7 High: audit-security)
     ↓ (If audit fails: rework with Gemini 3.8 Flash High, max 2 retries)
7. PR & Squash Merge (Closes #N; green CI 'ci' + audits PASS; gh pr merge --squash without --delete-branch)
     ↓
8. Deploy Check (Deploy ONLY if issue has 'deploy' label, after green merge)
```

---

## Phase 1: Intake & Context Scout

- **Trigger**: Issue carries the `agent` label (and does not carry `bug` or `epic`).
  - *Precedence Rule*: `epic` takes highest precedence (routes to `plan-epic`), followed by `bug` (routes to `fix-bug`).
- **Scout Model**: `antigravity::gemini-3.8-flash-low` (`effort: low`).
- Parse issue number `#N`, title, description, and attached labels.
- Perform targeted read-only reconnaissance across the codebase.
- Produce a tight context brief (`<2KB`) listing relevant files, existing patterns, tests, and documentation.

---

## Phase 2: Planning & Grilling

- **Planner Model**: `antigravity::gemini-3.8-flash-high` (`effort: high`).
- **Skills**:
  - [`wayfinder`](../wayfinder/SKILL.md): Locate key seams, interfaces, and architecture boundaries.
  - [`grill-with-docs`](../grill-with-docs/SKILL.md): Challenge proposed changes against existing architecture, domain models, and ADRs.
  - [`domain-modeling`](../domain-modeling/SKILL.md): Align terminology and entities.
  - [`to-spec`](../to-spec/SKILL.md): Write a clear, testable specification before coding.
- **Grilling Rules**:
  1. **Self-Deduce First**: Exhaustively resolve technical choices, types, conventions, and constraints from the codebase, git history, and documentation.
  2. **Questions for César**: If genuine product, scope, or trade-off ambiguities remain:
     - **NEVER comment on the issue or PR**.
     - Stop execution immediately.
     - Write a single numbered block of 2–3 questions in the **thread final message**. The external dispatcher (**Grok Bot**) will relay the block to César and pause until answered.

---

## Phase 3: Build (`poteto-mode` + `tdd`)

- **Builder Models**:
  - Standard UI / CRUD / Frontend: `antigravity::gemini-3.8-flash-medium` (`effort: medium`).
  - Complex Backend / DB / Concurrency: `grok::grok-4.7-build-fast` (`reasoningEffort: medium`).
- **Discipline**:
  - Follow official [`poteto-mode`](../poteto-mode/SKILL.md) under the `autopilot-full` playbook:
    - **Reproduce / Benchmark**: Verify current baseline state.
    - **Test First ([`tdd`](../tdd/SKILL.md))**: Author failing automated tests isolating expected behavior.
    - **Fix / Implement**: Write minimal, clean code to turn tests green.
    - **Refactor & Verify**: Clean up seams and ensure zero test regressions.

---

## Phase 4: Runtime Verification, Adversarial Audit & Security Audit

1. **Runtime Verification (Phase 4a)**:
   - Model: `antigravity::gemini-3.8-flash-medium` (`effort: medium`).
   - Run the application verification suite ([`verify-app`](../verify-app/SKILL.md) / `verify-<app>`).
   - Verify all unit, integration, and runtime checks pass cleanly (`exitCode === 0`).
2. **Adversarial Audit (Phase 4b)**:
   - Model: `grok::grok-4.7` (`reasoningEffort: high`, `GROK_AUDIT`, [`.cursor/agents/interrogator-grok.md`](../../../.cursor/agents/interrogator-grok.md)).
   - Read-only independent audit of diff, spec adherence, and edge cases (`verdict: PASS`).
3. **Security Audit (Phase 4c)**:
   - Model: `grok::grok-4.7` (`reasoningEffort: high`, `GROK_AUDIT`, [`.cursor/agents/security-auditor.md`](../../../.cursor/agents/security-auditor.md)).
   - Skill: [`audit-security`](../audit-security/SKILL.md).
   - Audit AST patterns, secrets, dependencies, and LLM/agent boundaries. Produce `artifacts/<work-item-id>/security-report.json` (`verdict: PASS`).
4. **Rework Rule**:
   - If verification, adversarial interrogation, or security audit fails:
     - Escalate rework to **`antigravity::gemini-3.8-flash-high`** (effort: high).
     - **Invariant**: The rework model is ALWAYS from a different family than the auditor (`grok-4.7`).
     - Maximum 2 rework attempts (`maxRetries: 2`).
     - If still unresolved after 2 retries, stop and report blocker in the thread final message.

---

## Phase 5: PR & Squash Merge

1. **Branch & PR**:
   - Create a feature branch off `main`: `feat/<work-item-id>`.
   - Commit changes as `cesarchavezcal` (`cesarchavezcal@gmail.com`).
   - Open a PR targeting `main`.
   - **Issue Link Invariant**: PR body MUST include `Closes #N` so GitHub automatically closes the issue upon merge. If this issue carries the `deploy` label as the final sub-issue of an epic, the PR body MUST ALSO include `Closes #<EPIC_NUMBER>`.
2. **Merge Gate**:
   - Merge ONLY when:
     - Required status check **`ci`** is green on the current head rebased onto `main`.
     - Independent verification, Grok interrogation, and Security audit all returned `PASS`.
3. **Merge Command (No Branch Deletion)**:
   - Execute squash merge:
     ```bash
     gh pr merge <PR_NUMBER> --squash
     ```
   - **Strict Rule**: NEVER pass `--delete-branch`. Never delete branches.

---

## Phase 6: Epic Sub-Issue Deploy Rule

- **Deploy Check**:
  - Inspect the issue labels for the **`deploy`** label.
  - If the issue carries the **`deploy`** label:
    - This is the designated final sub-issue of an epic.
    - Execute deployment steps ONLY AFTER the PR has cleanly merged to `main` with green CI.
  - If the issue does NOT carry the `deploy` label:
    - **No deploy**. Complete the ticket without deploying.
