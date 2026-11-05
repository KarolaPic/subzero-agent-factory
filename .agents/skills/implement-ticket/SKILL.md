---
name: implement-ticket
description: High-level orchestrator skill that takes an issue ticket through plan, build, audit, PR, and merge
---

# Implement Ticket Orchestrator (`implement-ticket`)

High-level orchestrator skill designed for autonomous feature tickets and issue-driven development following the Grok Bot Agent Factory model.

---

## Workflow Overview

```
1. Intake & Context Scout (Configured builder or subagents model)
     ↓
2. Planning & Grilling (Configured planner model from models.yml: plan in thread; questions? stop & ask; no questions? build immediately)
     ↓
3. Build (Configured builder model from models.yml: poteto-mode + tdd)
     ↓
4. Verification (Configured builder model: verify-app)
     ↓
5. Independent Adversarial Audit (Configured auditor model from models.yml, must differ from builder)
     ↓ (If audit fails: rework with planner or builder model distinct from auditor, max 2 retries)
6. PR & Squash Merge (Closes #N; green CI 'ci' + audit PASS; gh pr merge --squash without --delete-branch)
     ↓
7. Deploy Check (Deploy ONLY if issue has 'deploy' label, after green merge)
```

---

## Phase 1: Intake & Context Scout

- **Trigger**: Issue carries the `agent` label (and does not carry `bug` or `epic`).
  - *Precedence Rule*: `epic` takes highest precedence (routes to `plan-epic`), followed by `bug` (routes to `fix-bug`).
- **Model Resolution (`models.yml`)**:
  - Read configured models from [`models.yml`](../../../models.yml).
  - **Model Not Available Rule**: If any required model is unavailable in the environment, **stop and tell the user immediately**. Do NOT use a fallback model, and do NOT retry.
- **GitHub Account Invariant**:
  - Every commit, push, and PR must use the GitHub account `cesarchavezcal`.
  - Check `gh auth status` first before any push or `gh` command; if not `cesarchavezcal`, remember the active account, switch with `gh auth switch --user cesarchavezcal`, and switch back when done.
  - Maintain git email `cesarchavezcal@gmail.com` via `includeIf`, never changing the global git email.
- Parse issue number `#N`, title, description, and attached labels.
- Perform targeted read-only reconnaissance across the codebase.
- Produce a tight context brief (`<2KB`) listing relevant files, existing patterns, tests, and documentation.

---

## Phase 2: Planning & Grilling (Plan-Then-Build Protocol)

- **Planner Model**: Read `planner` from [`models.yml`](../../../models.yml).
- **Skills**:
  - [`wayfinder`](../wayfinder/SKILL.md): Locate key seams, interfaces, and architecture boundaries.
  - [`grill-with-docs`](../grill-with-docs/SKILL.md): Challenge proposed changes against existing architecture, domain models, and ADRs.
  - [`domain-modeling`](../domain-modeling/SKILL.md): Align terminology and entities.
  - [`to-spec`](../to-spec/SKILL.md): Write a clear, testable specification before coding.
- **Plan-Then-Build Rules**:
  1. **Task Card Check**: Check the issue task card first. If **Goal**, **Done when**, or **Don't touch** is missing, ambiguous, or incomplete, stop immediately and ask in the thread final message per `AGENTS.md` Section 2.
  2. **Thread Plan First**: Every issue thread starts with a short plan directly in the thread (files, tests, verification).
  3. **Self-Deduce First**: Exhaustively resolve technical choices, types, conventions, and constraints from the codebase, git history, and documentation.
  4. **Open Questions (Stop Gate)**: If ANY open question, scope ambiguity, or product trade-off remains:
     - **NEVER comment on the issue or PR**.
     - Stop execution immediately without editing files.
     - Write the questions directly in the **thread final message**. The external dispatcher (**Grok Bot**) will relay the questions to César and pause until answered.
  5. **No Questions (Immediate Build)**: If there are NO open questions:
     - Write `"No questions, starting build"`.
     - Continue directly to the build (Phase 3) in the same run without waiting for a separate build message.

---

## Phase 3: Build (`poteto-mode` + `tdd`)

- **Builder Model**: Read `builder` from [`models.yml`](../../../models.yml). Sub-agents use `subagents` from `models.yml`.
- **Discipline**:
  - Follow official [`poteto-mode`](../poteto-mode/SKILL.md) under the `autopilot-full` playbook:
    - **Reproduce / Benchmark**: Verify current baseline state.
    - **Test First ([`tdd`](../tdd/SKILL.md))**: Author failing automated tests isolating expected behavior.
    - **Fix / Implement**: Write minimal, clean code to turn tests green.
    - **Refactor & Verify**: Clean up seams and ensure zero test regressions.

---

## Phase 4: Runtime Verification & Independent Audit

1. **Runtime Verification**:
   - Model: Configured `builder` model.
   - Run the application verification suite ([`verify-app`](../verify-app/SKILL.md) / `verify-<app>`).
   - Verify all unit, integration, and runtime checks pass cleanly (`exitCode === 0`).
2. **Adversarial Audit**:
   - Model: Read `auditor` from [`models.yml`](../../../models.yml).
   - Invariant: Auditor MUST differ from builder.
   - Read-only independent audit of diff, spec adherence, security implications, and edge cases.
3. **Rework Rule**:
   - If verification fails or audit returns findings:
     - Escalate rework using configured `planner` or `builder` model distinct from `auditor`.
     - Maximum 2 rework attempts (`maxRetries: 2`).
     - If still unresolved after 2 retries, stop and report blocker in the thread final message.

---

## Phase 5: PR & Squash Merge

1. **GitHub Account & Identity Rule**:
   - Every commit, push, and PR must use the GitHub account `cesarchavezcal`.
   - Run `gh auth status` first before any push or `gh` command. If the active account is not `cesarchavezcal`, remember the previous active account, switch using `gh auth switch --user cesarchavezcal`, and switch back to the earlier account when done.
   - Maintain the git email `cesarchavezcal@gmail.com` via `includeIf`, and never change the global git email.
2. **Branch & PR**:
   - Create a feature branch off `main`: `feat/<work-item-id>`.
   - Commit changes as `cesarchavezcal` (`cesarchavezcal@gmail.com`).
   - Open a PR targeting `main`.
   - **PR Template Mandate**: PR body MUST strictly follow the short 4-section template (`.github/PULL_REQUEST_TEMPLATE.md`): `Why`, `What changed`, `How it was tested` (combining runtime verification and Grok audit verdict, with models used read dynamically from `models.yml`), and `Closes #N`.
   - **Issue Link Invariant**: PR body MUST include `Closes #N` so GitHub automatically closes the issue upon merge. If this issue carries the `deploy` label as the final sub-issue of an epic, the PR body MUST ALSO include `Closes #<EPIC_NUMBER>`.
3. **Merge Gate**:
   - Merge ONLY when:
     - Required status check **`ci`** is green on the current head rebased onto `main`.
     - Independent verification and Grok audit returned `PASS`.
4. **Merge Command (No Branch Deletion)**:
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
