---
name: scaffold-project
description: Interactive project scaffolding wizard ($orchestrate new) that discovers project purpose, recommends tech stack, installs project-source skills via vercel-labs/skills find-skills, generates validated .factory.yml, and wires GitHub remotes.
---

# Scaffold Project Wizard (`scaffold-project`)

The interactive scaffolding wizard for creating external client projects orchestrated by the Subzero Agent Factory.

Accessible via:
```bash
$orchestrate new [<project-name>]
```
or via the CLI tool:
```bash
python3 scripts/scaffold_project.py --name <project-name> --framework <nextjs|expo|vite|python|rust|go> --github
```

---

## Interactive Wizard Protocol

When invoked with `$orchestrate new`, the agent executes a structured 5-step intake protocol:

### Step 1: Project Identity & Purpose
- If `<project-name>` was not provided, prompt the user for the project name.
- Inquire about the project purpose:
  - *What core problem does this project solve?*
  - *Who is the target user?*

### Step 2: Tech Stack Recommendation
- Based on the purpose, suggest the optimal framework:
  - **Interactive Web App**: Next.js (App Router, Tailwind CSS, TypeScript).
  - **Cross-Platform Mobile**: Expo (React Native, TypeScript).
  - **Client-Side SPA**: Vite + React (TypeScript).
  - **API / Machine Learning / Tooling**: Python (FastAPI / Typer).
  - **High-Performance Systems**: Rust (Cargo).
  - **Microservices / Backend**: Go.
- Allow the user to confirm the suggestion or specify a different stack.

### Step 3: Project-Source Skills Installation
- The wizard executes:
  ```bash
  npx --yes skills add https://github.com/vercel-labs/skills --skill find-skills
  ```
- **Strict Invariant**: Skills are installed into the **client project's source tree** (`<project>/.agents/skills/`), NEVER into Subzero's own factory repository.

### Step 4: Adapter Configuration (`.factory.yml`)
- Automatically generates `.factory.yml` conforming to `factory-adapter.schema.json`.
- Configures default verify and build commands:
  - Node.js: `npm test`, `npm run build`
  - Rust: `cargo test`, `cargo build`
  - Go: `go test ./...`, `go build ./...`
  - Python: `pytest`

### Step 5: GitHub Remote Bootstrap & Webhook Wiring
- Initializes local git repository on branch `main`.
- Creates a **public** repository via `gh repo create <name> --public --source . --push` using `cesarchavezcal` credentials.
- Provisions factory labels (`agent`, `epic`, `deploy`, `bug`) via `scripts/setup-labels.sh`.
- Optionally registers the webhook pointing to Subzero's `factory_daemon.py` endpoint (`/webhook`).
- Files Issue #1 (`epic` + `agent`) with the initial feature backlog if requested.
