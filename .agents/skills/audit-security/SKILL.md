---
name: audit-security
description: High-level security audit skill that audits git diff, dependencies, secrets, AST patterns, and LLM agent attack surfaces, or dispatches standalone defect issues for Grok Bot
---

# Security Audit Orchestrator (`audit-security`)

High-level security audit skill designed for autonomous verification of source code, dependencies, LLM/agent surfaces, and infrastructure within the Grok Bot Agent Factory.

---

## Operating Modes

```
Mode A: PR Gate (Phase 4c before squash-merge)
  Git Diff + Runtime Verification Proofs
       ↓
  Static Code Analysis + Secret Scan + Supply Chain Verification
       ├─ Clean / Low Severity → PASS → Authorize Squash Merge
       └─ Critical / High Finding → BLOCK → Escalate Rework to Gemini 3.8 Flash High (max 2 retries)

Mode B: Autonomous Defect Dispatcher (Continuous / Repository Scan)
  Repository-wide Scan / Threat Detection
       ↓
  Synthesize Evidence (Vulnerability, CWE, Exact Path, Line, Reproduction)
       ↓
  gh issue create --title "fix(security): <CWE-XXX Short Summary>" --label "bug,agent,security"
       ↓
  notify-grok.yml dispatches webhook to Grok Bot → Automatic fix via fix-bug pipeline
```

---

## Phase 1: Reconnaissance & Scope Assessment

- **Auditor Model**: `grok::grok-4.7` (`pool: GROK_AUDIT`, `reasoningEffort: high`, `readonly: true`).
- **Pre-scan Assistant**: `antigravity::gemini-3.8-flash-high` (`pool: AGY_FAST`).
- Determine target scope:
  - If auditing a PR / work-item: inspect `git diff origin/main...HEAD` and files touched by the ticket.
  - If auditing repository: inspect application entrypoints, API handlers, data models, workflows, and dependencies.

---

## Phase 2: Multi-Domain Security Inspection

### 1. Secret Scanning
- Execute non-destructive regex scan:
  ```bash
  .agents/skills/audit-security/scripts/scan-secrets.sh --diff-base origin/main
  ```
- Verify:
  - Zero hardcoded API keys, tokens, passwords, private keys, or webhook secrets.
  - Invariant: Zero paid API key references (`GEMINI_API_KEY`, `XAI_API_KEY`, `CURSOR_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
  - **Strict Redaction**: Never print or leak raw secret strings. Replace with `[REDACTED_SECRET_TYPE]`.

### 2. Application & Source Code Security (OWASP Top 10 & CWE)
- **Injection (CWE-89, CWE-78, CWE-79, CWE-94)**:
  - SQL / Database: Check for raw string concatenation or template literals in database queries. Enforce parameterized bindings.
  - Command Injection: Check for unsanitized user inputs passed to `child_process.exec`, `os.system`, `subprocess.Popen(..., shell=True)`.
  - Cross-Site Scripting (XSS): Check for unescaped HTML injection or dangerous DOM sinks (`dangerouslySetInnerHTML`, `innerHTML`, `document.write`).
  - Path Traversal (CWE-22): Check for user-controlled paths passed to `fs.readFile`, `open()`, without path sanitization or containment checks.
- **Access Control & Authorization (CWE-284, CWE-862, BOLA/IDOR)**:
  - Verify every route or mutation validates authentication and user tenant/resource ownership.
- **Cryptographic & Data Exposure (CWE-327, CWE-312)**:
  - Verify secure password hashing (argon2id, bcrypt, pbkdf2) and safe random generation (`crypto.randomBytes`).

### 3. Supply Chain & Lockfile Integrity
- Check locked skills integrity:
  ```bash
  .agents/skills/audit-security/scripts/verify-skills-hashes.sh
  ```
- Package manifests (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`):
  - Check for unpinned dependencies or known vulnerable package ranges.
  - Check `npm audit --audit-level=high` if running in a Node.js project.

### 4. AI Application & LLM Agent Security (OWASP LLM Top 10)
- **Prompt Injection (LLM01)**:
  - Untrusted data (issue bodies, PR comments, user webhooks) must be isolated with clear boundary delimiters.
  - Verify agent instructions cannot be overridden by input content.
- **Excessive Agency & Permissions (LLM06)**:
  - Verify agents and tools follow least privilege: read-only where possible, no unrestricted shell/network tools without validation.
- **System Prompt & Secret Leakage (LLM02)**:
  - Ensure system prompts and internal API endpoints are not returned in user-facing error responses.

---

## Phase 3: Evidence Generation & Reporting

Generate structured artifact under `artifacts/<work-item-id>/security-report.json`:

```json
{
  "workItemId": "<work-item-id>",
  "timestamp": "ISO-8601",
  "auditorModel": "grok::grok-4.7",
  "verdict": "PASS | WARN | BLOCK",
  "summary": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "info": 0
  },
  "findings": [
    {
      "id": "SEC-001",
      "title": "CWE-89 SQL Injection in user search query",
      "severity": "HIGH",
      "confidence": "CONFIRMED",
      "cwe": "CWE-89",
      "filePath": "src/api/users.ts",
      "lineRange": "L42-L48",
      "evidenceSnippet": "db.query(`SELECT * FROM users WHERE name = '${input}'`)",
      "attackScenario": "Attacker supplies payload to bypass auth and extract tables",
      "reachability": "REACHABLE",
      "remediation": "Use parameterized query: db.query('SELECT * FROM users WHERE name = ?', [input])",
      "status": "DEFECT"
    }
  ]
}
```

---

## Phase 4: Decision Gates & Rework / Dispatch

### Mode A: PR Gate Decision
- **`PASS`**: Zero critical/high vulnerabilities. PR is cleared for squash-merge.
- **`BLOCK`**: One or more critical/high vulnerabilities detected:
  - Halt merge immediately.
  - Escalate rework to **`antigravity::gemini-3.8-flash-high`** (effort: high).
  - Maximum 2 rework attempts (`maxRetries: 2`).
  - If still unresolved after 2 retries, mark work-item as `blocked` and stop for human intervention.

### Mode B: Autonomous Issue Creation (Standalone Threats)
When standalone security defects are discovered outside the immediate PR scope:
1. Do NOT comment on any issue or PR.
2. Run `gh issue create` with labels `["bug", "agent", "security"]`:
   ```bash
   gh issue create \
     --title "fix(security): <CWE-XXX Description>" \
     --label "bug,agent,security" \
     --body "### Grok Bot Agent Factory — Security Defect
**Vulnerability**: <CWE-ID and title>
**Severity**: <CRITICAL | HIGH | MEDIUM>
**Affected Component**: <file path and lines>

### What happened?
<Factual explanation of defect without exposing raw secrets>

### Expected behavior
<Secure pattern required>

### Remediation
<Actionable instructions for the builder>"
   ```
3. The presence of the `agent` label automatically triggers `.github/workflows/notify-grok.yml`, dispatching the fix to Grok Bot.
