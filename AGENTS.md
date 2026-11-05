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

## 1. Intake & Routing Matrix (`agent`, `bug`, `epic` Labels)

- **Entry Condition**: Only issues from **GitHub Issues** or **Linear** carrying the **`agent`** label are eligible for execution.
- **Ignore Rule**: Any issue without the `agent` label MUST be ignored completely.
- **Routing Matrix & Precedence**:
  - **`epic` + `agent`** -> **[`plan-epic`](.agents/skills/plan-epic/SKILL.md)**: Planning-only thread that splits an epic into vertical sub-issues (`Part of #N`). Every created sub-issue MUST receive the `agent` label; exactly one final sub-issue receives the `deploy` label. Verify all sub-issues have `agent` before completing.
    - *Precedence*: `epic` takes priority over all other labels. If an issue carries `epic` + `bug` + `agent`, it routes to `plan-epic`.
  - **`bug` + `agent`** -> **[`fix-bug`](.agents/skills/fix-bug/SKILL.md)**: Starts with short plan in thread -> reproduces first (if cannot reproduce or open questions, stops and asks in thread final message; if no questions, writes `"No questions, starting build"` and builds immediately in same run) -> writes failing test -> fixes root cause (`ce-debug`, `tdd`, `principle-fix-root-causes`) -> verifies all tests + runs the app once -> Grok audit -> PR `Closes #N` -> squash merge on green CI.
  - **`agent` alone (or with `feature`)** -> **[`implement-ticket`](.agents/skills/implement-ticket/SKILL.md)**: Full lifecycle feature delivery: starts with short plan in thread -> if open questions exist, stops and asks in thread final message; if no questions, writes `"No questions, starting build"` and continues directly to build in same run without waiting for a separate build message (`wayfinder` + `grill-with-docs` -> `poteto-mode` reproduce, test, fix, verify -> Grok audit -> rework rule -> PR `Closes #N` -> squash merge on green CI).
  - **Manual Command: `$run-epic #N`** -> **[`run-epic`](.agents/skills/run-epic/SKILL.md)**: Full autonomous epic runner for manual execution in T3 Code without Grok Bot. Orchestrates the entire epic initiative end-to-end: executes `plan-epic #N` (or reuses existing `Part of #N` sub-issues if already planned), iterates through sub-issues sequentially in dependency order running `implement-ticket` (or `fix-bug` for `bug` sub-issues), enforces independent verification and Grok audit gates, merges PRs via squash merge on green CI, and deploys only on the final `deploy` sub-issue, closing the epic when the final PR merges.
    - *Standalone Invariant*: `plan-epic` and `implement-ticket` remain fully functional when run independently with unchanged behavior.
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

## 2. Workflow & Agent-Run Rules (Plan-Then-Build & GitHub Account)

- **Plan-Then-Build Rule**:
  - **Task Card Verification**: The agent checks the issue task card first. If **Goal**, **Done when**, or **Don't touch** is missing, ambiguous, or incomplete, ask in the thread final message and stop immediately without editing files.
  - Every issue thread starts with a short plan in the thread (files, tests, verification).
  - If there is **ANY open question**, ask it in the thread and stop without editing files. Wait for the human answer, then build.
  - If there are **NO questions**, write `"No questions, starting build"` and continue to the build in the same run (no waiting for a separate build message).
  - Epics (`epic` label) stay planning-only: create the `agent` sub-issues, no build.
  - Keep all existing gates: PR with `Closes #N`, Grok audit, squash-merge only when `ci` is green AND the audit passes, deploy only for the `deploy` sub-issue.
- **GitHub Account Rule (`cesarchavezcal`)**:
  - Every commit, push, and PR must use the GitHub account `cesarchavezcal`.
  - Check `gh auth status` first before any git push or `gh` command; if the active account is not `cesarchavezcal`, remember the previous active account, switch with `gh auth switch --user cesarchavezcal`, and switch back to the earlier account when done.
  - Maintain the git email `cesarchavezcal@gmail.com` via `includeIf`, and never change the global git email.
- **Run Log File Rule (`.factory/runs/runs.jsonl`)**:
  - Each agent run appends exactly one line to `.factory/runs/runs.jsonl` upon conclusion (end of run, after merge, block, or failure).
  - Format conforms strictly to [`.factory/schemas/run.schema.json`](.factory/schemas/run.schema.json) with fields: `issue`, `pr`, `kickoff_at`, `pr_opened_at`, `first_review_at`, `merged_at`, `human_intervened` (bool + count), `result` (`merged` | `blocked` | `failed`), `builder`, `auditor`, `pr_score`, `review_result`, `review_rounds`, `reviewer_model`.
  - Appends are thread- and process-safe via `scripts/run_log.py` using advisory `fcntl.flock` on `.runs.lock` and `.gitattributes` `merge=union`.
  - Zero Secret Leakage: No tokens, credentials, or secrets may ever appear in the run log (`additionalProperties: false`).
