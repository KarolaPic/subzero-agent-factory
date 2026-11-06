# Changelog

All notable changes to the Grok Bot Agent Factory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Install Impeccable UI/UX skill and automate changelog updates on PR merge in $orchestrate ([#122](https://github.com/cesarchavezcal/grok-bot-agent-factory/issues/122), [#123](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/123)).
- Adopted [Conventional Branch](https://conventionalbranch.org/) specification (`scripts/validate_conventions.py`), establishing `<type>/<issue>-<description>` branch naming alongside Conventional Commits and standardized PR titles ([#94](https://github.com/cesarchavezcal/grok-bot-agent-factory/issues/94)).
- Added test suite `tests/test_conventional_branch.py` verifying branch prefixes, character rules, commit formatting, and PR titles.
- Enforced branch and PR title validation in `.github/workflows/ci.yml`.
- Free text request intake for `$run-epic` (`scripts/find_or_create_issue.py`), enabling execution from natural language prompts with automated matching, task card generation, and duplicate prevention via hidden idempotency markers ([#89](https://github.com/cesarchavezcal/grok-bot-agent-factory/issues/89)).
- Unit test suite `tests/test_find_or_create_issue.py` verifying matching precedence, unclear request rejection, task card validation, and duplicate avoidance.
- Updated `.agents/skills/run-epic/SKILL.md`, `AGENTS.md`, and `docs/setup.md` with documented dry-run walkthroughs and intake rules.

## [2026-11-05] — Factory Overhaul & Autonomous Governance

### Added

#### Task Card Ingestion & Validation
- Added structured YAML task card template (`.github/ISSUE_TEMPLATE/task-card.yml`) enforcing mandatory `Goal`, `Done when`, and `Don't touch` fields ([#37](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/37)).
- Enforced task card validation across `AGENTS.md` and autonomous agent skills ([#44](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/44)).

#### Run Log System & Audit Trail
- Defined run log JSON schema (`.factory/schemas/run.schema.json`) with `.gitattributes` union merge strategy for parallel branch safe appending ([#47](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/47)).
- Implemented concurrency-safe append helper `scripts/run_log.py` using `fcntl.flock` on `.factory/runs/.runs.lock` ([#47](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/47)).
- Wired run log recording into agent lifecycle and documented in `AGENTS.md` ([#49](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/49)).
- Expanded run log schema to record autonomous PR review outcomes, review rounds, and reviewer models ([#79](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/79)).

#### Three-Tier Risk Merge Policy & PR Classifier
- Built diff risk classifier script `scripts/classify_pr_risk.py` with unit tests evaluating lines changed and protected paths ([#48](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/48)).
- Added CI workflow `.github/workflows/risk-classifier.yml` for automatic `low-risk`, `normal`, and `high-risk` labeling ([#50](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/50)).
- Documented merge rules and branch protection setup in `docs/merge-policy.md` ([#52](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/52)).
- Refined high-risk classification criteria and test coverage for security and infrastructure protection ([#77](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/77)).

#### Autonomous Epic Runner
- Created `$run-epic` orchestrator skill (`.agents/skills/run-epic/SKILL.md`) to run entire initiatives sequentially without Grok Bot ([#51](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/51)).
- Integrated manual routing in `AGENTS.md`, `docs/setup.md`, and CI verification ([#53](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/53)).

#### PR Template Standardization
- Enforced concise 4-section PR template (`## Why`, `## What changed`, `## How it was tested`, `Closes #N`) in `.github/PULL_REQUEST_TEMPLATE.md` ([#54](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/54)).
- Strictly prohibited `Refs #` directives across PR templates and agent skills to ensure automatic issue closing upon merge ([#55](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/55)).

#### T3 PR Scorer
- Added `scorer` model role (`gemini-3.8-flash-low`) to `models.yml` and `models.allowed.yml` with setup script validation ([#62](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/62)).
- Implemented zero-paid-API-key PR diff scoring module `scripts/score_pr.py` integrating score rationale into PR bodies and run logs ([#75](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/75)).
- Added CI workflow `.github/workflows/verify-run-log.yml` to validate run log formatting on pull requests ([#85](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/85)).

#### Factory Analytics Dashboard
- Created run log parser and metric calculation engine in `scripts/generate_dashboard.py` calculating throughput, failure rates, intervention frequencies, and average scores ([#63](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/63)).
- Deployed responsive static HTML/JS dashboard at `docs/index.html` with GitHub Pages setup instructions ([#73](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/73)).

#### Autonomous PR Reviewer Agent
- Created `review-pr` skill and automated review submission script `scripts/submit_review.py` supporting autonomous `APPROVE` or `REQUEST_CHANGES` verdicts ([#78](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/78)).
- Integrated autonomous review gates into `implement-ticket`, `fix-bug`, and `run-epic` execution loops ([#80](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/80)).
- Documented branch ruleset and GitHub App configuration in `docs/reviewer-setup.md` ([#81](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/81)).

#### Design, Motion & Animation Skills Integration
- Pinned and normalized upstream skill permissions in `skills-lock.json` ([#74](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/74)).
- Documented UI/UX, motion, and animation skills across lifecycle phases in `AGENTS.md` ([#76](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/76)).
- Mandated `break-ui` and visual parity checks in Phase 4a runtime verification playbooks ([#82](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/82)).
- Configured Grok auditor instructions for restraint and animation audits in Phase 4b ([#84](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/84)).
