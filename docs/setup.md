# Setup & GitHub/Linear Configuration Guide

This guide covers initial setup, GitHub merge policies, branch protection, secrets, labels, and template sync for working repositories created from `cesarchavezcal/grok-bot-agent-factory`.

> **Reminder (GitHub Free):** Working repositories created from this template **must be PUBLIC** (`--public`) so that GitHub Free allows required status checks (`ci`) and `allow_auto_merge`.

---

## 1. Labels (`agent`, `epic`, `deploy`, `bug`)

The factory relies on GitHub and Linear labels to route incoming tickets to the appropriate orchestrator skill.

### GitHub
Run the idempotent label script (also executed automatically by `./scripts/init.sh`):

```bash
./scripts/setup-labels.sh
```

This creates/updates:
- `agent` (`#0E8A16`) — Trigger: issue is picked up by the autonomous agent factory (Grok Bot).
- `epic` (`#B60205`) — Planning only: split into agent sub-issues.
- `deploy` (`#006B75`) — Deploy trigger: applied to the final sub-issue of an epic at creation; triggers deploy after green merge.
- `waiting-for-human` (`#FBCA04`) — Blocked on questions awaiting human response via Grok Bot.
- `in-progress` (`#1D76DB`), `rework` (`#D93F0B`), `ready-to-merge` (`#5319E7`), `feature` (`#A2EEEF`), `bug` (`#D73A4A`).

### Skill Routing Matrix & Priority
- **`epic` + `agent`** -> **`plan-epic`**: Planning-only thread that decomposes an epic into vertical sub-issues (`Part of #N`). Every created sub-issue MUST get the `agent` label; exactly one final sub-issue receives the `deploy` label. Label existence is verified before completion. Epics stay planning-only (no build).
  - *Precedence*: `epic` takes priority over all other labels. If an issue has `epic` + `bug` + `agent`, it routes to `plan-epic`.
- **`bug` + `agent`** -> **`fix-bug`**: Reproduction-first defect workflow. Starts with a short plan in the thread. Reproduces first (if unable to reproduce or open questions exist, stops and asks in thread final message; if no questions, writes `"No questions, starting build"` and builds immediately in the same run) -> writes failing test -> fixes root cause (`ce-debug`, `tdd`, `principle-fix-root-causes`) -> verifies all tests + runs app once -> Grok audit -> PR `Closes #N` -> merge on green CI.
- **`agent` alone (or with `feature`)** -> **`implement-ticket`**: Full lifecycle: starts with a short plan in the thread. If open questions exist, stops and asks in thread final message; if no questions, writes `"No questions, starting build"` and continues directly to build in the same run without waiting for a separate build message (`wayfinder` + `grill-with-docs` -> `poteto-mode` -> Grok audit -> rework rule -> PR `Closes #N` -> merge on green CI).
- **Manual Epic Runner: `$run-epic <#N | plain text request>`** -> **`run-epic`**: Manual orchestrator command to run an entire epic loop from a single command in T3 Code without requiring Grok Bot. Accepts an explicit issue number (`#N`, `issue N`) or a free text request (e.g. `$run-epic add a dark mode toggle`).
  - **Find-or-Create Resolution**: When given free text, runs `find_or_create_issue.py` to search open issues via hidden marker, exact title, or keyword overlap. Reuses a clear match, creates a new issue with a complete task card (`Goal`, `Done when`, `Don't touch`) and hidden idempotency marker if no match exists, or halts for César in the thread final message if ambiguous or unclear.
  - **Decomposition or Reuse**: Automatically checks if `Part of #N` sub-issues exist; if none exist, calls `plan-epic #N` to decompose into vertical tracer-bullet sub-issues with `agent` labels and a single `deploy` label on the final sub-issue (or executes the issue directly if a single slice).
  - **Anti-Clash & Concurrency Guard**: Inspects `in-progress` label, open PRs, and active branch state to prevent colliding with Grok Bot or concurrent agents.
  - **Sequential Execution**: Runs `implement-ticket` (or `fix-bug` for `bug` sub-issues) on each sub-issue one by one in dependency order.
  - **Model Resolution**: Resolves models from `models.yml` (`epic_planner`, `planner`, `builder`, `auditor`). Halts immediately with no fallback or retries if any model is unavailable. Zero Claude, GPT, or Argon.
  - **GitHub Account Invariant**: Automatically switches active `gh` auth to `cesarchavezcal` for git/gh operations and restores the prior active account upon completion or pause.
  - **Idempotency & Resumability**: Re-running `$run-epic` with an issue number or identical free text request reattaches to existing issues/PRs without creating duplicates.
  - **Merge & Deploy Rules**: PRs merge via squash merge on green `ci` + audit pass. Deploys only on the final sub-issue with the `deploy` label, closing both the sub-issue and parent epic (`Closes #SUB_ISSUE` and `Closes #EPIC`).
  - **Human Gates**: Stops and reports questions, unclear requests, multiple matches, or pauses in the thread final message (zero issue/PR comments).
  - **Backward Compatibility**: `plan-epic` and `implement-ticket` remain independently functional with identical behavior.