- **PR Score by T3 Rule (`scripts/score_pr.py`)**:
  - During each run, T3 evaluates each opened PR using the configured `scorer` model through a signed-in model session (zero paid API keys).
  - The score (1–10 + concise rationale) is placed in the PR body under `## How it was tested` (`- **PR Score**: <score>/10 — <short reason> (scorer: <model>)`) and written to `.factory/runs/runs.jsonl` under `pr_score`.
  - If the scorer model is unavailable, T3 stops and reports immediately in the thread final message. Zero fallback models, zero retries.
  - GitHub Actions on each PR run unit tests and validate the run log against its schema; workflows make zero model calls and use zero secrets.

---

## 3. Model Configuration (`models.yml`) & Pipeline Roles

Models are not hard-coded in the factory. They are configured at the repository root in [`models.yml`](models.yml) and configured via [`./scripts/setup-models.sh`](scripts/setup-models.sh) (or `./scripts/setup-models`).

### Roles in `models.yml`
- **`builder`**: Drives code construction, implementation, and bug fixing (`poteto-mode` + `tdd`).
- **`auditor`**: Performs independent adversarial interrogation and code review. **Must differ from the builder model**.
- **`planner`**: Handles architecture discovery, spec creation, and ticket planning (`wayfinder`, `to-spec`, `grill-with-docs`). Defaults to `builder`.
- **`epic_planner`**: Decomposes initiative-level epics into vertical sub-issues (`plan-epic`). Defaults to `builder`.
- **`subagents`**: Powers background task subagents and auxiliary workers. Defaults to `builder`.
- **`scorer`**: Cheap model role (default: `gemini-3.8-flash-low`) used by T3 during runs to score PR diffs (1–10 scale) without paid API keys.

### Allowed Models (`models.allowed.yml`)
The factory enforces a curated allowed list in [`models.allowed.yml`](models.allowed.yml):
- `gemini-3.8-flash-low`
- `gemini-3.8-flash-medium`
- `gemini-3.8-flash-high`
- `grok-4.7`

Default committed configuration: `builder: gemini-3.8-flash-high`, `auditor: grok-4.7`, `scorer: gemini-3.8-flash-low`, with `planner`, `epic_planner`, and `subagents` defaulting to `gemini-3.8-flash-high`.

### Strict Invariants & Rules
- **Auditor Must Differ from Builder**: The setup script refuses any configuration where `auditor == builder`, and CI fails on it.
- **Model Not Available Rule**: If a configured model is unavailable, **stop and tell the user immediately**. No fallback model, no retries.
- **Zero Paid API Keys**: Never require or read `GEMINI_API_KEY`, `XAI_API_KEY`, `CURSOR_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`. All models run through authenticated sessions.
- **100% Claude & GPT Free**: Never route tasks to Claude or GPT models (`disallowClaude: true`).
- **Zero Argon Usage**: Argon models are completely retired across all orchestration.

---

## 4. Communication Rules (Zero Issue/PR Comments)

- **NEVER comment on issues or PRs**.
- When a bug cannot be reproduced, or when grilling/clarification is needed for César:
  1. **Self-Deduction First**: Explore the repository, types, tests, ADRs, and existing docs to answer every question that can be deduced from code.
  2. **Thread Final Message**: If genuine ambiguities or reproduction blockers remain:
     - Formulate a numbered block of questions or reproduction findings.
     - Write them directly in the **thread final message**.
     - Stop execution immediately.
     - The external dispatcher (**Grok Bot**) relays the questions to César. Do NOT post comments on GitHub or Linear.

---

## 5. Build, Verification & Merge (`poteto-mode` · `Autopilot-full`)

Execution follows the official pstack [`poteto-mode`](.agents/skills/poteto-mode/SKILL.md) skill, [`tdd`](.agents/skills/tdd/SKILL.md) seam discipline, and the [`Autopilot-full`](.agents/skills/poteto-mode/playbooks/autopilot-full.md) playbook:

1. **Parallel Worktrees (Max Concurrency = 3)**:
   - Run at most **3 concurrent ticket owners** in isolated Git worktrees branched directly off `main` (never stacked).
2. **Independent Verification Before Merge**:
   - Green CI (`ci`) alone **never** authorizes a merge.
   - Before merging, every PR must pass:
     - **Green CI check (`ci`)** on the current head rebased onto `main`.
     - **Phase 4a Runtime Verification** running `.agents/skills/verify-app` (or `verify-<app>`) with `exitCode === 0` using the configured `builder` model.
     - **Phase 4b Independent Interrogation** using the configured `auditor` model from `models.yml` (e.g., `grok-4.7`, `reasoningEffort: high`, [`.cursor/agents/interrogator-grok.md`](.cursor/agents/interrogator-grok.md)) auditing the diff, spec, and verification evidence (`verdict: PASS`).
