# CONTEXT.md

Canonical glossary and domain model for `subzero-agent-factory` (Codename: **Subzero**). Implementation details, scratchpads, and execution specs belong elsewhere.

---

### Destination
The end-state of this initiative: an **Automated Self-Improvement Outer Loop** that inspects past agent execution traces, isolates recurring friction and quality failures, and proposes reviewed pull requests to evolve skills (`.agents/skills/`) and agent operating rules (`AGENTS.md`).

---

### Core Glossary

#### Inner Factory Loop
The operational task-execution cycle that ingests an `agent`-labeled issue, plans, builds test-first, verifies runtime behavior, interrogates with an independent auditor, and squash-merges to `main`.

#### Self-Improvement Outer Loop
The asynchronous evaluative cycle operating outside the inner factory loop that reviews completed work-items, scores session transcripts against quality rubrics, accumulates lessons, and synthesizes improvements to the factory's skill library.

#### Lesson
An atomic record of a friction point, rework cause, tool-call failure, or rubric violation extracted from an inner factory loop execution trace.

#### Memory Store
The durable repository (located in `.factory/memory/`) consisting of an append-only JSONL log (`lessons.jsonl`) and a computed pattern index (`patterns.json`).

#### Pattern Index
The indexed grouping of active lessons mapped by composite key `<failureClass>::<targetSkill>`, tracking repetition counts and threshold readiness.

#### Dedicated Memory Lockfile
The persistent lockfile (`.factory/memory/.memory.lock`) acquired via POSIX `fcntl.flock(LOCK_EX)` across all concurrent git worktrees (`git rev-parse --git-common-dir`), preventing inode-replacement race conditions during atomic file updates.

#### Composite Pattern Key
The canonical identifier format `<failureClass>::<targetSkill>` used to group atomic lessons into actionable patterns.

#### Graduated Pattern
A recurring failure pattern that has met or exceeded the repetition threshold, been synthesized into an improvement pull request by the Routine Maker, and marked resolved upon merge.

#### Repetition Threshold
The minimum number of independent occurrences of a categorized failure class (default: 3) required before the factory graduates lessons into an actionable modification.

#### Routine Maker (Skill Improver)
The meta-agent in the outer loop that analyzes repeated lessons once the repetition threshold is breached and drafts a focused pull request targeting the relevant skill or operating rule. Powered by the configured `planner` model (`gemini-3.8-flash-high`).

#### Evaluator
The meta-agent in the outer loop that inspects completed work-item runs and extracts structured lessons against the quality rubrics. Powered by the configured independent `auditor` model (`grok-4.7`).

#### Dual-Tier Evaluation Surface
The ingestion contract for the evaluator: primarily ingesting repo-native artifacts (`.factory/work-items/<id>.json`, git diffs, CI results, Grok audit logs in `artifacts/`), with optional support for deep harness session transcripts (`transcript.jsonl`) when available.

#### Quality Rubrics
The standardized scoring criteria applied to completed runs:
1. **Rework Frequency**: Escalation attempts during Phase 4a (runtime verification) or Phase 4b (Grok audit).
2. **Diff Economy**: Focus and conciseness of the diff relative to the ticket scope (absence of unwanted churn or scope creep).
3. **Test Seam Integrity**: Meaningful behavior verification without redundant tests or excessive mock isolation.
4. **Execution Efficiency**: Absence of looping tool-calls or repetitive shell failures (scored when deep transcripts are provided).

#### Receipt of Causality
A mandatory, structured section within any self-improvement PR linking the proposed skill or prompt change directly to the accumulated lessons, work-item IDs, and failure rubrics that necessitated the modification.

#### HITL Delivery Gate
The strict safety boundary dictating that while ordinary feature and bugfix PRs can auto-merge upon passing CI and independent Grok audit, all self-evolution pull requests modifying `.agents/skills/` or `AGENTS.md` require human review and explicit manual merge.
