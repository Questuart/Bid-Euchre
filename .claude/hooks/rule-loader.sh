#!/usr/bin/env bash
# rule-loader.sh — PreToolUse hook for progressive rule disclosure
# Injects deferred rule files on-demand when relevant paths are touched.
# Always exits 0 (never blocks tool execution).
set -euo pipefail

RULES_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/rules/deferred"
RUNTIME_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/runtime"
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-default}"
SENTINEL_FILE="${RUNTIME_DIR}/.loaded_rules_${SESSION_ID}"

# Read JSON from stdin
INPUT=$(cat)

# Extract tool name
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)

# Extract file path depending on tool
FILE_PATH=""
case "$TOOL_NAME" in
  Edit|Write|Read)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
    ;;
  Bash)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
    ;;
  *)
    # No match — exit with empty response
    echo '{"suppressOutput": true}'
    exit 0
    ;;
esac

if [ -z "$FILE_PATH" ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Determine which rules to load based on path patterns
RULES_TO_LOAD=()

# notebooks/ → rigor + notebook boundary
if echo "$FILE_PATH" | grep -q 'notebooks/'; then
  RULES_TO_LOAD+=("05_rigor.md" "45_notebook_boundary.md")
fi

# docs/04_reports/ → rigor + integrity
if echo "$FILE_PATH" | grep -q 'docs/04_reports/'; then
  RULES_TO_LOAD+=("05_rigor.md" "35_integrity.md")
fi

# core, logging, scoring → data contract
if echo "$FILE_PATH" | grep -qE 'src/bid_euchre/core/|src/bid_euchre/logging/|src/bid_euchre/scoring\.py'; then
  RULES_TO_LOAD+=("30_data_contract.md")
fi

# plans/ → integrity
if echo "$FILE_PATH" | grep -q 'plans/'; then
  RULES_TO_LOAD+=("35_integrity.md")
fi

# review_driver.py → review gate
if echo "$FILE_PATH" | grep -q 'scripts/internal/review_driver.py'; then
  RULES_TO_LOAD+=("60_review_gate.md")
fi

# gh pr commands → PRs + review gate
if echo "$FILE_PATH" | grep -q 'gh pr'; then
  RULES_TO_LOAD+=("40_prs.md" "60_review_gate.md")
fi

# No rules matched
if [ ${#RULES_TO_LOAD[@]} -eq 0 ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Deduplicate
RULES_TO_LOAD=($(printf '%s\n' "${RULES_TO_LOAD[@]}" | sort -u))

# Ensure runtime directory exists
mkdir -p "$RUNTIME_DIR"

# Check sentinel for already-loaded rules
ALREADY_LOADED=""
if [ -f "$SENTINEL_FILE" ]; then
  ALREADY_LOADED=$(cat "$SENTINEL_FILE")
fi

# Filter out already-loaded rules
NEW_RULES=()
for rule in "${RULES_TO_LOAD[@]}"; do
  if ! echo "$ALREADY_LOADED" | grep -qF "$rule"; then
    NEW_RULES+=("$rule")
  fi
done

# Nothing new to load
if [ ${#NEW_RULES[@]} -eq 0 ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Collect rule content
CONTEXT=""
for rule in "${NEW_RULES[@]}"; do
  RULE_FILE="${RULES_DIR}/${rule}"
  if [ -f "$RULE_FILE" ]; then
    CONTEXT="${CONTEXT}$(cat "$RULE_FILE")"$'\n\n'
    # Record as loaded
    echo "$rule" >> "$SENTINEL_FILE"
  fi
done

# Output additionalContext JSON
if [ -n "$CONTEXT" ]; then
  # Use jq to safely encode the content as JSON
  echo "$CONTEXT" | jq -Rs '{additionalContext: ., suppressOutput: true}' 2>/dev/null || echo '{"suppressOutput": true}'
else
  echo '{"suppressOutput": true}'
fi