3. **Rework Escalation (Up to 2 Attempts)**:
   - If Phase 4a or Phase 4b fails, increment `retryCount` and escalate the rework pass using the configured `planner` or `builder` model (ensuring it differs from the `auditor`, `maxRetries: 2`).
   - If the ticket still fails after 2 rework attempts, set `status: "blocked"`, `waitingOn: "blocked"`, and stop for human intervention.
4. **Mandatory Short 4-Section PR Template (`.github/PULL_REQUEST_TEMPLATE.md`)**:
   - Every opened PR MUST strictly adhere to the concise 4-section pull request template:
     - `## Why`: Brief explanation of the problem, motivation, and approach (1–3 sentences).
     - `## What changed`: Concise summary or diff-sketch of the modifications.
     - `## How it was tested`: Combined runtime verification proof (e.g. `verify-app` or test suite command with `exitCode: 0`) and independent Grok audit verdict (`verdict: PASS`), alongside PR score evaluated by T3 (`- **PR Score**: <score>/10 — <short reason>`) and models used (`builder: <model>`, `auditor: <model>`, `scorer: <model>`) dynamically read from `models.yml` (never an obsolete static table).
     - `Closes #N`: Mandatory issue closing directive (never `Refs #N`). For the designated final deploy sub-issue of an epic, also include `Closes #<EPIC_NUMBER>`.
5. **Merge Policy & Risk Classification Gate (`docs/merge-policy.md`)**:
   - **Three-Tier Governance (`scripts/classify_pr_risk.py`)**:
     - **`low-risk`**: Docs only, tests only, or a small fix under 50 changed lines touching zero high-risk paths. Auto-merges upon green `ci` and passing audit/review.
     - **`normal`**: Standard code changes ($\ge 50$ lines) touching zero high-risk paths. Routes to the autonomous reviewer agent (`review-pr`); auto-merges upon green `ci` and reviewer agent approval recorded in the PR body.
     - **`high-risk`**: Touches auth/secrets (`.env*`, `auth/*`, `secrets/*`), workflows (`.github/workflows/*`), branch rules/rulesets (`.github/rulesets/*`), dependencies, models (`models*.yml`), migrations/deletions (`migrations/*`, `*.sql`), deploy (`deploy/*`, `Dockerfile*`), factory config (`.factory/*`), or control plane files (`.agents/skills/*`, `AGENTS.md` per ADR 0001).
   - **No Auto-Merge for `high-risk`**: If a PR is classified as `high-risk` (or labeled `needs-approval`), the agent runner **MUST NOT auto-merge** it; it halts and reports `"waiting for César"` in the thread final message.
6. **Squash Merge & Branch Preservation**:
   - Every PR body MUST use `Closes #N` (never `Refs #N`). For epics, the final deploy sub-issue PR also includes `Closes #EPIC`.
   - Once `ci` is green, both Phase 4a and Phase 4b pass on the `main`-rebased head, and the PR satisfies the `low-risk` rule (or human approval is granted), merge via **squash merge**:
     ```bash
     gh pr merge <PR_NUMBER> --squash
     ```
   - **Strict Rule**: NEVER pass `--delete-branch`. Never delete branches.

---

## 6. Self-Improvement Outer Loop (Memory Store, Evaluator & Routine Maker)

Beyond the inner task execution loop, the factory runs an asynchronous evaluative outer loop that extracts lessons from completed runs and iteratively improves `.agents/skills/`:

1. **Post-Merge Evaluation (`.github/workflows/evaluate-run.yml`)**:
   - Triggers automatically upon merge of any `agent`-labeled PR to `main`.
   - Runs `scripts/evaluate_run.py` to inspect diff economy, rework retry counts, verification outcomes, and audit logs.
   - Extracts structured lessons matching [`.factory/schemas/lesson.schema.json`](.factory/schemas/lesson.schema.json).
2. **Process-Safe Memory Store (`.factory/memory/`)**:
   - Atomically appends lessons to `.factory/memory/lessons.jsonl` and updates the aggregated pattern index in `.factory/memory/patterns.json`.
   - Uses POSIX `fcntl.flock(LOCK_EX)` on `.factory/memory/.memory.lock` across concurrent worktrees (`git rev-parse --git-common-dir`).
   - `.gitattributes` enforces `merge=union` on `lessons.jsonl` to ensure parallel branch merges preserve all lesson records without merge conflicts.
