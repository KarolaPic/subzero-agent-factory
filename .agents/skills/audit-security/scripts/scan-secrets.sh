#!/usr/bin/env bash
# Scans git diff or specified path for exposed secrets and forbidden environment keys.
# NEVER prints raw secret values in output. Safe and non-destructive.
# Usage:
#   scan-secrets.sh [--diff-base <git-ref>] [path]

set -euo pipefail

DIFF_BASE=""
TARGET_PATH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --diff-base)
      DIFF_BASE="${2:-origin/main}"
      shift 2
      ;;
    *)
      TARGET_PATH="$1"
      shift
      ;;
  esac
done

FINDINGS=0

check_pattern() {
  local pattern="$1"
  local description="$2"
  local content="$3"
  local case_insensitive="${4:-0}"

  local matches
  if [ "$case_insensitive" -eq 1 ]; then
    matches=$(echo "$content" | grep -i -n -E -e "$pattern" || true)
  else
    matches=$(echo "$content" | grep -n -E -e "$pattern" || true)
  fi
  if [ -n "$matches" ]; then
    while IFS= read -r line; do
      local line_num
      line_num=$(echo "$line" | cut -d: -f1)
      local file_name
      file_name=$(echo "$line" | cut -d: -f2- | awk '{print $1}')
      echo "  ❌ [SECRET-DETECTED] $description at line $line_num (value redacted: [REDACTED_SECRET])"
      FINDINGS=$((FINDINGS + 1))
    done <<< "$matches"
  fi
}

echo "🔍 Running secret scanning check..."

CONTENT=""
if [ -n "$DIFF_BASE" ]; then
  if git rev-parse --verify "$DIFF_BASE" >/dev/null 2>&1; then
    echo "  ℹ️  Inspecting git diff against $DIFF_BASE"
    CONTENT=$(git diff "$DIFF_BASE" -- || true)
  else
    echo "  ℹ️  $DIFF_BASE not found, inspecting HEAD~1"
    CONTENT=$(git diff HEAD~1 -- 2>/dev/null || git diff HEAD -- || true)
  fi
elif [ -n "$TARGET_PATH" ] && [ -d "$TARGET_PATH" ]; then
  echo "  ℹ️  Inspecting directory: $TARGET_PATH"
  CONTENT=$(grep -rnE ".*" "$TARGET_PATH" 2>/dev/null || true)
else
  echo "  ℹ️  Inspecting uncommitted working tree diff"
  CONTENT=$(git diff HEAD -- || true)
fi

if [ -z "$CONTENT" ]; then
  echo "  ✓ No diff content to scan."
  exit 0
fi

# 1. AWS Access Key ID
check_pattern 'AKIA[0-9A-Z]{16}' "AWS Access Key ID" "$CONTENT"

# 2. GitHub Personal Access Token / Fine-grained Token
check_pattern 'gh[pousr]_[A-Za-z0-9_]{36,}' "GitHub Personal Access Token" "$CONTENT"
check_pattern 'github_pat_[A-Za-z0-9_]{22,}' "GitHub Fine-Grained Token" "$CONTENT"

# 3. Private Keys
check_pattern '-----BEGIN[ A-Z0-9_-]*PRIVATE KEY-----' "Cryptographic Private Key Block" "$CONTENT"

# 4. Prohibited Factory API Keys assigned to static strings
check_pattern '(GEMINI_API_KEY|XAI_API_KEY|CURSOR_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_-]{16,}["'"'"']' "Prohibited Paid API Key Assignment" "$CONTENT" 0

# 5. Generic API Keys / Tokens with hardcoded strings
check_pattern '(api[_-]?key|auth[_-]?token|secret[_-]?key)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_-]{24,}["'"'"']' "Hardcoded High-Entropy Secret/Key Assignment" "$CONTENT" 1

if [ "$FINDINGS" -gt 0 ]; then
  echo ""
  echo "❌ Secret scan FAILED: $FINDINGS potential secret exposure(s) detected!"
  echo "   Remediation: Remove raw credentials immediately, rotate exposed keys, and use environment variables."
  exit 1
fi

echo "✓ Secret scan passed cleanly. Zero exposed secrets detected."
exit 0