- **Plan-Then-Build Rule**:
  - Every issue thread starts with a short plan in the thread (files, tests, verification).
  - If there is ANY open question, ask it in the thread and stop without editing files. Wait for the human answer, then build.
  - If there are NO questions, write `"No questions, starting build"` and continue to the build in the same run (no waiting for a separate build message).
  - Epics (`epic` label) stay planning-only: create the `agent` sub-issues, no build.
  - Keep all existing gates: PR with `Closes #N`, Grok audit, squash-merge only when `ci` is green AND the audit passes, deploy only for the `deploy` sub-issue.
- **GitHub Account Rule (`cesarchavezcal`)**:
  - Every commit, push, and PR must use the `cesarchavezcal` account.
  - Check `gh auth status` first before any push or `gh` command; if the active account is not `cesarchavezcal`, remember the active account, switch using `gh auth switch --user cesarchavezcal`, and switch back when done.
  - Keep git email `cesarchavezcal@gmail.com` via `includeIf`, never changing the global git email.
- **Manual Labeling Order (`epic` before `agent`)**: When manually labeling an existing issue in GitHub or Linear, **always add `epic` before `agent`** so `epic` is already present on the issue payload when `agent` triggers `notify-grok.yml`.
- **Deploy Rule**: Intermediate sub-issues never deploy. Deploy occurs only on the final sub-issue of an epic (carrying the `deploy` label), after its green merge.
- **Issue Closing Rule**: Every PR body uses `Closes #N` (never `Refs #N`). For epics, the final deploy sub-issue PR also includes `Closes #EPIC`. Agents never close issues by hand.
- **Communication Rule**: Never comment on issues or PRs. When questions or reproduction blockers arise, stop and write them in the thread final message for dispatcher relay.
- **Conventional Branch & Git Conventions ([`conventionalbranch.org`](https://conventionalbranch.org/))**:
  - **Branch Naming**: All branches follow `<type>/<issue>-<description>` with permitted types (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`, `hotfix/`, `release/`). Lowercase alphanumerics and single hyphens only.
  - **Commit Messages**: All commits follow Conventional Commits: `<type>(<scope>): <summary> (#<issue>)`.
  - **Pull Requests**: PR titles match Conventional Commits; PR bodies follow the mandatory 4-section format (`Why`, `What changed`, `How it was tested`, `Closes #N`).
  - **Automated Validation**: Verified via `python3 scripts/validate_conventions.py`.

### Linear
In Linear (**Workspace Settings → Labels**), create a label named **`agent`** (exact lowercase). Only Linear issues tagged with `agent` are dispatched.

---

## 2. Model Setup & Configuration (`./scripts/setup-models.sh` & `models.yml`)

The template allows users to pick their models at setup instead of hard-coding them.

### Setup Script
Run the interactive model setup script (also executed during `./scripts/init.sh`):

```bash
./scripts/setup-models.sh
# or using the symlink:
./scripts/setup-models
```

- **Interactive Prompts**: Prompts for the **builder** and **auditor** models from [`models.allowed.yml`](../models.allowed.yml).
- **Defaults**: The **planner**, **epic planner**, and **sub-agents** automatically default to the builder model unless custom options are provided.
- **Auditor Invariant**: The auditor model **MUST differ from the builder model**. If the same model is selected, the script refuses it, and CI fails.
- **Re-running**: To change models at any time, simply **re-run `./scripts/setup-models.sh`**.
- **CLI Flags**: For automation or scripts, flags are supported:
  ```bash
  ./scripts/setup-models.sh --builder gemini-3.8-flash-high --auditor grok-4.7
  ./scripts/setup-models.sh --defaults
  ```

### Roles in `models.yml`
The answers are written to [`models.yml`](../models.yml) at the repository root:
- `builder`: Standard code generation, implementation, and bug fixing.
- `auditor`: Adversarial code review and interrogation. Must differ from builder.
- `planner`: Planning, spec generation, and grilling.
- `epic_planner`: Initiative epic breakdown.
- `subagents`: Auxiliary background agents.

### Allowed Models List (`models.allowed.yml`)
The setup script and CI checks only permit models declared in [`models.allowed.yml`](../models.allowed.yml):
- `gemini-3.8-flash-low`
- `gemini-3.8-flash-medium`
- `gemini-3.8-flash-high`
- `grok-4.7`

*(Argon, Claude, and GPT models are strictly forbidden.)*

### Model Unavailability Rule
If a configured model is unavailable in the environment, the factory **stops immediately and tells the user**. There is no fallback model and no retries.

---

## 3. Grok Bot Webhook Secrets (`GROK_WEBHOOK_URL` & `GROK_WEBHOOK_AUTH`)

`.github/workflows/notify-grok.yml` triggers on `issues` (`types: [labeled]`) and runs only when `github.event.label.name == 'agent'`:
- When an issue is **created with labels** (e.g., via the `.github/ISSUE_TEMPLATE/bug.yml` issue form), GitHub emits a `labeled` event for each initial label, so exactly one run dispatches when `agent` is processed.
- When `agent` is **added later to an existing issue**, GitHub emits a `labeled` event for `agent`.
- The webhook payload includes the full event enriched with an explicit top-level `labels` array, a stable `idempotency_key` (`<repo>#<issue>`), `delivery_id`, and the validated `models` object from `models.yml`.
- Concurrency per issue (`cancel-in-progress: false`) ensures events are processed reliably in order.

### Required Repository Secrets
- `GROK_WEBHOOK_URL` — Full HTTPS webhook endpoint URL for Grok Bot.
- `GROK_WEBHOOK_AUTH` — Value sent in the `Authorization` HTTP header (for example, `Bearer <token>`).

During `./scripts/init.sh`, the script checks `gh secret list` for both secrets:
- Any secret already present is skipped (idempotent).
- Any missing secret prompts interactively with hidden input via `gh secret set <NAME>` when a TTY is attached (never echoing or logging secret values).
- If run non-interactively (no TTY) or if you skip the prompt, `./scripts/init.sh` finishes cleanly and prints a reminder with the manual commands:

```bash
gh secret set GROK_WEBHOOK_URL
gh secret set GROK_WEBHOOK_AUTH
```

If either `GROK_WEBHOOK_URL` or `GROK_WEBHOOK_AUTH` is not configured when an issue is labeled with `agent`, `.github/workflows/notify-grok.yml` logs a `::notice::` annotation and exits `0` without failing workflow runs.

### Test the Grok webhook
1. Make sure the repo secrets `GROK_WEBHOOK_URL` and `GROK_WEBHOOK_AUTH` are set.
2. Create a test issue with the `agent` label plus one more label (for example `documentation`).
3. In the Actions tab, check that `notify-grok` ran exactly once for that issue (one run, triggered by the `agent` label).
4. Check that Grok Bot received one webhook whose payload has `idempotency_key` equal to `<owner>/<repo>#<issue number>` and includes the `.models` object.
5. If you see two runs or two webhooks for the same issue, the duplicate-webhook fix is missing: compare `notify-grok.yml` with the template.

---

## 4. Allow Auto-Merge, Squash Merge & Preserve Branches

The `Autopilot-full` playbook merges PRs via **squash merge** once both the **`ci`** status check and independent verification (`verify-app` + independent adversarial audit from `models.yml`) pass. Branches are preserved (`delete_branch_on_merge=false`). Every PR body uses `Closes #N` (never `Refs #N`) so the issue closes when the PR merges, and for epics the last (deploy) sub-issue PR also includes `Closes #EPIC`.

### CLI (`gh api PATCH`)
```bash
REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
gh api --method PATCH "repos/$REPO" \
  -F allow_auto_merge=true \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F delete_branch_on_merge=false
```

---

## 5. Branch Protection & Ruleset on `main` (Required Check: `ci` Only, Strict Linear History)

The factory enforces quality gates on `main` via branch rulesets and protection:
- **Required Reviews**: `0` required approving reviews (`required_pull_request_reviews: null`). Reviewer agent approval is recorded directly in the PR body and run log, enabling single-account operation under `cesarchavezcal`.
- **Status Check**: Strict check **`ci`** from `.github/workflows/ci.yml`.

### CLI (`gh api PUT`)
```bash
REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
gh api --method PUT "repos/$REPO/branches/main/protection" --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
```

### GitHub Web UI (Rulesets)
Navigate to **Settings → Rules → Rulesets → New branch ruleset**:
1. **Ruleset Name**: `main-protection`
2. **Enforcement status**: `Active`
3. **Target branches**: Include default branch (`main`)
4. **Rules**:
   - [x] **Restrict deletions**
   - [x] **Block force pushes**
   - [x] **Require linear history**
   - [ ] **Require a pull request before merging** (leave required approvals at 0 or null; gate is `ci` + agent approval)
   - [x] **Require status checks to pass**:
     - Require branches to be up to date before merging
     - Status checks: **`ci`**

### If the Repo Was Created Private on GitHub Free
If the API returns HTTP `403` (`Upgrade to GitHub Pro or make this repository public to enable this feature`), make the working repository public and re-run `./scripts/init.sh`:

```bash
gh repo edit "$REPO" --visibility public --accept-visibility-change-consequences
./scripts/init.sh
```

---

## 6. Reviewer Agent Inspection & Merge Gate

The autonomous reviewer agent ([`review-pr`](../.agents/skills/review-pr/SKILL.md) / [`scripts/review_pr.py`](../scripts/review_pr.py)) inspects PR diffs, task cards, and test evidence under the `auditor` model from `models.yml`.

- **Verdict Recording**: Rather than requiring a secondary bot account or GitHub App, the reviewer verdict (`APPROVE` or `REQUEST_CHANGES`), findings, and review round number are recorded directly in the PR body under `## Reviewer Agent` and in the run log (`.factory/runs/runs.jsonl`).
- **Merge Gate**: The auto-merge gate is strictly green `ci` + Reviewer Agent Approve.
- **Single Account**: All PR creation, body edits, and merges are performed under `cesarchavezcal`.


---

## 7. App Verification Skill (`.agents/skills/verify-app`)

Before running autonomous merges on a new application:
1. Customize `.agents/skills/verify-app/SKILL.md` (or copy it to `.agents/skills/verify-<app>/SKILL.md` and update `"verifySkill"` in `.factory/config.json`).
2. Document your user-facing feature verification recipes in `.agents/skills/verify-app/features/`.

---

## 8. Syncing Upstream Template Updates (`./scripts/sync-template.sh`)

Derived working repositories can pull factory infrastructure updates from the private template (`cesarchavezcal/grok-bot-agent-factory`) at any time without touching application code:

```bash
# Sync from `main` (default) inside a derived working repo and open a PR if managed files changed
./scripts/sync-template.sh

# Sync from a specific branch, tag, or commit SHA
./scripts/sync-template.sh --ref <branch-or-sha>

# Run from a template checkout against another target repository (including first-time sync)
./scripts/sync-template.sh --target /path/to/working-repo

# Preview the diff summary without creating a branch or PR
./scripts/sync-template.sh --dry-run
```

### How It Works
1. **Authenticated Private Fetch**: Uses `gh repo clone` (`gh` CLI authentication) to fetch `cesarchavezcal/grok-bot-agent-factory` into a temporary directory.
2. **First-Time Bootstrap & `--target <path>`**:
   - If the target repository does not yet have `.factory/template-sync.json` (for example, an older derived repo or an existing project adopting the factory), `sync-template.sh` fetches `.factory/template-sync.json` from the template ref via `gh` auth, uses it to drive the sync, and includes `.factory/template-sync.json` in the synced files.
   - Pass `--target <path>` to run `scripts/sync-template.sh` directly from a template checkout against any target repository; both the clean working-tree guard and the template self-guard evaluate the **target** repository rather than the script's location.
3. **Explicit Manifest (`.factory/template-sync.json`)**: Copies only the managed paths declared in `.factory/template-sync.json`:
   - `.factory/template-sync.json`
   - `.github/workflows/*`
   - `.github/ISSUE_TEMPLATE/*`
   - `scripts/*` (including `scripts/sync-template.sh`, `scripts/init.sh`, `scripts/setup-labels.sh`, `scripts/setup-models.sh`)
   - `.agents/skills/*`
   - `.cursor/rules`
   - `.cursor/agents`
   - `AGENTS.md`
   - `skills-lock.json`
   - `models.allowed.yml`
   - `.factory/work-item.schema.json`
   - `.factory/WORK-ITEM.example.json`
4. **Never Touches App Code or Custom Models**: Application source files, `models.yml`, `.factory/config.json` (which stores the working repo's `app` slug and `verifySkill`), `.factory/work-items`, and `.agents/skills/verify-app/features` are preserved.
5. **Idempotent**: If no managed files changed, it prints an up-to-date message and exits `0` without creating a branch or opening a PR.
6. **Version Tracking (`.factory/template-version`)**: When managed files change, it records the synced 40-character template commit SHA in `.factory/template-version`, prints a diff summary, pushes `chore/template-sync-<short-sha>`, and opens (or updates) a Pull Request against `main`.

---

## 9. Troubleshooting

Common issues and their resolutions:

1. **The webhook doesn't fire**: Check that the issue has the `agent` label and that the `GROK_WEBHOOK_URL` and auth secrets are set in the repo settings (`GROK_WEBHOOK_URL` and `GROK_WEBHOOK_AUTH` under **Settings → Secrets and variables → Actions**).
2. **The webhook fires twice**: Check that `.github/workflows/notify-grok.yml` only triggers on `labeled` with `github.event.label.name == 'agent'`.
3. **Commits use the wrong GitHub account**: Run `gh auth status` and switch with `gh auth switch --user <account>`. Ensure the git author email matches `cesarchavezcal@gmail.com`.

