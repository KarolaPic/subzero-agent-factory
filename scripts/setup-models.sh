#!/usr/bin/env bash
# `setup-models.sh` — Model configuration setup script for Grok Bot Agent Factory.
# Prompts for builder and auditor models (must differ), defaulting planner, epic_planner,
# and subagents to builder unless explicitly changed. Writes to models.yml at repo root.
#
# Usage:
#   ./scripts/setup-models.sh                     # Interactive or uses defaults if non-interactive
#   ./scripts/setup-models.sh --defaults          # Writes default models without prompting
#   ./scripts/setup-models.sh --builder <model> --auditor <model> [--planner <m>] [--epic-planner <m>] [--subagents <m>]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ALLOWED_FILE="$ROOT_DIR/models.allowed.yml"
MODELS_FILE="$ROOT_DIR/models.yml"

if [ ! -f "$ALLOWED_FILE" ]; then
  echo "Error: Allowed models file not found at $ALLOWED_FILE" >&2
  exit 1
fi

# Load allowed models into bash array using python3
ALLOWED_MODELS=()
while IFS='' read -r line; do
  [ -n "$line" ] && ALLOWED_MODELS+=("$line")
done < <(python3 -c "
import yaml
with open('$ALLOWED_FILE') as f:
    data = yaml.safe_load(f)
models = data.get('models', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
for m in models:
    if m:
        print(str(m).strip())
")

if [ "${#ALLOWED_MODELS[@]}" -eq 0 ]; then
  echo "Error: No allowed models defined in $ALLOWED_FILE" >&2
  exit 1
fi

is_allowed() {
  local target="$1"
  for m in "${ALLOWED_MODELS[@]}"; do
    if [ "$m" = "$target" ]; then
      return 0
    fi
  done
  return 1
}

# Template defaults per Decision 9
TEMPLATE_DEFAULT_BUILDER="gemini-3.8-flash-high"
TEMPLATE_DEFAULT_AUDITOR="grok-4.7"
TEMPLATE_DEFAULT_SUBAGENTS="cursor-small"
TEMPLATE_DEFAULT_SCORER="gemini-3.8-flash-low"

DEFAULT_BUILDER="$TEMPLATE_DEFAULT_BUILDER"
DEFAULT_AUDITOR="$TEMPLATE_DEFAULT_AUDITOR"
DEFAULT_SUBAGENTS="$TEMPLATE_DEFAULT_SUBAGENTS"
DEFAULT_SCORER="$TEMPLATE_DEFAULT_SCORER"
CURRENT_PLANNER=""
CURRENT_EPIC_PLANNER=""
CURRENT_SUBAGENTS=""
CURRENT_SCORER=""

# If models.yml already exists, read existing values for defaults
if [ -f "$MODELS_FILE" ]; then
  CURRENT_BUILDER="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('builder', ''))" 2>/dev/null || echo "")"
  CURRENT_AUDITOR="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('auditor', ''))" 2>/dev/null || echo "")"
  CURRENT_PLANNER="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('planner', ''))" 2>/dev/null || echo "")"
  CURRENT_EPIC_PLANNER="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('epic_planner', ''))" 2>/dev/null || echo "")"
  CURRENT_SUBAGENTS="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('subagents', ''))" 2>/dev/null || echo "")"
  CURRENT_SCORER="$(python3 -c "import yaml; print(yaml.safe_load(open('$MODELS_FILE')).get('scorer', ''))" 2>/dev/null || echo "")"
  [ -n "$CURRENT_BUILDER" ] && DEFAULT_BUILDER="$CURRENT_BUILDER"
  [ -n "$CURRENT_AUDITOR" ] && DEFAULT_AUDITOR="$CURRENT_AUDITOR"
  [ -n "$CURRENT_SUBAGENTS" ] && DEFAULT_SUBAGENTS="$CURRENT_SUBAGENTS"
  [ -n "$CURRENT_SCORER" ] && DEFAULT_SCORER="$CURRENT_SCORER"
fi

CHOSEN_BUILDER=""
CHOSEN_AUDITOR=""
CHOSEN_PLANNER=""
CHOSEN_EPIC_PLANNER=""
CHOSEN_SUBAGENTS=""
CHOSEN_SCORER=""
USE_DEFAULTS=0

