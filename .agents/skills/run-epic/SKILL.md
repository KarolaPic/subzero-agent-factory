---
name: run-epic
description: Autonomous orchestrator skill that executes an entire epic initiative end-to-end, decomposing into sub-issues (or reusing existing ones) and driving sequential implementation, verification, audit, PR merges, and final deployment.
---

# Run Epic Orchestrator (`run-epic`)

Autonomous orchestrator skill that drives an entire initiative-level epic from a single command: `$run-epic #N` or `$run-epic <plain text request>`. It handles automated issue discovery / creation (matching open issues or creating a task card with duplicate prevention), automated decomposition (or reuses existing sub-issues), sequential ticket implementation, independent verification and audit gates, PR squash merging, and final deployment without requiring human babysitting or an active Grok Bot dispatcher.

---

## Workflow Overview

```
$run-epic <#N | plain text request>
     │
     ▼
[Phase 1: Epic Intake, Discovery & Issue Resolution]
  ├─ If explicit issue (#N, issue N): Use issue #N directly
  ├─ If free text request: Run find-or-create step (scripts/find_or_create_issue.py):
  │    ├─ Check if unclear / ambiguous ──► STOP & ask César in thread final message
  │    ├─ Search open issues (hidden marker, exact title, keyword score):
  │    │    ├─ One clear match ──► Reuse discovered issue #N
  │    │    ├─ Multiple candidate matches ──► STOP & ask César in thread final message
  │    │    └─ No match ──► Create new issue with task card & hidden marker, label 'agent'
  │    └─ Verify task card fields (Goal, Done when, Don't touch) before build starts
  ├─ Query existing sub-issues: gh issue list --search "Part of #N"
  ├─ If sub-issues exist ──► Reuse discovered sub-issues in dependency order
  └─ If none exist ───────► If epic, invoke plan-epic #N to decompose; else execute ticket directly
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
  │      ├─ Records evaluation in PR body and run log (up to 3 rounds)
  │      └─ If unapproved after 3 rounds ──► HALT & report to César
  ├─ 5. Three-Tier Risk Merge Gate:
  │      ├─ Required status check 'ci' MUST be green
  │      ├─ low-risk ──► auto squash merge
  │      ├─ normal ──► auto squash merge on green CI + reviewer agent APPROVE recorded in PR body
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

## Phase 1: Epic Intake, Discovery & Find-or-Create Resolution

### 1. Dual Command Invocations
`$run-epic` accepts both an explicit issue number and a plain text request:
- **Explicit Issue Input**: `$run-epic #<EPIC_NUMBER>`, `$run-epic <EPIC_NUMBER>`, or `$run-epic issue <EPIC_NUMBER>`.
- **Plain Text Request**: `$run-epic <free text request>` (for example, `$run-epic add a dark mode toggle` or `$run-epic export telemetry logs to s3`).

### 2. Find-or-Create Issue Resolution (`scripts/find_or_create_issue.py`)
When invoked with free text, `$run-epic` executes `python3 scripts/find_or_create_issue.py --query "<request>" --json` to resolve or create the issue before starting the execution loop:

```bash
INTAKE_JSON=$(python3 scripts/find_or_create_issue.py --query "$USER_INPUT" --json)
STATUS=$(echo "$INTAKE_JSON" | jq -r '.status')
```

#### A. Input Classification & Explicit Issue Resolution
If the input starts with `#`, `issue `, or is a pure integer:
- Resolves immediately to the target issue number `#N` without querying search.
- Existing `$run-epic #N` behavior remains 100% backward-compatible and unchanged.

#### B. Search & Matching Precedence
For free text requests, open issues are queried (`gh issue list --state open`) and evaluated in order of strict precedence:
1. **Exact Hidden Idempotency Marker (Highest Priority)**:
   - Every issue created by `$run-epic` embeds a hidden HTML comment marker in its body:
     ```html
     <!-- run-epic-request: <normalized_request> -->
     ```
   - If an open issue contains this exact marker matching the normalized query, it is chosen immediately.
   - **Guarantees zero duplicate issues** when re-running the same request.
2. **Exact Title Match**:
   - Matches if normalized issue title equals normalized request (ignoring conventional commit prefixes like `feat:`, `fix:`, `docs:`, etc.).
3. **Keyword Overlap Scoring**:
   - Evaluates tokenized keywords (with English stop words removed).
   - Weighted score: Title keyword matches carry **3x weight** relative to body keyword matches.
   - If all query keywords appear in the issue title, confidence is high ($\ge 90\%$).

#### C. Resolution Outcomes
1. **One Clear Match**:
   - Single candidate with confidence score $\ge 80\%$ and at least $25\%$ lead over the second candidate (or single strong candidate).
   - `$run-epic` automatically attaches to this issue and proceeds to the execution loop.
