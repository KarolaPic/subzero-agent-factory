# Subzero Agent Factory (Codename: Subzero)

Autonomous, zero-paid-API-key, Claude-free software factory template orchestrated with **T3 Code**, official **`mattpocock/skills`**, and official **`pstack` (`poteto-mode`)**, designed to work with an external issue dispatcher (**Grok Bot**).

> **Codename: Subzero**
>
> * **Subzero Cost**: Strict zero-cost invariant (`"strictZeroCost": true`). Operates exclusively through signed-in model sessions (Gemini / Antigravity quota + Grok / Cursor free tiers) with zero paid API keys (`GEMINI_API_KEY`, `XAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` are forbidden).
> * **Cold Autonomous Precision**: Worktree-isolated execution, test-driven development (TDD), runtime verification, independent adversarial audits, and automated merge gates without human intervention.

---

## Quick Start (`template init` — Public Working Repos)

> **Note on Visibility (GitHub Free):** This template repository (`cesarchavezcal/subzero-agent-factory`) is **PRIVATE**, but **all working repositories created from it MUST be PUBLIC** (`--public`) so GitHub Free enables branch protection (`ci` required status check) and `allow_auto_merge`.

When creating a new project from this template (manually or via **Grok Bot**):

```bash
# 1. Create a PUBLIC working repository from the template
gh repo create <name> --public --template cesarchavezcal/subzero-agent-factory --clone
cd <name>

# 2. Run the idempotent initialization script
./scripts/init.sh
```

*(Alternatively, inside an existing local checkout without a remote yet, run `./scripts/init.sh --create-repo <name>` to create the public GitHub repository and bootstrap it in one step.)*

[`./scripts/init.sh`](scripts/init.sh) is 100% idempotent and safe to re-run at any time without duplicate side effects. It:
1. Verifies required CLI tools (`git`, `gh` authenticated, `node`, `npx`).
2. Installs/restores all official skills pinned by commit SHA and hash in [`skills-lock.json`](skills-lock.json) into `.agents/skills/`.
3. Creates/updates GitHub repository labels (`agent`, `epic`, `deploy`, `bug`, etc.) via [`./scripts/setup-labels.sh`](scripts/setup-labels.sh).
4. Configures GitHub merge policy via `gh api PATCH` (`allow_auto_merge=true`, `allow_squash_merge=true`, `delete_branch_on_merge=false`) and **Branch protection on `main`** via `gh api PUT` with the required status check **`ci`**. If a repository is private on GitHub Free (`403 / upgrade`), it emits a clear, explicit warning instead of failing silently.
5. Checks `gh secret list` for `GROK_WEBHOOK_URL` and `GROK_WEBHOOK_AUTH`, interactively running `gh secret set` (hidden input) for any missing secret when a TTY is present, or printing a clear reminder without failing if skipped or run non-interactively.
6. Verifies/sets up model choices in [`models.yml`](models.yml) using [`./scripts/setup-models.sh`](scripts/setup-models.sh) from [`models.allowed.yml`](models.allowed.yml).
7. Updates the project slug in [`.factory/config.json`](.factory/config.json) and prints the optional T3 Code project registration command.

See [`docs/setup.md`](docs/setup.md) for manual GitHub/Linear setup details and [`AGENTS.md`](AGENTS.md) for the complete agent operating contract.

### Syncing Upstream Template Updates (`sync-template.sh`)

Inside any working repository derived from this template (or from a template checkout targeting another repo via `--target`), pull the latest managed workflows, scripts, skills, and rules from the private `cesarchavezcal/subzero-agent-factory` template and open a PR:

```bash
./scripts/sync-template.sh                          # Sync from `main` (default)
./scripts/sync-template.sh --ref <ref>              # Sync from a specific branch, tag, or SHA
./scripts/sync-template.sh --target /path/to/repo   # Sync another repo from a template checkout
./scripts/sync-template.sh --dry-run                # Print diff summary without creating a branch/PR
```

