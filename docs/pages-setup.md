# GitHub Pages Factory Dashboard Deployment Guide

This guide describes how the static operational dashboard for **Subzero Agent Factory** (Codename: **Subzero**) is deployed and maintained on **GitHub Pages**.

---

## 1. Overview

The factory dashboard is a pure static single-page application (`plain HTML/CSS/JS`, zero build server or package dependencies) hosted in the `/docs` directory on the `main` branch:

- **Source Location**: `docs/index.html` and `docs/metrics.js`
- **Data Source**: `.factory/runs/runs.jsonl`
- **Hosted URL**: `https://cesarchavezcal.github.io/subzero-agent-factory/`

---

## 2. GitHub Pages Setup (Repository Settings)

> [!IMPORTANT]
> **César does this by hand in repo settings.**  
> Due to GitHub security permissions for GitHub Apps and PAT scopes, GitHub Pages activation cannot be automated via agent tokens. César enables and configures GitHub Pages manually in the repository settings.

### Step-by-Step Manual Activation

1. Navigate to the repository settings:
   `https://github.com/cesarchavezcal/subzero-agent-factory/settings/pages`
2. Under **Build and deployment**:
   - **Source**: Select `Deploy from a branch`
   - **Branch**: Select `main`
   - **Folder**: Select `/docs` (default root `/` must be changed to `/docs`)
3. Click **Save**.
4. GitHub Pages will build and deploy within 1–2 minutes at:
   `https://cesarchavezcal.github.io/subzero-agent-factory/`

---

## 3. Metrics Displayed

The dashboard computes and renders the following core factory metrics:

1. **PRs Opened & Merged**: Count of PRs opened by agents, successfully merged to `main`, and the merge completion rate.
2. **Kickoff → PR Opened**: Average latency in seconds/minutes from run kickoff to initial PR opening.
3. **PR → First Review**: Average duration from PR creation to first adversarial Grok audit or review.
4. **Review → Merge**: Average duration from passing review to squash merge.
5. **Human Interventions**: Total interventions recorded across runs, and the average intervention rate per PR.
6. **Recent Runs Table**: Chronological table of agent runs with status badges (`merged`, `blocked`, `failed`), builder/auditor models, and PR scores.

---

## 4. Empty Log Handling & Offline Resilience

- If `.factory/runs/runs.jsonl` does not exist yet or contains zero records, the dashboard displays zeroed summary stats and a clear empty state card without throwing JavaScript runtime errors.
- If served locally (via `file://` where browser CORS prevents `fetch()`), the dashboard displays instructions and an inline file picker / raw text paste input so developers can load a log file locally without running a local web server.

---

## 5. Security & Privacy Invariants

- **No Secrets**: No API keys, personal access tokens, or private environment variables are included in `docs/` or `.factory/runs/runs.jsonl`.
- **Public Visibility**: The page only displays public run metadata (issue numbers, PR numbers, public model identifiers, and durations).
