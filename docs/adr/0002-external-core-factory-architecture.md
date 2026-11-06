# 0002: External Core Factory Architecture (Hub-and-Spoke)

## Status
Accepted

## Context
The previous template model embedded the entire agent factory infrastructure (`.agents/skills/`, `.factory/`, `scripts/`, `.github/workflows/`, and `AGENTS.md`) into each working repository. While this allowed repos to operate self-contained, it created severe repository footprint bloat, required frequent and error-prone `sync-template.sh` pull requests across all client projects, duplicated dozens of locked scripts, and fragmented lessons learned into project silos.

## Decision
We decouple the factory into an **External Core Factory (Hub)** that operates on clean **Target Projects (Spokes)** from the outside.

Key architectural decisions:
1. **Hybrid Execution Model**: The core engine is built as a stateless, deterministic CLI runner (`scripts/factory-run.sh` or `factory-run`), with a lightweight webhook listener daemon on top for background dispatches.
2. **Zero-Config with Adapter Override**: The runner auto-detects standard language build/test suites (`npm test`, `pytest`, `cargo test`, `go test`). Projects requiring multi-step verification or custom configurations provide a minimal `.factory.yml`.
3. **External Worktree Isolation**: The factory creates isolated Git worktrees under `~/.factory/worktrees/<repo-slug>/<issue-id>` rather than polluting the client's working directory or `.gitignore`.
4. **Layered Skills Resolution**: Worktrees dynamically overlay Global Core Skills (`poteto-mode`, `tdd`, `implement-ticket`, `fix-bug`, `plan-epic`) via symlinks, with Project-Local Skills (`<project>/.agents/skills/*`) taking precedence on name collisions.
5. **Git Identity Governance**: Defaults strictly to `cesarchavezcal` (`cesarchavezcal@gmail.com`) with automatic `gh auth` switching and restoring, allowing `.factory.yml` overrides for work/organization repositories.
6. **Dual-Tier Memory**: General engineering lessons, rubric violations, and security patterns aggregate globally in `~/.factory/memory/`, with an optional local `.factory/memory/` for project-specific business domain constraints.

## Consequences
- **Positive**: Target projects remain completely clean of factory boilerplate. Core improvements to skills and prompts immediately benefit all projects. Lessons learned in one project compound across all projects.
- **Negative / Mitigations**: The factory must manage worktree lifecycles and cleanup reliably; handled via atomic directory locks and trap-based worktree pruning.