- **First-Time Sync Ready**: If the target repo does not yet have `.factory/template-sync.json`, the script fetches the manifest from the template ref via `gh` auth, uses it to drive the sync, and includes `.factory/template-sync.json` in the synced files.
- **Remote Target (`--target <path>`)**: Can be run from a template checkout against another local repo; both the dirty-tree guard and the template self-guard apply to the target repo rather than the script location.
- **Explicit Manifest ([`.factory/template-sync.json`](.factory/template-sync.json))**: Syncs only managed factory paths (`.factory/template-sync.json`, `.github/workflows/*`, `.github/ISSUE_TEMPLATE/*`, `scripts/*`, `.agents/skills/*`, `.cursor/rules`, `.cursor/agents`, `AGENTS.md`, `skills-lock.json`, `.factory/work-item.schema.json`, `.factory/WORK-ITEM.example.json`) and never touches application code or `.factory/config.json`.
- **Idempotent**: Prints a diff summary and creates no branch or PR when nothing changed.
- **Version Tracking ([`.factory/template-version`](.factory/template-version))**: Records the synced 40-character template commit SHA.

---

## Workflow Overview

1. **Intake & Dispatch Routing (`agent`, `bug`, `epic` labels)**:
   - Only GitHub Issues or Linear Issues labeled with **`agent`** are ingested. Everything else is ignored.
   - [`.github/workflows/notify-grok.yml`](.github/workflows/notify-grok.yml) triggers on `issues` (`types: [labeled]`) when `github.event.label.name == 'agent'` and passes the full event payload enriched with explicit top-level `labels`, a stable `idempotency_key` (`<repo>#<issue>`), and `delivery_id` to `GROK_WEBHOOK_URL` (with `Authorization: $GROK_WEBHOOK_AUTH`).
   - **Double-Fire Prevention**: Triggering strictly on `labeled` for `agent` eliminates duplicate webhook runs when issues are created with initial template labels. Concurrency per issue (`cancel-in-progress: false`) ensures reliable sequential delivery.
   - **Skill Routing Matrix & Precedence**:
     - **`epic` + `agent`** -> **[`plan-epic`](.agents/skills/plan-epic/SKILL.md)** (or **`$orchestrate plan`**): Planning-only flow that decomposes an epic into vertical tracer-bullet sub-issues. Every created sub-issue MUST have `agent`; exactly one final sub-issue receives `deploy`. Label existence is verified before ending. `epic` takes precedence over all other labels. Epics stay planning-only (no build).
     - **`bug` + `agent`** -> **[`fix-bug`](.agents/skills/fix-bug/SKILL.md)** (or **`$orchestrate bug`**): Reproduction-first defect workflow. Starts with a short plan in thread. Reproduces first (if not reproducible or open questions, stops and asks in thread final message; if no questions, writes `"No questions, starting build"` and builds immediately in the same run) -> failing test -> root cause fix (`ce-debug`, `tdd`, `principle-fix-root-causes`) -> verifies all tests + runs app once -> Grok audit -> PR `Closes #N` -> merge on green CI.
     - **`agent` alone (or with `feature`)** -> **[`implement-ticket`](.agents/skills/implement-ticket/SKILL.md)** (or **`$orchestrate code`**): Standard feature pipeline orchestrating plan (`wayfinder` + `grill-with-docs`) -> build (`poteto-mode`) -> Grok audit -> rework -> PR `Closes #N` -> squash merge on green CI. If no questions, proceeds directly to build without waiting for a separate build message. Deploys only if the issue carries the `deploy` label.
     - **Unified Manual Entry Point (`$orchestrate`)**: Manual runs in T3 Code use **[`$orchestrate`](.agents/skills/orchestrate/SKILL.md)**: `$orchestrate plan` (epic decomposition), `$orchestrate bug` (defect repair), `$orchestrate code` (feature ticket), or `$orchestrate <#N | query>` (full autonomous initiative runner via `run-epic`). Existing commands (`$run-epic`, `$plan-epic`, `$implement-ticket`, `$fix-bug`) remain 100% supported as direct aliases.
