---
name: run-epic
description: Autonomous orchestrator skill that executes an entire epic initiative end-to-end, decomposing into sub-issues (or reusing existing ones) and driving sequential implementation, verification, audit, PR merges, and final deployment.
---

# Run Epic Orchestrator (`run-epic`)

Autonomous orchestrator skill that drives an entire initiative-level epic from a single command: `$run-epic #N`. It handles automated decomposition (or reuses existing sub-issues), sequential ticket implementation, independent verification and audit gates, PR squash merging, and final deployment without requiring human babysitting or an active Grok Bot dispatcher.

---

## Workflow Overview

```
$run-epic #N
     │
     ▼
[Phase 1: Epic Intake & Discovery]
  ├─ Inspect target Epic #N (Goal, Done when, Don't touch)
  ├─ Query existing sub-issues: gh issue list --search "Part of #N"
  ├─ If sub-issues exist ──► Reuse discovered sub-issues in dependency order
  └─ If none exist ───────► Invoke plan-epic #N to decompose & verify labels
     │
     ▼
[Phase 2: Anti-Clash & Concurrency Guard]
  ├─ Check Grok Bot activity on candidate sub-issue
  ├─ Inspect 'in-progress' label / open PRs / active worktree branches
  └─ If already in progress ──► Pause or report to avoid duplicate runs
     │
     ▼
[Phase 3: GitHub Account Switch & Model Validation]
  ├─ Switch active gh auth to 'cesarchavezcal' (record previous account)
  ├─ Read epic_planner, planner, builder, auditor from models.yml
  └─ Check model availability (if unavailable: STOP immediately, NO fallback)
     │
     ▼
[Phase 4: Sequential Execution Loop (Sub-issues 1 .. N)]
  For each sub-issue in dependency order:
  ├─ 1. Check if already merged ──► Skip cleanly (idempotent resumption)
  ├─ 2. If PR already open ─────► Reattach & wait for CI / audit / merge
  ├─ 3. If unstarted:
  │      ├─ Label issue: 'in-progress'
  │      ├─ Execute implement-ticket (or fix-bug for bug tickets)
  │      ├─ TDD & runtime app verification (verify-app)
  │      ├─ Independent adversarial audit (grok-4.7)
  │      └─ Open PR (Closes #<SUB_ISSUE>)
  ├─ 4. Reviewer Agent Gate (review-pr):
  │      ├─ Execute review_pr.py --pr <PR> --issue <SUB_ISSUE>
  │      ├─ Formally submits APPROVE or REQUEST_CHANGES (up to 3 rounds)
  │      └─ If unapproved after 3 rounds ──► HALT & report to César
  ├─ 5. Three-Tier Risk Merge Gate:
  │      ├─ Required status check 'ci' MUST be green
  │      ├─ low-risk ──► auto squash merge
  │      ├─ normal ──► auto squash merge on green CI + review-pr APPROVE
  │      ├─ high-risk / needs-approval ──► STOP and ask César in thread final message
  │      └─ gh pr merge <PR> --squash (NEVER pass --delete-branch)
  ├─ 6. Log Run: Append run outcome to .factory/runs/runs.jsonl with review metrics
  └─ 7. Clean up 'in-progress' label
     │
     ▼
[Phase 5: Final Deploy & Epic Closure]
  ├─ Inspect final sub-issue for 'deploy' label
  ├─ Final sub-issue PR MUST contain BOTH:
  │    Closes #<FINAL_SUB_ISSUE>
  │    Closes #<EPIC_NUMBER>
  ├─ Execute post-merge deploy workflow
  └─ Restore previous GitHub auth account
```

---

## Phase 1: Epic Intake & Discovery

1. **Invocation**:
   Command pattern: `$run-epic #<EPIC_NUMBER>` or `$run-epic <EPIC_NUMBER>`.
2. **Inspect Epic Task Card**:
   - Fetch the epic:
     ```bash
     gh issue view "$EPIC_NUMBER" --json title,body,labels,state
     ```
   - Verify task card sections per `AGENTS.md` Section 2:
     - **Goal**
     - **Done when**
     - **Don't touch**
   - If any section is missing or ambiguous, **STOP immediately** and write questions in the thread final message.
