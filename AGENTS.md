# AGENTS.md — Grok Bot Agent Factory

This repository is an autonomous software factory powered by **T3 Code**, official **`mattpocock/skills`**, and official **`pstack` (`poteto-mode`)**, coordinated with an external dispatcher (**Grok Bot**).

---

## 0. Creating a New Project & `template init`

> **Visibility Rule (GitHub Free):** While the template `cesarchavezcal/grok-bot-agent-factory` remains **PRIVATE**, **every working repository created from this template MUST be PUBLIC** (`--public`) so that GitHub Free permits branch protection (`ci` required status check) and `allow_auto_merge`.

When an agent or **Grok Bot** creates a new working project from this template:

```bash
# 1. Create the new working repository as PUBLIC from the private template
gh repo create <name> --public --template cesarchavezcal/grok-bot-agent-factory --clone
cd <name>

# 2. Run idempotent bootstrap (or `./scripts/init.sh --create-repo <name>` from a local dir)
./scripts/init.sh
```

What [`./scripts/init.sh`](scripts/init.sh) does (idempotent, safe to re-run at any time):
1. **Tool & Auth Verification**: Verifies `git`, `gh` (authenticated), `node`, and `npx` with clear diagnostic messages.
2. **Official Skills Sync**: Installs/restores official upstream skills pinned by commit SHA and hash in [`skills-lock.json`](skills-lock.json) (`wayfinder`, `grill-with-docs`, `grilling`, `domain-modeling`, `to-spec`, `to-tickets`, `tdd`, `poteto-mode`), and checks that [`.agents/skills/verify-app/SKILL.md`](.agents/skills/verify-app/SKILL.md) is present.
3. **GitHub Labels**: Runs [`./scripts/setup-labels.sh`](scripts/setup-labels.sh) to ensure `agent`, `epic`, `deploy`, `bug`, and workflow state labels exist.
4. **Merge Policy & Branch Protection (`gh api`)**:
   - Calls `gh api PATCH repos/<owner>/<repo>` to enable `allow_auto_merge=true`, `allow_squash_merge=true`, `allow_merge_commit=false`, `allow_rebase_merge=false`, and `delete_branch_on_merge=false` (branches are preserved).
   - Calls `gh api PUT repos/<owner>/<repo>/branches/main/protection` to protect `main` with the required status check **`ci`** (`strict: true`), linear history, and conversation resolution.
   - If the repository is private on a GitHub Free plan (API returns `403 / Upgrade to GitHub Pro`), it prints an **explicit warning** with the command to make the working repo public (`gh repo edit <repo> --visibility public --accept-visibility-change-consequences`) and does not fail silently.
5. **Factory Config & T3 Registration**: Updates the `app` slug in [`.factory/config.json`](.factory/config.json) and prints the optional T3 Code registration call (`t3_project_create`).

---

## 1. Intake & Routing Matrix (`agent`, `bug`, `epic`, `security` Labels)

- **Entry Condition**: Only issues from **GitHub Issues** or **Linear** carrying the **`agent`** label are eligible for execution.
- **Ignore Rule**: Any issue without the `agent` label MUST be ignored completely.
- **Routing Matrix & Precedence**:
  - **`epic` + `agent`** -> **[`plan-epic`](.agents/skills/plan-epic/SKILL.md)**: Planning-only thread that splits an epic into vertical sub-issues (`Part of #N`). Every created sub-issue MUST receive the `agent` label; exactly one final sub-issue receives the `deploy` label. Verify all sub-issues have `agent` before completing.
    - *Precedence*: `epic` takes priority over all other labels. If an issue carries `epic` + `bug` + `agent`, it routes to `plan-epic`.
  - **`security` + `agent`** -> **[`audit-security`](.agents/skills/audit-security/SKILL.md)**: Dedicated security audit and vulnerability triage. Audits code, secrets, dependencies, and agent surfaces. If standalone defects exist, creates structured issues (`fix(security): ...`, labels `bug,agent,security`) without raw secrets, prompting Grok Bot to orchestrate resolution via `fix-bug`.
  - **`bug` + `agent`** -> **[`fix-bug`](.agents/skills/fix-bug/SKILL.md)**: Reads issue/error/logs -> reproduces first (if it cannot reproduce, stop and ask César in thread final message) -> writes failing test -> fixes root cause (`ce-debug`, `tdd`, `principle-fix-root-causes`) -> verifies all tests + runs the app once -> Grok audit & security audit -> PR `Closes #N` -> squash merge on green CI.
  - **`agent` alone (or with `feature`)** -> **[`implement-ticket`](.agents/skills/implement-ticket/SKILL.md)**: Full lifecycle feature delivery: plan (`grill-with-docs` + `wayfinder`) -> build (`poteto-mode` reproduce, test, fix, verify) -> Grok audit & security audit -> rework rule -> PR `Closes #N` -> squash merge on green CI.