2. **Multiple Possible Matches**:
   - Multiple candidate issues match with similar scores (no clear winner).
   - **STOP immediately**. Do NOT pick arbitrarily. Present candidate issue numbers and titles to César in the **thread final message** and wait for his instruction.
3. **Unclear Request**:
   - The request is evaluated against the Unclear Request Criteria.
   - If unclear, **STOP immediately**. Write an explanation in the **thread final message** asking César for clarification or an explicit issue number.
4. **No Match Found (Issue Creation)**:
   - When zero issues match, `$run-epic` creates a new issue via `gh issue create`.
   - Title: Formatted with conventional prefix (e.g. `feat: <request>`).
   - Body: Standardized Task Card with mandatory **Goal**, **Done when**, and **Don't touch** sections, plus the hidden idempotency marker `<!-- run-epic-request: <normalized_request> -->`.
   - Labels: Applied with `agent` (and `epic` if initiative decomposition is needed).
   - **Task Card Validation Gate (#26)**: Validates that Goal, Done when, and Don't touch are all present and non-empty. If validation fails, execution stops immediately.

### 3. What Counts as "Unclear"
A request is classified as **unclear** and halted for César if it meets any of the following:
- **Empty or Too Short**: Query is empty or shorter than 3 characters (e.g. `""`, `"hi"`).
- **Stop Words Only**: Query consists entirely of common function words without actionable verbs or nouns (e.g. `"can you please do this for me"`).
- **Single Generic Word**: Query is a single generic word without a target component or subsystem (e.g. `"fix"`, `"update"`, `"bug"`, `"test"`, `"problem"`).
- **Generic Vague Phrase**: Query consists only of generic words without naming an identifiable entity (e.g. `"fix bug"`, `"update tests"`, `"make changes"`).
- **Unfillable Task Card**: The request is so ambiguous that concrete acceptance criteria cannot be formed without making ungrounded assumptions.

### 4. Duplicate Prevention & Idempotency
- When an issue is created for a free text request, its body includes `<!-- run-epic-request: <normalized_request> -->`.
- If the user runs the exact same request again (e.g. `$run-epic add dark mode toggle`), the intake search step finds the existing issue via the hidden marker and re-attaches to it instead of creating a second issue.
- Idempotent and resumable, identical to `$run-epic #N`.

### 5. Inspect Epic Task Card & Sub-Issue Discovery
Once the issue `#EPIC_NUMBER` is resolved or created:
1. Fetch the issue:
   ```bash
   gh issue view "$EPIC_NUMBER" --json title,body,labels,state
   ```
2. Verify task card sections (**Goal**, **Done when**, **Don't touch**).
3. Query existing sub-issues:
   ```bash
   EXISTING_SUB_ISSUES=$(gh issue list --search "Part of #$EPIC_NUMBER in:body" --json number,title,labels,state --limit 50)
   ```
4. **Case A (Sub-issues exist)**: Reuse discovered sub-issues in dependency order.
5. **Case B (No sub-issues exist)**:
   - If issue carries label `epic`, invoke [`plan-epic`](../plan-epic/SKILL.md) on `#EPIC_NUMBER` to decompose into vertical tracer bullets.
   - If issue is a standalone ticket (non-epic), queue the issue itself directly for execution in Phase 4.

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
   - `scorer`: cheap model role (default `gemini-3.8-flash-low`) used by T3 during runs to score PR diffs (1–10 scale) without paid API keys.
2. **Strict Invariants**:
   - **Auditor Must Differ from Builder**: Enforce `auditor != builder`.
   - **Model Availability Check**:
     - Verify that all configured models are present and accessible in the environment.
     - **Model Unavailability Rule**: If any required model (including `scorer`) is unavailable, **STOP IMMEDIATELY**.
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

  # Step 6: PR creation and T3 PR scoring
  # T3 evaluates the PR diff using the configured 'scorer' model (zero paid API keys)
  # If the scorer model is unavailable, stop immediately and report in thread final message
  SCORE_JSON=$(python3 scripts/score_pr.py --base origin/main --head HEAD --json)
  PR_SCORE=$(echo "$SCORE_JSON" | jq -r '.score')
  SCORE_REASON=$(echo "$SCORE_JSON" | jq -r '.reason')
  SCORER_MODEL=$(echo "$SCORE_JSON" | jq -r '.model')

  # Ensure PR body contains correct Closes directive and PR score in ## How it was tested
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

  # Step 8: Log run outcome with review metrics and PR score (scripts/run_log.py)
  if [ -f "scripts/run_log.py" ]; then
    python3 scripts/run_log.py record --issue "$SUB_NUM" --pr "$PR_NUM" --result merged --score "$PR_SCORE"
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

`$run-epic` is designed to be safely interrupted and re-run at any time (`$run-epic #N` or `$run-epic <plain request>`):

- **Merged Slices**: Skipped without repeated runs.
- **Open PRs**: Identified and reconnected to without creating duplicate PRs.
- **Existing Worktrees / Branches**: Fetched and rebased cleanly off `origin/main`.
- **Existing Sub-Issues**: Reused without re-running `plan-epic`.
- **Duplicate Prevention**: Re-running a free text request finds the issue created during previous runs via the embedded marker `<!-- run-epic-request: <normalized_request> -->`. Zero duplicate issues or PRs are ever generated.

---

## Documented Dry-Run Walkthroughs

### Walkthrough 1: Free Text Request with Match Found
**Scenario**: An open issue `#105` ("feat: add a dark mode toggle") already exists in the repository.
1. César runs: `$run-epic add a dark mode toggle`.
2. Intake runs `find_or_create_issue.py --query "add a dark mode toggle" --json`.
3. The matching engine evaluates open issues:
   - Evaluates title tokens `['dark', 'mode', 'toggle']`.
   - Issue `#105` matches all keywords in the title (confidence: 95%).
   - One clear match found: `#105`.
4. `$run-epic` logs: `"Match found: using existing issue #105 ('feat: add a dark mode toggle')"`
5. Proceeds directly to Phase 2 (Anti-Clash) and Phase 4 (Sequential Loop) on `#105`.

### Walkthrough 2: Free Text Request with No Match (Issue Created)
**Scenario**: César wants a new feature not yet tracked in GitHub: `"add customer billing receipt email notification"`.
1. César runs: `$run-epic add customer billing receipt email notification`.
2. Intake runs `find_or_create_issue.py --query "add customer billing receipt email notification" --json`.
3. The matching engine scans open issues; zero issues match.
4. Issue creation:
   - Generates task card with **Goal**, **Done when**, **Don't touch**, and hidden marker:
     ```html
     <!-- run-epic-request: add customer billing receipt email notification -->
     ```
   - Labels with `agent` and `enhancement`.
   - Validates task card sections (passes #26 gate).
   - Creates new issue (e.g. `#110`) via `gh issue create`.
5. `$run-epic` logs: `"Created issue #110 for 'add customer billing receipt email notification'"`
6. Proceeds to execution loop on `#110`.

### Walkthrough 3: Unclear Request or Multiple Matches (Stops for César)
**Scenario A (Unclear Request)**:
1. César runs: `$run-epic fix bug`.
2. Intake evaluates the request: query contains only generic words without target context.
3. `$run-epic` **halts immediately**.
4. Writes alert in the **thread final message**:
   > *"Request 'fix bug' is too vague. Please provide specific component names, symptoms, or an explicit issue number (e.g. `$run-epic #123`)."*

**Scenario B (Multiple Candidate Matches)**:
1. César runs: `$run-epic database connection pool`.
2. Intake searches open issues and finds two close matches:
   - `#120`: `chore: database connection pool timeouts` (score: 90%)
   - `#121`: `fix: database connection pool leak on reconnect` (score: 90%)
3. Neither candidate holds a 25% margin.
4. `$run-epic` **halts immediately**.
5. Reports candidates in the **thread final message**:
   > *"Multiple candidate issues match 'database connection pool':*
   > *- #120: chore: database connection pool timeouts*
   > *- #121: fix: database connection pool leak on reconnect*
   > *Please specify which issue number you want to run."*

### Walkthrough 4: Resumed Execution & Duplicate Avoidance
**Scenario**: César previously ran `$run-epic add customer billing receipt email notification` which created `#110`, but execution was interrupted before PR merge.
1. César re-runs: `$run-epic add customer billing receipt email notification`.
2. Intake searches open issues:
   - Scans issue bodies for `<!-- run-epic-request: add customer billing receipt email notification -->`.
   - Finds exact marker match on issue `#110`!
3. Reattaches to `#110` without creating a duplicate issue.
4. Checks branch/PR state: reconnects to existing branch or PR, finishes testing/audit, and drives to merge.

### Walkthrough 5: Sample 3-Issue Initiative Epic (`$run-epic #100`)
To illustrate the full multi-issue initiative flow:

```
Initiative Epic #100: "Add Payment Gateway"
├── Sub-issue #101: feat(payment): data schema and Stripe SDK integration (agent, feature)
├── Sub-issue #102: feat(payment): checkout endpoint and webhook handler (agent, feature)
└── Sub-issue #103: feat(payment): UI payment modal and billing receipt (agent, feature, deploy)
```

1. **Run 1 (`$run-epic #100`)**:
   - Inspects `#100`; discovers `#101`, `#102`, `#103` (or plans them via `plan-epic`).
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
