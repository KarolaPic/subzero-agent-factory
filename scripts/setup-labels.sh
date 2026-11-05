#!/usr/bin/env bash
# Idempotent script to create/update the Grok Bot Agent Factory labels in GitHub.
# Also prints instructions for configuring the `agent` label in Linear.

set -euo pipefail

REPO_ARG=()
if [ "${1:-}" != "" ]; then
  REPO_ARG=(--repo "$1")
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "❌ Error: GitHub CLI ('gh') is not installed. Install it from https://cli.github.com/"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "❌ Error: 'gh' is not authenticated. Run 'gh auth login' first."
  exit 1
fi

echo "🏷️  Syncing GitHub repository labels..."

create_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  gh label create "$name" --color "$color" --description "$description" --force ${REPO_ARG[@]+"${REPO_ARG[@]}"}
  echo "  ✓ $name (#$color)"
}

create_label "agent"             "0E8A16" "Trigger: issue is picked up by the autonomous agent factory (Grok Bot)"
create_label "epic"              "B60205" "Planning only: split into agent sub-issues"
create_label "deploy"            "006B75" "Final sub-issue of an epic; triggers deploy after green merge"
create_label "waiting-for-human" "FBCA04" "Blocked on questions awaiting human response via Grok Bot"
create_label "in-progress"       "1D76DB" "Currently being planned, built, or verified by an agent worktree"
create_label "rework"            "D93F0B" "Escalated to Gemini 3.8 Flash High for rework after verification/interrogation failure"
create_label "ready-to-merge"    "5319E7" "Green CI + independent verification & Grok 4.7 interrogation passed"
create_label "feature"           "A2EEEF" "New user-facing feature or enhancement"
create_label "bug"               "D73A4A" "Bug report or regression fix"
create_label "low-risk"          "0E8A16" "PR risk: docs-only, tests-only, or small fix under 50 lines; auto-merge eligible"
create_label "needs-approval"    "FBCA04" "PR risk: high-risk paths, dependencies, workflows, models, or large diff; requires César approval"

echo ""
echo "✅ GitHub labels configured."
echo "ℹ️  Linear setup note:"
echo "   In Linear (Workspace Settings > Labels), create a label named 'agent' (exact lowercase)."
echo "   Only Linear or GitHub issues tagged with 'agent' are ingested by the factory."
