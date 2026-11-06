# External Core Factory Guide

This guide describes how to operate the **External Core Factory (Hub-and-Spoke)** architecture defined in [ADR 0002](adr/0002-external-core-factory-architecture.md).

The External Core Factory allows you to orchestrate autonomous agent lifecycles across external target repositories without duplicating factory scripts, prompts, workflows, or skills inside each client project.

---

## 1. Architecture Overview

```
                      ┌─────────────────────────────────────────┐
                      │   External Core Factory (Hub)           │
                      │   - factory_runner.py                   │
                      │   - factory_daemon.py                   │
                      │   - project_adapter.py                  │
                      │   - skills_resolver.py                  │
                      │   - git_identity.py                     │
                      │   - Global Memory (~/.factory/memory/)  │
                      └────────────────────┬────────────────────┘
                                           │
                    Orchestrates Worktrees │ (stateless & isolated)
                                           ▼
       ┌───────────────────────────────────┴───────────────────────────────────┐
       │                                                                       │
       ▼                                                                       ▼
┌───────────────────────────────┐                       ┌───────────────────────────────┐
│ Target Project A (Node.js)    │                       │ Target Project B (Rust/Go/Py) │
│ Staged at:                    │                       │ Staged at:                    │
│ ~/.factory/worktrees/repoA/1  │                       │ ~/.factory/worktrees/repoB/2  │
│ - Zero factory boilerplate    │                       │ - Optional .factory.yml       │
│ - Local skills override       │                       │ - Isolated branch & cleanup   │
└───────────────────────────────┘                       └───────────────────────────────┘
```

---

## 2. CLI Runner (`factory_runner.py`)

The primary execution vehicle is the CLI runner. It creates isolated worktrees under `~/.factory/worktrees/<repo-slug>/<issue-id>` and handles POSIX trap cleanup automatically:

```bash
python3 scripts/factory_runner.py \
  --repo https://github.com/my-org/my-project.git \
  --issue 42 \
  --branch feat/42-new-feature
```

### Supported Flags

| Flag | Required | Description |
| :--- | :--- | :--- |
| `--repo` | Yes | Target project git repository URL, remote, or local directory path |
| `--issue` | Yes | Target issue number or unique identifier |
| `--branch` | Yes | Branch name to checkout or create |
| `--dry-run` | No | Print actions without altering files or creating worktrees |
| `--base-dir` | No | Custom worktree staging directory (defaults to `~/.factory/worktrees`) |

---

## 3. Zero-Config Framework Detection & `.factory.yml`

By default, the factory automatically detects standard build and verification commands:

| Language / Marker | Detected Framework | Default Verify Command | Package Manager |
| :--- | :--- | :--- | :--- |
| `package.json` | Node.js (`node`) | `npm test` | `npm` |
| `pyproject.toml` / `requirements.txt` | Python (`python`) | `pytest` | `pip` |
| `Cargo.toml` | Rust (`rust`) | `cargo test` | `cargo` |
| `go.mod` | Go (`go`) | `go test ./...` | `go` |

### Customizing with `.factory.yml`

For multi-step verification or custom setups, add a `.factory.yml` to the root of the target project:

```yaml
# .factory.yml
name: customer-billing-service
framework: node
base_branch: main
verify_command: npm run test:ci && npm run lint
build_command: npm run build
package_manager: pnpm

# Skill overrides
exclude_skills:
  - apple-design
  - mobile-native

# Multi-identity Git overrides
github_user: my-org-bot
git_email: bot@my-org.com

# Memory tier (global, local, or dual)
memory_tier: global
```

The configuration is strictly validated against `.factory/schemas/factory-adapter.schema.json`.

---

## 4. Layered Skills Resolution (`skills_resolver.py`)

When an external worktree is staged, `skills_resolver.py` dynamically overlays Global Core Skills from the factory repository into `.agents/skills/`:

1. **Symlink Isolation**: Global skills are linked via symlinks without committing anything to the client project's git index.
2. **Local Precedence**: If the client repository defines its own `.agents/skills/<skill-name>`, the local version takes precedence and the global skill is not linked.
3. **Exclusion Filtering**: Skills listed under `exclude_skills` in `.factory.yml` are omitted.

```bash
# Manually overlay skills into a worktree
python3 scripts/skills_resolver.py --worktree ~/.factory/worktrees/my-project/42

# Clean up overlay symlinks
python3 scripts/skills_resolver.py --worktree ~/.factory/worktrees/my-project/42 --clean
```

---

## 5. Webhook Listener Daemon (`factory_daemon.py`)

To dispatch agent runs automatically from GitHub issues, run the lightweight HTTP daemon:

```bash
python3 scripts/factory_daemon.py --port 8088 --concurrency 4
```

### GitHub Webhook Configuration
1. In your GitHub repository settings, navigate to **Webhooks** $\to$ **Add webhook**.
2. **Payload URL**: `https://<your-factory-domain>/webhook` (or ngrok/tunnel during development).
3. **Content type**: `application/json`.
4. **Events**: Select **Issues**.
5. When an issue is labeled with `agent`, the daemon receives the event and queues an asynchronous job in the runner thread pool.

---

## 6. Git Identity Governance (`git_identity.py`)

All commits and PR operations strictly default to `cesarchavezcal` (`cesarchavezcal@gmail.com`).

The governance engine automatically:
- Checks `gh auth status` before git push/PR creation.
- Switches active `gh` auth to `cesarchavezcal` (or custom user from `.factory.yml`).
- Automatically restores the previous account upon completion or failure.