# Parse command-line arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --defaults)
      USE_DEFAULTS=1
      shift
      ;;
    --builder)
      CHOSEN_BUILDER="${2:-}"
      shift 2
      ;;
    --auditor)
      CHOSEN_AUDITOR="${2:-}"
      shift 2
      ;;
    --planner)
      CHOSEN_PLANNER="${2:-}"
      shift 2
      ;;
    --epic-planner|--epic_planner)
      CHOSEN_EPIC_PLANNER="${2:-}"
      shift 2
      ;;
    --subagents)
      CHOSEN_SUBAGENTS="${2:-}"
      shift 2
      ;;
    --scorer)
      CHOSEN_SCORER="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./scripts/setup-models.sh [options]"
      echo ""
      echo "Options:"
      echo "  --defaults                   Apply template defaults (builder: gemini-3.8-flash-high, auditor: grok-4.7, subagents: cursor-small, scorer: gemini-3.8-flash-low)"
      echo "  --builder <model>            Builder model"
      echo "  --auditor <model>            Auditor model (must differ from builder)"
      echo "  --planner <model>            Planner model (defaults to builder)"
      echo "  --epic-planner <model>       Epic planner model (defaults to builder)"
      echo "  --subagents <model>          Sub-agents model (defaults to cursor-small)"
      echo "  --scorer <model>             Scorer model (defaults to gemini-3.8-flash-low)"
      echo "  -h, --help                   Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$USE_DEFAULTS" -eq 1 ]; then
  CHOSEN_BUILDER="$TEMPLATE_DEFAULT_BUILDER"
  CHOSEN_AUDITOR="$TEMPLATE_DEFAULT_AUDITOR"
  CHOSEN_PLANNER="$CHOSEN_BUILDER"
  CHOSEN_EPIC_PLANNER="$CHOSEN_BUILDER"
  CHOSEN_SUBAGENTS="$TEMPLATE_DEFAULT_SUBAGENTS"
  CHOSEN_SCORER="$TEMPLATE_DEFAULT_SCORER"
fi

# Interactive selection helper: all output to stderr except chosen model string
select_model() {
  local prompt_label="$1"
  local current_default="$2"
  local exclude_model="${3:-}"
  local chosen=""

  while true; do
    echo "" >&2
    echo "Select $prompt_label model:" >&2
    local i=1
    for m in "${ALLOWED_MODELS[@]}"; do
      local note=""
      if [ "$m" = "$current_default" ]; then
        note=" (current/default)"
      fi
      if [ -n "$exclude_model" ] && [ "$m" = "$exclude_model" ]; then
        note=" (disallowed: matches builder)"
      fi
      echo "  [$i] $m$note" >&2
      i=$((i + 1))
    done

    printf "Enter choice [1-%d] or model name (default: %s): " "${#ALLOWED_MODELS[@]}" "$current_default" >&2
    local input=""
    read -r input || input=""
    input="$(echo "$input" | xargs)"

    if [ -z "$input" ]; then
      chosen="$current_default"
    elif [[ "$input" =~ ^[0-9]+$ ]] && [ "$input" -ge 1 ] && [ "$input" -le "${#ALLOWED_MODELS[@]}" ]; then
      local idx=$((input - 1))
      chosen="${ALLOWED_MODELS[$idx]}"
    elif is_allowed "$input"; then
      chosen="$input"
    else
      echo "❌ Invalid choice: '$input'. Please choose from the allowed list." >&2
      continue
    fi

    if [ -n "$exclude_model" ] && [ "$chosen" = "$exclude_model" ]; then
      echo "❌ Auditor cannot be the same as builder ($chosen). Auditor must differ from builder." >&2
      continue
    fi

    echo "$chosen"
    return 0
  done
}