3. **Sub-Issue Discovery vs. Decomposition**:
   - Search for existing sub-issues created for this epic:
     ```bash
     EXISTING_SUB_ISSUES=$(gh issue list --search "Part of #$EPIC_NUMBER in:body" --json number,title,labels,state --limit 50)
     ```
   - **Case A (Sub-issues already exist)**:
     - Parse the list into dependency order.
     - Verify sub-issues carry `agent` label, and exactly one final sub-issue carries `deploy`.
     - Log: `"Reusing existing sub-issues for Epic #<N>: <IDs>"`
   - **Case B (No sub-issues exist yet)**:
     - Execute [`plan-epic`](../plan-epic/SKILL.md) on `#EPIC_NUMBER`.
     - `plan-epic` generates the vertical tracer-bullet sub-issues with `agent` labels, applies `deploy` to the final sub-issue, and validates the label invariants.
     - Capture the newly created sub-issue numbers into the execution queue.

---

## Phase 2: Anti-Clash & Concurrency Guard (Grok Bot & Parallel Runs)

When operating in an environment where Grok Bot may also be listening for `agent` labels or running concurrent sub-agents:

1. **Pre-Flight Sub-Issue Status Check**:
   Before picking up any sub-issue `#SUB_NUM`:
   ```bash
   SUB_DATA=$(gh issue view "$SUB_NUM" --json labels,state,assignees)
   ```
2. **Anti-Collision Checks**:
   - **Closed Check**: If `state == "CLOSED"`, the sub-issue is already done. Skip immediately.
   - **Label Check**: If `labels` contains `in-progress` AND an active remote branch or open PR exists by another actor:
     - Check the latest commit / PR author and timestamp.
     - If actively touched within the last 30 minutes, pause and report:
       `"Sub-issue #<SUB_NUM> is currently in-progress by another agent. Pausing run-epic to avoid collision."`
   - **Open PR Check**:
     ```bash
     OPEN_PR=$(gh pr list --search "head:feat/$SUB_NUM- in:comments Closes #$SUB_NUM" --json number,headRefName,state)
     ```
     - If an open PR already exists for `#SUB_NUM`, do NOT create a new branch or duplicate PR. Reattach to the existing PR, run CI / audit verification, and drive it to merge.
3. **Claiming the Sub-Issue**:
   - If no conflict exists, add the `in-progress` label to signal to Grok Bot and other workers that this issue is actively claimed:
     ```bash
     gh issue edit "$SUB_NUM" --add-label "in-progress"
     ```

---

## Phase 3: Model Configuration & Unavailability Gate

1. **Read Models from `models.yml`**:
   - `epic_planner`: used for initial epic decomposition (if needed).
   - `planner`: used for sub-issue planning and spec authoring.
   - `builder`: used for TDD implementation and runtime verification.
   - `auditor`: used for independent adversarial interrogation.
2. **Strict Invariants**:
   - **Auditor Must Differ from Builder**: Enforce `auditor != builder`.
   - **Model Availability Check**:
     - Verify that all configured models are present and accessible in the environment.
     - **Model Unavailability Rule**: If any required model is unavailable, **STOP IMMEDIATELY**.
     - **NEVER use a fallback model, and NEVER retry**.
     - Write an explicit alert in the thread final message citing the missing model.
   - **No Prohibited Models**: Strictly zero Claude, GPT, or Argon models.

---

## Phase 4: GitHub Account & Identity Invariant

1. **Before Any Git/GitHub Operations**:
   - Check the currently active account:
     ```bash
     PREV_ACCOUNT=$(gh auth status 2>&1 | grep "Active account: true" -B 2 | grep "account" | awk '{print $NF}')
     ```
   - If not `cesarchavezcal`, switch:
     ```bash
     gh auth switch --user cesarchavezcal
     ```
   - Verify git author email is `cesarchavezcal@gmail.com`.
2. **Upon Completion or Interruption**:
   - When the run completes (or halts on error/question), switch back to `$PREV_ACCOUNT` if it was set and differed from `cesarchavezcal`:
     ```bash
     gh auth switch --user "$PREV_ACCOUNT"
     ```

---

## Phase 5: Sequential Execution Loop