3. **Threshold-Triggered Routine Maker (`gemini-3.8-flash-high`)**:
   - When a failure pattern accumulates $\ge 3$ occurrences, `patterns.json` flags `readyForRoutineMaker: true`.
   - The Routine Maker ([`.cursor/agents/routine-maker.md`](.cursor/agents/routine-maker.md)) authors a minimal diff modifying the target skill or rule.
4. **HITL Delivery Gate (ADR 0001)**:
   - Self-evolution PRs strictly require human approval (`cesarchavezcal`) and MUST NOT auto-merge.
   - Every self-evolution PR must include a structured **Receipt of Causality** citing the contributing lesson IDs, repetition counts, and expected behavioral changes.

---

## 7. Frontend, Design, Motion & Verification Skills Lifecycle

The factory integrates specialized design, layout, motion, and animation skills across the standard 5-phase software delivery lifecycle:

```
[Phase 1: Planning / Spec] ──► [Phase 3: Build / TDD] ──► [Phase 4a: Verification] ──► [Phase 4b: Audit] ──► [Phase 5: Ship]
   gather, sketchbook             emil-design-eng                 break-ui, match               restraint              ship
   prototype, pick-ui-library     layout & motion skills          animation-performance         review-animations
   apple-design, scope, defaults  mobile-native, ask-sonner       deconstruct, lab              remove-animations, rule
```

### Phase 1: Discovery, Ideation & Design Foundations (Planning / Spec)
Used during `to-spec`, `grill-with-docs`, and architectural discovery before code construction:
- **`gather`**: Collect reference UI patterns, design inspiration, and real-world implementation candidates.
- **`sketchbook`**: Rapid layout exploration and concept drafting in project stack.
- **`prototype`**: Disposable interaction prototypes to validate ergonomics before committing to architecture.
- **`pick-ui-library`**: Choose optimal component primitives (Base UI, Radix, Tailwind, etc.) without analysis paralysis.
- **`apple-design`**: Align with Apple Human Interface Guidelines, spatial depth, materials, and typography tokens.
- **`scope`** & **`defaults`**: Enforce crisp feature boundaries and opinionated house defaults (focus, scroll, type, surfaces).

### Phase 3: Construction & Component Craft (Build / TDD)
Used by the builder agent during feature and UI development:
- **Visual Design & Layout**:
  - **`emil-design-eng`**: Emil Kowalski's craft principles, micro-interactions, and visual polish.
  - **`frames`**, **`viewports`**, **`alignment`**, **`color`**, **`icons`**, **`avatar`**: Grid alignment, responsive breakpoint testing, accessible color tokens, SVG icon drafting, and avatar rendering.
  - **`mobile-native`**: Mobile-web ergonomics (100vh viewport fix, tap targets $\ge 44$px, safe area insets, no tap delay).
  - **`ask-sonner`**: Robust toast notification wiring and state management.
  - **`web-design-guidelines`**: Accessibility (a11y), contrast ratios, keyboard navigation, and web standards.
  - **`prose`** & **`copy`**: Clear UX copy, Title Case labels, typographic hierarchy, and concise microcopy.
- **Motion & Dynamics**:
  - **`animate`** & **`animate-expo`**: Physics-based animation authoring for web and React Native/Expo.
  - **`choreograph`**: Sequence and stagger complex multi-element transitions.
  - **`stageshow`**: Choreograph presentation flows, scene transitions, and demo showcases.
  - **`motion`** & **`animation-vocabulary`**: Map physical motion descriptions to exact spring parameters.

### Phase 4a: Runtime Verification & Visual Parity (Verification)
Used during `verify-app` to capture concrete runtime proof before PR opening:
- **`break-ui`**: Mandatory stress-testing of UI components against worst-case data (overflows, zero states, long unbreakable strings, extreme numbers, emoji).
- **`match`** & **`verify`**: Verify visual parity side-by-side against design specs or references.
- **`deconstruct`**: Frame-by-frame clock scrubber to inspect animated transitions against easing curves.
- **`lab`**: Force interactive component states open (hover, active, focus, disabled, error) for inspection.
- **`animation-performance`**: Ensure 60fps frame budgets, GPU compositing (`transform`, `opacity`), and zero main-thread jank.

### Phase 4b: Independent Audit & Interrogation (Audit)
Used by the independent auditor (`grok-4.7`) to enforce restraint and prevent visual churn:
- **`restraint`**: Identify visual clutter, decorative noise, and unnecessary elements that add friction.
- **`review-animations`**: Critique motion timing, spring overshoots, and awkward transitions against Emil Kowalski's standards.
- **`remove-animations`**: Strip unnecessary animations that slow user interaction down.
- **`rule`** & **`reuse`**: Enforce design token compliance, component reuse, and adherence to established patterns.

### Phase 5: Release & Packaging (Ship)
- **`ship`**: Production asset optimization, bundle sanity checks, and final release verification.


