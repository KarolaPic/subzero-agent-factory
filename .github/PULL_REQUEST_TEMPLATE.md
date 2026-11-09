## Summary

- **Source Issue / Ticket**: <!-- e.g. Closes #12 (for an epic's last deploy sub-issue PR, also include Closes #EPIC) or LIN-123; never use Refs #N -->
- **Specification / Plan**: <!-- e.g. docs/specs/<slug>.md -->
- **Playbook**: `poteto-mode` (`Autopilot-full`)

## Multi-Model Execution & Receipts (Zero-API-Key, Claude-Free)

| Phase | Pool | Model | Artifact / Verdict |
| :--- | :--- | :--- | :--- |
| **Phase 0: Context Scout** | `AGY_FAST` | `antigravity::gemini-3.8-flash-low` | Context brief (`<2KB`) |
| **Phase 1 & 2: Spec & Plan** | `AGY_FAST` | `antigravity::gemini-3.8-flash-high` | `docs/specs/<slug>.md` / DAG tickets |
| **Phase 3: Build (UI / CRUD)** | `AGY_FAST` | `antigravity::gemini-3.8-flash-medium` | Scoped minimal diff |
| **Phase 3: Build (Backend)** | `GROK_WORK` | `grok::grok-4.7-build-fast` | Scoped minimal diff |
| **Rework Escalation (<=2)** | `AGY_FAST` | `antigravity::gemini-3.8-flash-high` | `retryCount: 0..2` |
| **Phase 4a: Runtime Proof** | `AGY_FAST` | `antigravity::gemini-3.8-flash-medium` | `verify-app` (`exitCode: 0`) |
| **Phase 4b: Interrogation** | `GROK_AUDIT` | `grok::grok-4.7` (`reasoningEffort: high`) | `verdict: PASS` |
| **Phase 4c: Security Audit** | `GROK_AUDIT` | `grok::grok-4.7` (`reasoningEffort: high`) | `security-report.json` (`PASS`) |

### Phase 4a: Runtime Verification Proof
```text
# Paste verification command + exitCode: 0 + artifacts/<work-item-id>/ summary
```

### Phase 4b: Independent Grok 4.7 Interrogation Verdict
```text
verdict: PASS
```

### Phase 4c: Independent Security Audit Receipt
```text
verdict: PASS
# artifacts/<work-item-id>/security-report.json
```