2. **Workflow & Agent-Run Rules (Plan-Then-Build & GitHub Account)**:
   - **Plan-Then-Build**: Every issue thread starts with a short plan in the thread (files, tests, verification). If there is ANY open question, ask it in the thread and stop without editing files. Wait for human answer, then build. If NO questions, write `"No questions, starting build"` and continue to the build in the same run (no waiting for a separate build message). Epics stay planning-only: create `agent` sub-issues, no build. Keep all existing gates (PR with `Closes #N`, Grok audit, squash-merge only when `ci` is green AND audit passes, deploy only for `deploy` sub-issue).
   - **GitHub Account Rule (`cesarchavezcal`)**: Every commit, push, and PR uses `cesarchavezcal`. Check `gh auth status` first; switch with `gh auth switch --user cesarchavezcal` if needed, and switch back to the earlier account when done. Keep git email `cesarchavezcal@gmail.com` via `includeIf`, never changing the global git email.
3. **Communication Discipline**:
   - **Never comment on GitHub/Linear issues or PRs**.
   - If clarification or reproduction guidance is needed for César, the agent stops immediately and writes the questions in the **thread final message**. The external dispatcher (**Grok Bot**) relays it to César.
4. **Planning (`mattpocock/skills`)**:
   - Uses official skills pinned in [`skills-lock.json`](skills-lock.json): [`wayfinder`](.agents/skills/wayfinder/SKILL.md), [`grill-with-docs`](.agents/skills/grill-with-docs/SKILL.md), [`grilling`](.agents/skills/grilling/SKILL.md), [`domain-modeling`](.agents/skills/domain-modeling/SKILL.md), [`to-spec`](.agents/skills/to-spec/SKILL.md), [`to-tickets`](.agents/skills/to-tickets/SKILL.md), and [`tdd`](.agents/skills/tdd/SKILL.md).
5. **Build & Merge (`pstack` `poteto-mode` · `Autopilot-full`)**:
   - Follows official [`poteto-mode`](.agents/skills/poteto-mode/SKILL.md) under the [`Autopilot-full`](.agents/skills/poteto-mode/playbooks/autopilot-full.md) playbook + [`tdd`](.agents/skills/tdd/SKILL.md).
   - Every PR body uses `Closes #N` (never `Refs #N`). For epics, the final deploy sub-issue PR also includes `Closes #EPIC`.
   - Merges via **squash merge** (`gh pr merge <PR_NUMBER> --squash` without `--delete-branch`) only when **`ci` is green** AND **independent verification + Grok audit** pass. Branches are never deleted.

---

## Model Configuration & Setup (`models.yml`)

The template lets users pick their models at setup via [`./scripts/setup-models.sh`](scripts/setup-models.sh) (or `./scripts/setup-models`). Choices are stored in [`models.yml`](models.yml) at the repo root:

- **`builder`**: Implementation, testing, and bug fixing.
- **`auditor`**: Independent adversarial code interrogation. **Must differ from builder**.
- **`planner`**: Architecture discovery, spec generation, and grilling (defaults to `builder`).
- **`epic_planner`**: Initiative epic breakdown into vertical sub-issues (defaults to `builder`).
- **`subagents`**: Auxiliary subagents and background workers (defaults to `builder`).

### Allowed Models List (`models.allowed.yml`)
The setup script and CI checks only permit models declared in [`models.allowed.yml`](models.allowed.yml):
- `gemini-3.8-flash-low`
- `gemini-3.8-flash-medium`
- `gemini-3.8-flash-high`
- `grok-4.7`

Committed defaults: `builder: gemini-3.8-flash-high`, `auditor: grok-4.7`, and `planner`, `epic_planner`, `subagents` defaulting to `gemini-3.8-flash-high`.