Process each discovered sub-issue chronologically: `Sub-issue 1`, `Sub-issue 2`, ..., `Sub-issue N`.

```bash
for SUB_NUM in "${SUB_ISSUES[@]}"; do
  # Step 1: Idempotency check - skip if already closed/merged
  STATE=$(gh issue view "$SUB_NUM" --json state --jq '.state')
  if [ "$STATE" = "CLOSED" ]; then
    echo "Sub-issue #$SUB_NUM is already closed/merged. Skipping."
    continue
  fi

  # Step 2: Concurrency guard - claim issue
  gh issue edit "$SUB_NUM" --add-label "in-progress"

  # Step 3: Branch checkout
  BRANCH="feat/${SUB_NUM}-slice"
  # If remote branch exists, check out; otherwise create off origin/main
  if git ls-remote --heads origin "$BRANCH" | grep -q "$BRANCH"; then
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
  else
    git checkout -b "$BRANCH" origin/main
  fi

  # Step 4: Dispatch implementation
  # Inspect if sub-issue has 'bug' label -> run fix-bug; else run implement-ticket
  IS_BUG=$(gh issue view "$SUB_NUM" --json labels --jq '[.labels[].name] | contains(["bug"])')
  if [ "$IS_BUG" = "true" ]; then
    echo "Executing fix-bug on #$SUB_NUM..."
    # Execute fix-bug lifecycle (poteto-mode tdd + verification + grok audit)
  else
    echo "Executing implement-ticket on #$SUB_NUM..."
    # Execute implement-ticket lifecycle (wayfinder + poteto-mode + grok audit)
  fi

  # Step 5: Verification & Audit Gates
  # A. Runtime verification: verify-app must pass (exitCode 0)
  # B. Independent adversarial audit (grok-4.7): verdict MUST be PASS
  # Rework rule: up to 2 rework attempts if audit or verification fails

  # Step 6: PR creation or update
  # Ensure PR body contains correct Closes directive
  IS_DEPLOY=$(gh issue view "$SUB_NUM" --json labels --jq '[.labels[].name] | contains(["deploy"])')
  if [ "$IS_DEPLOY" = "true" ]; then
    CLOSING_DIRECTIVE="Closes #${SUB_NUM}\nCloses #${EPIC_NUMBER}"
  else
    CLOSING_DIRECTIVE="Closes #${SUB_NUM}"
  fi

  # Create PR if not already open
  PR_NUM=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
  if [ -z "$PR_NUM" ]; then
    PR_URL=$(gh pr create --title "feat(#${SUB_NUM}): ..." --body "$CLOSING_DIRECTIVE" --base main --head "$BRANCH")
    PR_NUM=$(basename "$PR_URL")
  fi

  # Step 7: Autonomous Reviewer Agent Gate & Three-Tier Risk Merge Policy
  # A. Dispatch reviewer agent (review-pr)
  REVIEW_OUTPUT=$(python3 scripts/review_pr.py --pr "$PR_NUM" --issue "$SUB_NUM" --json)
  REVIEW_VERDICT=$(echo "$REVIEW_OUTPUT" | jq -r '.verdict')
  IS_HALTED=$(echo "$REVIEW_OUTPUT" | jq -r '.halted')

  if [ "$IS_HALTED" = "true" ] || [ "$REVIEW_VERDICT" != "APPROVE" ]; then
    echo "Reviewer agent requested changes or halted after 3 rounds on PR #$PR_NUM. Stopping for César."
    exit 2
  fi

  # B. Check risk classification (classify_pr_risk.py)
  RISK_TIER=$(python3 scripts/classify_pr_risk.py --base origin/main --head HEAD --label)
  if [ "$RISK_TIER" = "high-risk" ]; then
    echo "PR #$PR_NUM is high-risk. Halting for César in thread final message."
    exit 0
  fi

  # C. Auto-merge on green CI + reviewer approval
  # Wait for required status check 'ci' to turn green
  gh pr merge "$PR_NUM" --squash
  # NOTE: NEVER pass --delete-branch. Branches are always preserved.

  # Step 8: Log run outcome with review metrics (scripts/run_log.py)
  if [ -f "scripts/run_log.py" ]; then
    python3 scripts/run_log.py record --issue "$SUB_NUM" --pr "$PR_NUM" --result merged
  fi

  # Step 9: Remove in-progress label
  gh issue edit "$SUB_NUM" --remove-label "in-progress"
done
```