- **Manual Labeling Order (`epic` before `agent`)**:
  - When manually adding labels to an existing issue in GitHub or Linear, **always add `epic` before `agent`** so `epic` is already present on the issue payload when `agent` triggers `.github/workflows/notify-grok.yml`.
- **Deploy Rule**:
  - Deploy only in the last sub-issue of an epic (carrying the **`deploy`** label), after its green merge.
  - Intermediate sub-issues never deploy.
- **Issue Closing Rule**:
  - PR bodies MUST use `Closes #N` (never `Refs #N`) so the issue closes automatically when the PR merges; for epics, the final deploy sub-issue PR also includes `Closes #EPIC`.
  - Agents never close issues by hand; issues close only when their PR merges.
- **Work-Item State**: Each accepted issue is tracked in `.factory/work-items/<id>.json` following [`.factory/work-item.schema.json`](.factory/work-item.schema.json). Do not commit runtime work-item JSON files unless explicitly asked.

---

## 2. Pipeline Stages & Skills

| Stage | Primary Skill(s) | Active Model (`provider::model`) | Pool |
| :--- | :--- | :--- | :--- |
| **Phase 0: Context Scout** | Repo exploration & context brief (`<2KB`) | `antigravity::gemini-3.8-flash-low` | `AGY_FAST` |
| **Phase 1: Discovery & Grilling** | [`wayfinder`](.agents/skills/wayfinder/SKILL.md), [`grill-with-docs`](.agents/skills/grill-with-docs/SKILL.md), [`grilling`](.agents/skills/grilling/SKILL.md), [`domain-modeling`](.agents/skills/domain-modeling/SKILL.md) | `antigravity::gemini-3.8-flash-high` | `AGY_FAST` |
| **Phase 2: Spec & Tickets** | [`to-spec`](.agents/skills/to-spec/SKILL.md), [`to-tickets`](.agents/skills/to-tickets/SKILL.md), [`plan-epic`](.agents/skills/plan-epic/SKILL.md) | `antigravity::gemini-3.8-flash-high` | `AGY_FAST` |
| **Phase 3a: Build (UI / CRUD / Standard)** | [`poteto-mode`](.agents/skills/poteto-mode/SKILL.md) ([`autopilot-full`](.agents/skills/poteto-mode/playbooks/autopilot-full.md)) + [`tdd`](.agents/skills/tdd/SKILL.md) | `antigravity::gemini-3.8-flash-medium` | `AGY_FAST` |
| **Phase 3b: Build (Backend / Complex)** | [`poteto-mode`](.agents/skills/poteto-mode/SKILL.md) ([`autopilot-full`](.agents/skills/poteto-mode/playbooks/autopilot-full.md)) + [`tdd`](.agents/skills/tdd/SKILL.md) | `grok::grok-4.7-build-fast` (`reasoningEffort: medium`) | `GROK_WORK` |
| **Phase 4a: Runtime Verification** | [`verify-app`](.agents/skills/verify-app/SKILL.md) (`verify-<app>`) | `antigravity::gemini-3.8-flash-medium` | `AGY_FAST` |
| **Phase 4b: Independent Audit** | Adversarial diff & spec interrogation ([`interrogator-grok`](.cursor/agents/interrogator-grok.md)) | `grok::grok-4.7` (`reasoningEffort: high`) | `GROK_AUDIT` |
| **Phase 4c: Security Audit** | [`audit-security`](.agents/skills/audit-security/SKILL.md) ([`security-auditor`](.cursor/agents/security-auditor.md)) | `grok::grok-4.7` (`reasoningEffort: high`) | `GROK_AUDIT` |
| **Rework Escalation (max 2)** | Scoped repair from 4a/4b/4c findings | `antigravity::gemini-3.8-flash-high` (`maxRetries: 2`) | `AGY_FAST` |

