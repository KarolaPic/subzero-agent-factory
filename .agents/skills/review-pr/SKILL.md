---
name: review-pr
description: Autonomous reviewer agent skill that inspects PR diffs, task cards, and test evidence, then submits formal GitHub PR reviews (Approve or Request Changes) using a dedicated GitHub App / reviewer identity.
---

# Reviewer Agent (`review-pr`)

Autonomous code review skill designed for pull request verification and approval within the Grok Bot Agent Factory. It acts as the independent reviewer agent in the three-tier risk governance model, inspecting PR diffs, task card specifications, and test evidence before submitting a formal GitHub Pull Request Review (`APPROVE` or `REQUEST_CHANGES`).

---

## Workflow Overview

```
PR Diff + Task Card (Goal, Done when, Don't touch) + Test Evidence
                             │
                             ▼
     [Phase 1: Model Resolution & Invariant Verification]
       ├─ Read auditor model from models.yml
       ├─ Verify auditor != builder
       ├─ Verify zero Argon / Claude / GPT models
       └─ If unavailable: STOP immediately (NO fallback)
                             │
                             ▼
     [Phase 2: Adversarial Code & Spec Review]
       ├─ Diff inspection (diff economy, cleanliness, scope)
       ├─ Task card alignment (Goal & Done when fulfilled?)
       ├─ Negative constraint check (Don't touch respected?)
       ├─ Verification check (Runtime tests passing? Evidence present?)
       └─ Risk tier validation (No unflagged high-risk paths)
                             │
                             ▼
     [Phase 3: Formal Review Submission]
       ├─ Submit formal GitHub PR Review via GitHub App / Bot token
       ├─ If all criteria met ──► Event: APPROVE
       └─ If issues found ──────► Event: REQUEST_CHANGES with concrete findings
                             │
                             ▼
     [Phase 4: Review Loop & Escalation Guard]
       ├─ Track review rounds (Round 1 .. 3)
       ├─ If approved ──────────► Auto-merge gate unblocked
       └─ If round > 3 ─────────► HALT execution & report to César
```

---

## Phase 1: Model Resolution & Invariant Verification

1. **Auditor Model Resolution**:
   - Model is configured as **`auditor`** dynamically read from [`models.yml`](../../../models.yml) (e.g. `grok-4.7` or Gemini at differing effort from builder).
   - **Auditor != Builder Rule**: The `auditor` model MUST NOT be the same model as the `builder` model.
   - **Gemini Preference & Differing Effort**: When Gemini models are used, builder and auditor must operate at differing reasoning efforts (e.g. `gemini-3.8-flash-high` builder vs `gemini-3.8-flash-medium` or distinct auditor).
   - **Strict Prohibitions**: Zero Argon, Claude, or GPT models across all review orchestration.
2. **Model Availability Gate**:
   - If the configured `auditor` model is unavailable or encounters an API error, **stop immediately and report to César**.
   - **NO fallback model** and **NO silent degradation** are permitted.

---

## Phase 2: Adversarial Code & Spec Review

The reviewer agent inspects three core artifacts for every PR:

1. **Pull Request Diff**:
   - Fetched via `gh pr diff <PR_NUMBER>` or the review engine.
   - Assesses diff economy: are changes minimal, focused, and free of extraneous file additions or debug code?
   - Checks security: zero exposed credentials, tokens, or uncommitted secrets.
2. **Issue Task Card**:
   - Extracted from the issue description (`gh issue view <ISSUE_NUMBER>`).
   - Validates three mandatory task card sections:
     - **Goal**: Does the PR fulfill the stated objective?
     - **Done when**: Are all acceptance checkboxes and criteria completely implemented and verifiable?
     - **Don't touch**: Have all negative constraints been strictly respected without accidental modifications?
3. **Runtime & Test Verification Evidence**:
   - Inspects test run output (e.g. `python3 -m unittest discover tests` with `exitCode === 0`).
   - Confirms that test evidence is present in the PR body under `## How it was tested`.
   - If tests are missing or failing, approval is withheld.
4. **Risk Classification Check**:
   - Evaluates changes against [`scripts/classify_pr_risk.py`](../../../scripts/classify_pr_risk.py).
   - PRs touching high-risk paths (`high-risk` / `needs-approval`) must halt for César; reviewer agent never auto-approves high-risk changes for merge.

---

## Phase 3: Formal Review Submission Engine

The reviewer agent submits formal GitHub Pull Request Reviews using [`scripts/review_pr.py`](../../../scripts/review_pr.py):

1. **Identity & Authentication**:
   - Reviews are submitted under a dedicated **GitHub App** or bot account identity.
   - Token precedence: `REVIEWER_GITHUB_TOKEN` -> `GITHUB_APP_TOKEN` -> `GH_TOKEN` -> `GITHUB_TOKEN`.
2. **Review Action (`gh pr review`)**:
   - **Approval**:
     ```bash
     gh pr review <PR_NUMBER> --approve --body "<Approval summary detailing verified criteria>"
     ```
   - **Request Changes**:
     ```bash
     gh pr review <PR_NUMBER> --request-changes --body "<Numbered list of concrete, actionable findings>"
     ```
3. **Communication Invariant (Zero Bot Comments)**:
   - **Strict Rule**: No bot comments on issues or PRs other than the **formal GitHub PR review**.
   - Never post standalone PR discussion comments or issue comments. All feedback must be submitted through the official GitHub Review event (`APPROVE` or `REQUEST_CHANGES`).

---

## Phase 4: Review Loop Enforcement (Max 3 Rounds)

1. **Round Tracking**:
   - Review rounds are tracked incrementally per PR (Round 1, Round 2, Round 3).
   - If changes are requested, the builder agent performs rework and opens a new review round.
2. **Max 3 Rounds Escalation**:
   - A maximum of **3 review rounds** is strictly enforced.
   - If the PR is still not approved after 3 rounds:
     - The reviewer agent **halts execution immediately**.
     - It sets review state to `blocked` (exit code 2).
     - Reports the failure and remaining findings directly to **César** in the thread final message.
3. **Branch Preservation**:
   - Reviewer agent and merge workflows **NEVER delete branches**. Never pass `--delete-branch`.