---

## Phase 6: Human Stop-and-Ask Gates

At any point during the `$run-epic` loop, execution **MUST halt immediately** without altering files or retrying blindly under these conditions:

1. **Ambiguity / Open Questions**:
   If an issue's scope, acceptance criteria, or technical constraint is ambiguous.
2. **Model Unavailability**:
   If a configured model from `models.yml` cannot be reached.
3. **Task Card Defect**:
   If Goal, Done when, or Don't touch is incomplete.
4. **Audit Failure After Rework**:
   If a sub-issue fails independent Grok audit after 2 rework passes.
5. **Approval Required Gate (Epic #28)**:
   If a PR is classified as `needs-approval` (touches protected infrastructure or exceeds 50 lines), `$run-epic` **stops and requests César's review**.

### Communication Protocol
- **NEVER post bot comments on GitHub issues or PRs**.
- All questions, pause notices, and approval requests MUST be reported directly in the **thread final message** for César.

---

## Phase 7: Deployment & Final Epic Closure

1. **Deploy Invariant**:
   - Deploy steps execute **ONLY on the final sub-issue** bearing the `deploy` label.
   - Intermediate sub-issues `1` through `N-1` **NEVER trigger deployment**.
2. **Simultaneous Issue Closure**:
   - The final deploy sub-issue PR explicitly states:
     ```markdown
     Closes #<SUB_ISSUE_NUMBER>
     Closes #<EPIC_NUMBER>
     ```
   - Merging this final PR automatically closes both the final sub-issue and the parent epic simultaneously on GitHub.
   - Agents never close issues manually via `gh issue close`.

---

## Phase 8: Idempotency & Resumability

`$run-epic` is designed to be safely interrupted and re-run at any time (`$run-epic #N`):

- **Merged Slices**: Skipped without repeated runs.
- **Open PRs**: Identified and reconnected to without creating duplicate PRs.
- **Existing Worktrees / Branches**: Fetched and rebased cleanly off `origin/main`.
- **Existing Sub-Issues**: Reused without re-running `plan-epic`.
- **Duplicate Prevention**: No duplicate sub-issues or PRs are ever generated.

---

## Dry-Run Walkthrough: Sample 3-Issue Epic

To illustrate the exact flow on a representative initiative (Epic `#100` with 3 sub-issues):

```
Initiative Epic #100: "Add Payment Gateway"
├── Sub-issue #101: feat(payment): data schema and Stripe SDK integration (agent, feature)
├── Sub-issue #102: feat(payment): checkout endpoint and webhook handler (agent, feature)
└── Sub-issue #103: feat(payment): UI payment modal and billing receipt (agent, feature, deploy)
```

1. **Run 1 (`$run-epic #100`)**:
   - Inspects `#100`; discovers `#101`, `#102`, `#103` (or plans them).
   - Starts `#101`: checks out `feat/101-slice`, runs TDD, passes `verify-app`, passes Grok audit.
   - Opens PR `#104` (`Closes #101`). CI turns green. Squash merges.
   - Continues to `#102`: checks out `feat/102-slice`, implements, passes tests & audit. Opens PR `#105` (`Closes #102`).
   - *Interruption occurs (e.g. process restart or human stops)*.
2. **Run 2 (Resumed `$run-epic #100`)**:
   - Discovers existing sub-issues `#101`, `#102`, `#103`.
   - Checks `#101`: closed/merged → skips.
   - Checks `#102`: open PR `#105` found! Reattaches, verifies green CI, squash merges PR `#105`. `#102` closes.
   - Moves to final sub-issue `#103` (`deploy`):
     - Implements modal UI, verifies tests and Grok audit.
     - Opens PR `#106` with body:
       ```markdown
       Closes #103
       Closes #100
       ```
     - CI turns green, audit passes. Squash merges PR `#106`.
     - Executes deploy check (detected `deploy` label on `#103`).
     - GitHub automatically closes `#103` and Epic `#100`.
     - `$run-epic` completes successfully.