### Strict Invariants
- **Auditor Must Differ from Builder**: The script refuses identical models, and CI check fails on it.
- **Model Not Available Rule**: If a configured model is unavailable, the factory **stops immediately and informs the user**. No fallback models, no retries.
- **Zero Paid API Keys**: Never requires paid keys (`GEMINI_API_KEY`, `XAI_API_KEY`, `CURSOR_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
- **100% Claude & GPT Free**: Never routes to Claude or GPT models (`disallowClaude: true`).
- **Zero Argon Usage**: Argon models are completely retired.

---

## Repository Structure

```text
.
├── AGENTS.md                                    # Agent operating contract & pipeline rules
├── README.md                                    # Overview & quick start
├── models.allowed.yml                           # Allowed model list for the template
├── models.yml                                   # Configured roles to model mappings
├── skills-lock.json                             # Locked official skills (mattpocock/skills + pstack)
├── .agents/skills/                              # Official skills + orchestrators + verify-app template
│   ├── orchestrate/                             # Unified top-level orchestrator interface
│   ├── run-epic/                                # Autonomous epic initiative runner skill
│   ├── implement-ticket/                        # High-level feature orchestrator skill
│   ├── fix-bug/                                 # High-level bug fixing orchestrator skill
│   ├── plan-epic/                               # High-level epic planning orchestrator skill
│   ├── wayfinder/
│   ├── grill-with-docs/
│   ├── grilling/
│   ├── domain-modeling/
│   ├── to-spec/
│   ├── to-tickets/
│   ├── tdd/
│   ├── poteto-mode/
│   └── verify-app/
├── .cursor/
│   ├── rules/factory.mdc                        # Always-applied factory rules
│   └── agents/                                  # Builder (Flash/Grok) & Interrogator (Grok) profiles
├── .factory/
│   ├── config.json                              # Generic factory & model routing configuration
│   ├── template-sync.json                       # Explicit manifest of managed template sync paths
│   ├── template-version                         # Synced template commit SHA
│   ├── schemas/                                 # Schemas (lesson.schema.json, patterns.schema.json)
│   ├── work-item.schema.json                    # Work-item JSON schema
│   ├── WORK-ITEM.example.json                   # Work-item example
│   ├── memory/                                  # Persistent memory store (lessons.jsonl, patterns.json)
│   └── work-items/.gitkeep                      # Runtime work-items directory
├── .github/
│   ├── ISSUE_TEMPLATE/                          # Issue forms (bug.yml, feature.md, config.yml)
│   ├── PULL_REQUEST_TEMPLATE.md                 # Generic PR receipt template
│   └── workflows/
│       ├── ci.yml                               # Generic CI workflow (stable check name: `ci`)
│       ├── evaluate-run.yml                     # Outer loop post-merge evaluation workflow
│       └── notify-grok.yml                      # Dispatches `agent`-labeled issues to Grok Bot webhook
├── docs/
│   ├── adr/                                     # Architecture Decision Records (ADR 0001)
│   └── setup.md                                 # Setup, models, branch protection, auto-merge & sync guide
├── scripts/
│   ├── evaluate_run.py                          # Post-merge evaluation runner
│   ├── evaluator.py                             # Lesson extraction against quality rubrics
│   ├── init.sh                                  # Idempotent `template init` bootstrap script
│   ├── memory_store.py                          # Process-safe memory store client with flock
│   ├── routine_maker.py                         # Synthesizes patterns into skill PRs
│   ├── setup-labels.sh                          # Idempotent GitHub labels script (+ Linear note)
│   ├── setup-models.sh                          # Model setup script (writes models.yml)
│   ├── setup-models                             # Executable symlink to setup-models.sh
│   ├── sync-template.sh                         # Idempotent upstream template sync & PR script
│   ├── validate_models.py                       # Validates models.yml against models.allowed.yml
│   └── validate-models.py                       # Executable symlink to validate_models.py
└── tests/
    ├── test_evaluate_run.py                     # Tests for post-merge PR evaluation
    ├── test_evaluator.py                        # Tests for lesson extraction and rubrics
    ├── test_memory_store.py                     # Tests for atomic appending and locking
    ├── test_models.py                           # Tests for models.yml validation & CLI setup
    ├── test_notify_grok.py                      # Tests for webhook payload & duplicate prevention
    └── test_routine_maker.py                    # Tests for Receipt of Causality generation
```