### Strict Invariants
- **Zero Paid API Keys**: Never require or read `GEMINI_API_KEY`, `XAI_API_KEY`, `CURSOR_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`. All models run through authenticated sessions.
- **100% Claude & GPT Free**: Never route tasks to Claude or GPT models (`disallowClaude: true`).
- **Zero Argon Usage**: Argon models are completely retired across all orchestration.
- **Model Separation on Audit & Rework**: Rework escalates to `antigravity::gemini-3.8-flash-high` (up to 2 attempts) so the rework builder is always a different model family from the `grok::grok-4.7` auditor.
- **Task-Based Effort Scaling**:
  - `low` (`gemini-3.8-flash-low`) for scout & simple tasks.
  - `medium` (`gemini-3.8-flash-medium`) for normal work (UI/CRUD build, runtime verification).
  - `high` (`gemini-3.8-flash-high`) for plan / spec / hard problems / rework.

---

## 3. Communication Rules (Zero Issue/PR Comments)

- **NEVER comment on issues or PRs**.
- When a bug cannot be reproduced, or when grilling/clarification is needed for César:
  1. **Self-Deduction First**: Explore the repository, types, tests, ADRs, and existing docs to answer every question that can be deduced from code.
  2. **Thread Final Message**: If genuine ambiguities or reproduction blockers remain:
     - Formulate a numbered block of questions or reproduction findings.
     - Write them directly in the **thread final message**.
     - Stop execution immediately.
     - The external dispatcher (**Grok Bot**) relays the questions to César. Do NOT post comments on GitHub or Linear.

---

## 4. Build, Verification & Merge (`poteto-mode` · `Autopilot-full`)

Execution follows the official pstack [`poteto-mode`](.agents/skills/poteto-mode/SKILL.md) skill, [`tdd`](.agents/skills/tdd/SKILL.md) seam discipline, and the [`Autopilot-full`](.agents/skills/poteto-mode/playbooks/autopilot-full.md) playbook:

1. **Parallel Worktrees (Max Concurrency = 3)**:
   - Run at most **3 concurrent ticket owners** in isolated Git worktrees branched directly off `main` (never stacked).
2. **Independent Verification Before Merge**:
   - Green CI (`ci`) alone **never** authorizes a merge.
   - Before merging, every PR must pass:
     - **Green CI check (`ci`)** on the current head rebased onto `main`.
     - **Phase 4a Runtime Verification** (`antigravity::gemini-3.8-flash-medium`) running `.agents/skills/verify-app` (or `verify-<app>`) with `exitCode === 0`.
     - **Phase 4b Independent Interrogation** (`grok::grok-4.7`, `reasoningEffort: high`, [`.cursor/agents/interrogator-grok.md`](.cursor/agents/interrogator-grok.md)) auditing the diff, spec, and verification evidence (`verdict: PASS`).
     - **Phase 4c Security Audit** (`grok::grok-4.7`, `reasoningEffort: high`, [`.cursor/agents/security-auditor.md`](.cursor/agents/security-auditor.md)) auditing AST patterns, OWASP Top 10, secrets, and supply-chain integrity (`verdict: PASS`).
3. **Rework Escalation (Up to 2 Attempts)**:
   - If Phase 4a, Phase 4b, or Phase 4c fails, increment `retryCount` and escalate the rework pass to **`antigravity::gemini-3.8-flash-high`** (`maxRetries: 2`).
   - If the ticket still fails after 2 rework attempts, set `status: "blocked"`, `waitingOn: "blocked"`, and stop for human intervention.
4. **Squash Merge & Branch Preservation**:
   - Every PR body MUST use `Closes #N` (never `Refs #N`). For epics, the final deploy sub-issue PR also includes `Closes #EPIC`.
   - Once `ci` is green and both Phase 4a and Phase 4b pass on the `main`-rebased head, merge via **squash merge**:
     ```bash
     gh pr merge <PR_NUMBER> --squash
     ```
   - **Strict Rule**: NEVER pass `--delete-branch`. Never delete branches.
