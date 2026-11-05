# Merge Policy & Risk Classification

This document specifies the merge policy and risk governance model for the **Grok Bot Agent Factory**.

---

## 1. Core Principle

**PRs auto-merge only when verified and approved within authorized risk boundaries.**
- **`low-risk`**: Auto-merges upon green CI and independent audit/verification.
- **`normal`**: Routes to the autonomous reviewer agent (`review-pr`); auto-merges upon green CI and formal reviewer approval.
- **`high-risk`**: Strictly halts autonomous merge and requires human review and sign-off from **César** (`cesarchavezcal`).

---

## 2. Three-Tier Risk Classification Model

Risk classification is determined automatically from the pull request diff (changed paths, additions, and deletions) by `scripts/classify_pr_risk.py` and enforced in CI (`.github/workflows/ci.yml`).

### A. Low-Risk Criteria (`low-risk`)

A pull request is classified as **`low-risk`** if and only if it meets one of the following conditions with zero high-risk paths:

1. **Documentation-only**: All changed files are documentation (e.g. `*.md`, `docs/*`, `*.txt`, `*.rst`).
2. **Tests-only**: All changed files are test files (e.g. `tests/*`, `*_test.py`, `*.test.ts`).
3. **Small Code Fix**: A small fix under **50 changed lines** (total additions + deletions < 50) that touches **zero** high-risk paths.

### B. Normal Risk Criteria (`normal`)

A pull request is classified as **`normal`** if:
- It contains standard code changes where total changed lines (additions + deletions) $\ge 50$.
- It touches **zero** high-risk or protected paths.
- It routes to the autonomous **reviewer agent** (`review-pr`) for independent review and formal approval.

### C. High-Risk Criteria (`high-risk` / `needs-approval`)

A pull request is classified as **`high-risk`** if it touches any protected infrastructure or high-risk domain:

1. **Auth & Secrets**: Modifies credentials, tokens, or environment configs (`.env*`, `auth/*`, `secrets/*`, credential management).
2. **Workflows**: Modifies any GitHub Action workflow (`.github/workflows/*`).
3. **Branch Rules & Rulesets**: Modifies rulesets or branch protection (`.github/rulesets/*`, ruleset definitions).
4. **Dependencies**: Modifies any package manifest or lockfile (`package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.).
5. **Models**: Modifies model routing or permitted model registries (`models.yml`, `models.allowed.yml`).
6. **Migrations & Deletions**: Modifies database schemas, migrations (`migrations/*`, `*.sql`), or destructive deletions.
7. **Deploy**: Modifies deployment scripts or container configs (`deploy/*`, `Dockerfile`, `docker-compose.*`).
8. **Factory Architecture**: Modifies core factory configuration or schemas (`.factory/*`).
9. **Control Plane & Self-Evolution (ADR 0001)**: Modifies `AGENTS.md` or any agent prompt/skill (`.agents/skills/*`). Per [ADR 0001](adr/0001-hitl-delivery-gate-for-skill-evolution.md), self-evolution strictly requires human sign-off.

---

## 3. Autonomous Merge Gate Requirements

For a pull request to auto-merge autonomously:

1. **Required Status Check**: The **`ci`** required check must pass on the current head commit rebased onto `main`.
2. **Review & Approval Gate**:
   - **`low-risk`**: Passing independent audit (or reviewer approval).
   - **`normal`**: Reviewer agent **approval** (`review-pr`) recorded directly in the PR body and run log.
3. **Merge Method**: Squash merge ONLY (`gh pr merge <PR_NUMBER> --squash`). Branches are never deleted (`delete_branch_on_merge=false`).

If a pull request is classified as **`high-risk`**, autonomous auto-merge is strictly halted:
- The agent reports **`waiting for César`** in the thread final message.
- The PR remains open awaiting manual review and merge by César.

---

## 4. GitHub Ruleset & Branch Protection Configuration

To enforce this policy at the repository level on `main`:

### Required Ruleset / Branch Protection Settings on `main`

1. **Target Branch**: `main` (fnmatch: `main`)
2. **Require a pull request before merging**:
   - **Required approvals**: **0 required approving reviews** (`required_pull_request_reviews: null`). Reviewer agent approval is tracked via the PR body and run log, allowing single-account execution under `cesarchavezcal`.
3. **Require status checks to pass before merging**:
   - **Require branches to be up to date before merging** (`strict: true`).
   - **Required status check**: Exactly **`ci`** (defined in `.github/workflows/ci.yml`).
4. **Require linear history**: Enabled.
5. **Merge method**: Allow squash merging only; disable merge commits and rebase merging.
6. **Branch preservation**: Automatically delete head branches must remain **DISABLED** (`delete_branch_on_merge=false`).
7. **Force pushes and deletions**: Disallowed (`allow_force_pushes=false`, `allow_deletions=false`).

### Reviewer Verdict in PR Body & Run Log

The autonomous reviewer agent operates without requiring a separate GitHub App or secondary token:
- **Verdict and Findings**: Appended/updated in the target PR body (`gh pr edit <PR_NUMBER> --body ...`) under `## Reviewer Agent`.
- **Run Log Recording**: Stored directly in `.factory/runs/runs.jsonl` under `review_result`, `review_rounds`, and `reviewer_model`.
- **Zero Bot Comments**: The reviewer agent never creates standalone discussion comments or issue comments.

### Manual Administration Note

> [!IMPORTANT]
> **César applies repo settings by hand** if the agent token cannot.
> Due to GitHub Free permissions, agents cannot modify live organization/repository rulesets directly. Agents must never attempt to override or bypass live repository settings without César.

---

## 5. End-to-End Reviewer Flow Verification Checklist

Verify the entire automated review and merge pipeline before live production use:

- [ ] **Model Resolution**: `models.yml` specifies `auditor: <model>` distinct from `builder: <model>` (Gemini at differing effort, zero Argon/Claude/GPT, no fallback).
- [ ] **Reviewer Verdict in PR Body**: Reviewer agent updates the PR body with verdict (`APPROVE` or `REQUEST_CHANGES`), round count, and findings.
- [ ] **Run Log Record**: Reviewer metrics (`review_result`, `review_rounds`, `reviewer_model`) recorded in `.factory/runs/runs.jsonl`.
- [ ] **Branch Protection on `main`**: Requires `ci` required status check (`strict: true`), 0 required GitHub reviews (`required_pull_request_reviews: null`), linear history enabled, branch deletion disabled.
- [ ] **Three-Tier Risk Triage**:
  - `low-risk` PRs: Auto-merge upon green `ci` check.
  - `normal` PRs: Auto-merge upon green `ci` check + reviewer agent approval recorded in PR body.
  - `high-risk` PRs: Auto-merge halted; stops and reports "waiting for César" in thread final message.
- [ ] **Review Loop Guard**: Enforces max 3 review rounds. If unapproved after 3 rounds, halts for César.
- [ ] **Zero Bot Comments**: No bot comments posted on PRs or issues.
- [ ] **Branch Preservation**: All PR merges use `gh pr merge --squash` without `--delete-branch`.
- [ ] **Single Account Identity**: All actions executed under `cesarchavezcal`.

---

## 6. Invariants (Don't Touch)

- The required check name is strictly **`ci`**.
- All merges are **squash merges**.
- Branches are **never deleted**.
- **ADR 0001** is immutable: self-evolution PRs never auto-merge.
- Live repository settings are managed solely with César's administrative authorization.