# Interactive prompts when on TTY or stdin is available and builder/auditor not provided via flags
if [ -z "$CHOSEN_BUILDER" ] || [ -z "$CHOSEN_AUDITOR" ]; then
  if [ -t 0 ] || [ -p /dev/stdin ] || [ ! -t 0 ]; then
    # If stdin has input available
    if [ "$USE_DEFAULTS" -eq 0 ] && [ -t 0 ]; then
      echo "============================================================" >&2
      echo "🤖 Grok Bot Agent Factory — Model Setup" >&2
      echo "============================================================" >&2
      [ -z "$CHOSEN_BUILDER" ] && CHOSEN_BUILDER="$(select_model "BUILDER" "$DEFAULT_BUILDER")"
      [ -z "$CHOSEN_AUDITOR" ] && CHOSEN_AUDITOR="$(select_model "AUDITOR" "$DEFAULT_AUDITOR" "$CHOSEN_BUILDER")"

      # Prompt for secondary roles or default to builder
      printf "\nUse '%s' for planner, epic_planner, and subagents? [Y/n]: " "$CHOSEN_BUILDER" >&2
      read -r USE_BUILDER_FOR_ALL || USE_BUILDER_FOR_ALL=""
      if [[ "$USE_BUILDER_FOR_ALL" =~ ^[Nn]$ ]]; then
        [ -z "$CHOSEN_PLANNER" ] && CHOSEN_PLANNER="$(select_model "PLANNER" "$CHOSEN_BUILDER")"
        [ -z "$CHOSEN_EPIC_PLANNER" ] && CHOSEN_EPIC_PLANNER="$(select_model "EPIC_PLANNER" "$CHOSEN_BUILDER")"
        [ -z "$CHOSEN_SUBAGENTS" ] && CHOSEN_SUBAGENTS="$(select_model "SUBAGENTS" "$CHOSEN_BUILDER")"
      fi
    else
      [ -z "$CHOSEN_BUILDER" ] && CHOSEN_BUILDER="$DEFAULT_BUILDER"
      [ -z "$CHOSEN_AUDITOR" ] && CHOSEN_AUDITOR="$DEFAULT_AUDITOR"
    fi
  else
    [ -z "$CHOSEN_BUILDER" ] && CHOSEN_BUILDER="$DEFAULT_BUILDER"
    [ -z "$CHOSEN_AUDITOR" ] && CHOSEN_AUDITOR="$DEFAULT_AUDITOR"
  fi
fi

# Validate builder and auditor
if ! is_allowed "$CHOSEN_BUILDER"; then
  echo "Error: Builder model '$CHOSEN_BUILDER' is not in allowed models list." >&2
  exit 1
fi

if ! is_allowed "$CHOSEN_AUDITOR"; then
  echo "Error: Auditor model '$CHOSEN_AUDITOR' is not in allowed models list." >&2
  exit 1
fi

if [ "$CHOSEN_BUILDER" = "$CHOSEN_AUDITOR" ]; then
  echo "Error: Auditor model ('$CHOSEN_AUDITOR') must differ from builder model ('$CHOSEN_BUILDER')." >&2
  exit 1
fi

# Planner, epic_planner, and subagents default to builder unless set
if [ -z "$CHOSEN_PLANNER" ]; then
  CHOSEN_PLANNER="$CHOSEN_BUILDER"
fi
if [ -z "$CHOSEN_EPIC_PLANNER" ]; then
  CHOSEN_EPIC_PLANNER="$CHOSEN_BUILDER"
fi
if [ -z "$CHOSEN_SUBAGENTS" ]; then
  CHOSEN_SUBAGENTS="$DEFAULT_SUBAGENTS"
fi
if [ -z "$CHOSEN_SCORER" ]; then
  CHOSEN_SCORER="$DEFAULT_SCORER"
fi

for role_pair in "planner:$CHOSEN_PLANNER" "epic_planner:$CHOSEN_EPIC_PLANNER" "subagents:$CHOSEN_SUBAGENTS" "scorer:$CHOSEN_SCORER"; do
  r="${role_pair%%:*}"
  m="${role_pair##*:}"
  if ! is_allowed "$m"; then
    echo "Error: Role '$r' model '$m' is not in allowed models list." >&2
    exit 1
  fi
done

# Write models.yml
cat > "$MODELS_FILE" <<EOF
# Model configuration for Grok Bot Agent Factory
# Run ./scripts/setup-models.sh to change these models.
builder: $CHOSEN_BUILDER
auditor: $CHOSEN_AUDITOR
planner: $CHOSEN_PLANNER
epic_planner: $CHOSEN_EPIC_PLANNER
subagents: $CHOSEN_SUBAGENTS
scorer: $CHOSEN_SCORER
EOF

# Validate written configuration
python3 "$ROOT_DIR/scripts/validate_models.py"

echo "✓ Successfully configured models in models.yml"
