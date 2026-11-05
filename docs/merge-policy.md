# Merge Policy & Risk Classification

This document specifies the merge policy and risk governance model for the **Grok Bot Agent Factory**.

---

## 1. Core Principle

**Only low-risk pull requests may autonomously auto-merge.**  
Everything else requires human review and explicit approval from **César** (`cesarchavezcal`).

---

## 2. Risk Classification Rules

Risk classification is determined automatically from the pull request diff (changed paths, additions, and deletions) by `scripts/classify_pr_risk.py` and enforced in CI (`.github/workflows/ci.yml`).

### Low-Risk Criteria (`low-risk`)

A pull request is classified as **`low-risk`** if and only if it meets one of the following conditions:

1. **Documentation-only**: All changed files are documentation (e.g. `*.md`, `docs/*`, `*.txt`, `*.rst`), provided no protected/control plane paths are modified.
2. **Tests-only**: All changed files are test files (e.g. `tests/*`, `*_test.py`, `*.test.ts`), provided no protected/control plane paths are modified.
3. **Small Code Fix**: A small fix under **50 changed lines** (total additions + deletions < 50) that touches **zero** protected or high-risk paths.

### High-Risk / Needs-Approval Criteria (`needs-approval`)

A pull request is classified as **`needs-approval`** if any of the following are true:

- **Workflows**: Modifies any GitHub Action workflow (`.github/workflows/*`).
- **Models**: Modifies model routing or permitted model registries (`models.yml`, `models.allowed.yml`).
- **Dependencies**: Modifies any package manifest or lockfile (`package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.).
- **Factory Architecture**: Modifies core factory configuration or schemas (`.factory/*`).
- **Control Plane & Self-Evolution (ADR 0001)**: Modifies `AGENTS.md` or any agent prompt/skill (`.agents/skills/*`). Per [ADR 0001](adr/0001-hitl-delivery-gate-for-skill-evolution.md), self-evolution strictly requires human sign-off.
- **Large Diffs**: Any code change where total changed lines (additions + deletions) $\ge 50$.

---

## 3. Autonomous Merge Gate Requirements

For a pull request to auto-merge autonomously:

1. **Risk Classification**: The PR must be classified as **`low-risk`** (labeled `low-risk`).
2. **Required Status Check**: The **`ci`** required check must pass on the current head commit rebased onto `main`.
3. **Independent Interrogation**: The independent Grok 4.7 audit pass must yield a `PASS` verdict.
4. **Merge Method**: Squash merge ONLY (`gh pr merge <PR_NUMBER> --squash`). Branches are never deleted (`delete_branch_on_merge=false`).

If a pull request is classified as **`needs-approval`**, autonomous auto-merge is strictly halted:
- The agent reports **`waiting for César`** in the thread final message.
- The PR remains open awaiting manual review and merge by César.

---

## 4. GitHub Ruleset & Branch Protection Configuration

To enforce this policy at the repository level:

### Required Settings on `main`

1. **Branch Protection / Ruleset Target**: `main`
2. **Require a pull request before merging**:
   - Required approvals: **1 approval** (from `cesarchavezcal` or designated CODEOWNERS).
   - Dismiss stale pull request approvals when new commits are pushed.
   - Require review from Code Owners.
3. **Require status checks to pass before merging**:
   - Require branches to be up to date before merging (`strict: true`).
   - Required status check: **`ci`**.
4. **Require linear history**: Enabled.
5. **Merge method**: Allow squash merging only; disable merge commits and rebase merging.
6. **Branch preservation**: Automatically delete head branches must remain **DISABLED**.
7. **Force pushes and deletions**: Disallowed (`allow_force_pushes=false`, `allow_deletions=false`).

### Manual Administration Note

> [!IMPORTANT]
> **César applies repo settings by hand** if the agent token cannot.
> Due to GitHub Free permissions or GitHub App token administrative scopes, agents cannot modify live organization/repository rulesets directly. Agents must never attempt to override or bypass live repository settings without César.

---

## 5. Invariants (Don't Touch)

- The required check name is strictly **`ci`**.
- All merges are **squash merges**.
- Branches are **never deleted**.
- **ADR 0001** is immutable: self-evolution PRs never auto-merge.
- Live repository settings are managed solely with César's administrative authorization.
