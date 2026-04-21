#!/usr/bin/env bash
# permission_denied_alert.sh — escalate auto-mode classifier denials to ops.
#
# Companion to .claude/hooks/permission-denied-log.sh. The log hook provides
# historical JSONL for observation; this hook converts a live denial into an
# operator-visible escalation so unattended fleet lanes do not silently stall
# on Sonnet 4.6 classifier blocks.
#
# Context: PR #2675 switched fleet defaultMode from bypassPermissions to
# "auto" (classifier-gated). When the classifier blocks a tool call it emits
# a PermissionDenied event. The Claude Code UI shows a "Recently denied" tab
# with a manual retry key, but that UX assumes an operator is watching —
# useless for the autonomous fleet overnight.
#
# Behavior:
#   1. Reads JSON denial payload from stdin (best-effort parse).
#   2. Derives lane id from $CLAUDE_AGENT_NAME or $CLAUDE_PROJECT_DIR
#      (falls back to hostname — never crashes).
#   3. Sends an escalation message to the ops lane via ops.py message send
#      (best-effort; swallowed if ops.py is unavailable).
#   4. Appends a JSONL record to
#      .claude/runtime/classifier_denials/YYYY-MM-DD.jsonl with fields:
#      {ts, lane, tool, rule, message}. This schema is a contract with
#      future observation tooling — treat changes as breaking.
#
# Safety:
#   - Always exits 0. Hook must never block the lane.
#   - All subshells and writes are wrapped in `|| true`.
#   - Message body is truncated to 200 chars to avoid oversized messages.
#
# Refs: #2249 (self-modification gating), #2238 (review-lane permission stalls)
set -u  # -e deliberately omitted so partial failures never block the lane

MAX_MESSAGE_LEN=200

# ---------------------------------------------------------------------------
# Step 1 — parse stdin defensively
# ---------------------------------------------------------------------------
INPUT=$(cat 2>/dev/null || echo "")

# Extract fields, tolerating missing keys, malformed JSON, and empty input.
# Accept multiple schema variants:
#   - task packet spec: {tool_name, rule_matched, message}
#   - observed Claude Code payload: {tool_name, reason, tool_input, session_id}
TOOL_NAME="unknown"
RULE="unknown"
MESSAGE=""
if [ -n "$INPUT" ]; then
  TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
  RULE=$(printf '%s' "$INPUT" | jq -r '.rule_matched // .reason // "unknown"' 2>/dev/null || echo "unknown")
  MESSAGE=$(printf '%s' "$INPUT" | jq -r '.message // .reason // ""' 2>/dev/null || echo "")
fi

# Normalize "null" → "unknown"/"" and guard against jq printing literal null
[ "$TOOL_NAME" = "null" ] && TOOL_NAME="unknown"
[ "$RULE" = "null" ] && RULE="unknown"
[ "$MESSAGE" = "null" ] && MESSAGE=""

# Truncate message body to MAX_MESSAGE_LEN chars
if [ ${#MESSAGE} -gt $MAX_MESSAGE_LEN ]; then
  MESSAGE="${MESSAGE:0:$MAX_MESSAGE_LEN}..."
fi

# ---------------------------------------------------------------------------
# Step 2 — derive lane id
# ---------------------------------------------------------------------------
LANE=""
if [ -n "${CLAUDE_AGENT_NAME:-}" ]; then
  LANE=$(printf '%s' "$CLAUDE_AGENT_NAME" | sed 's/^steward-//')
elif [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR" 2>/dev/null || echo "")
  case "$DIR_NAME" in
    *steward-author-scratch) LANE="author-scratch" ;;
    *steward-author-b)       LANE="author-b" ;;
    *steward-author-c)       LANE="author-c" ;;
    *steward-author-d)       LANE="author-d" ;;
    *steward-author)         LANE="author-a" ;;
    *steward-brws-author-a)  LANE="brws-author-a" ;;
    *steward-brws-author-b)  LANE="brws-author-b" ;;
    *steward-brws-author-c)  LANE="brws-author-c" ;;
    *steward-brws-author-d)  LANE="brws-author-d" ;;
    *steward-analyst-b)      LANE="analyst-b" ;;
    *steward-analyst-c)      LANE="analyst-c" ;;
    *steward-analyst-d)      LANE="analyst-d" ;;
    *steward-analyst)        LANE="analyst-a" ;;
    *steward-flex-a)         LANE="flex-a" ;;
    *steward-flex-b)         LANE="flex-b" ;;
    *steward-flex-c)         LANE="flex-c" ;;
    *steward-flex-d)         LANE="flex-d" ;;
    *steward-review)         LANE="review" ;;
    *steward-ops)            LANE="ops" ;;
    Bid-Euchre)              LANE="main" ;;
    *)                       LANE=$(printf '%s' "$DIR_NAME" | sed 's/^Bid-Euchre-steward-//' | sed 's/^Bid-Euchre/main/') ;;
  esac
fi
# Final fallback: hostname. Never let LANE be empty.
if [ -z "$LANE" ]; then
  LANE=$(hostname 2>/dev/null || echo "unknown")
fi

# ---------------------------------------------------------------------------
# Step 3 — append JSONL record to dated denials log
# ---------------------------------------------------------------------------
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "unknown")
DATE_STAMP=$(date -u +"%Y-%m-%d" 2>/dev/null || echo "unknown-date")

LOG_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/runtime/classifier_denials"
LOG_FILE="$LOG_DIR/${DATE_STAMP}.jsonl"
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Build record with jq for proper JSON encoding; fall back to hand-rolled JSON
# if jq is missing or fails.
RECORD=$(jq -nc \
  --arg ts "$TIMESTAMP" \
  --arg lane "$LANE" \
  --arg tool "$TOOL_NAME" \
  --arg rule "$RULE" \
  --arg message "$MESSAGE" \
  '{ts: $ts, lane: $lane, tool: $tool, rule: $rule, message: $message}' \
  2>/dev/null) || RECORD=""

if [ -z "$RECORD" ]; then
  # Hand-rolled fallback. Escapes per RFC 8259 §7:
  #   - `\` → `\\`, `"` → `\"`
  #   - named short escapes for \b \t \n \f \r
  #   - remaining C0 control chars (U+0000–U+001F) → \uXXXX
  # Uses awk (not sed) because sed cannot process embedded newlines in a
  # single invocation without non-portable GNU-only extensions, and a single
  # unescaped newline in the message would corrupt every subsequent line in
  # the JSONL file (see #2691).
  _esc() {
    printf '%s' "$1" | LC_ALL=C awk '
      BEGIN {
        for (i = 1; i < 256; i++) ord[sprintf("%c", i)] = i
      }
      { buf = (NR == 1 ? $0 : buf "\n" $0) }
      END {
        n = length(buf)
        for (i = 1; i <= n; i++) {
          c = substr(buf, i, 1)
          v = ord[c] + 0
          if (c == "\\")            printf "\\\\"
          else if (c == "\"")       printf "\\\""
          else if (v == 8)          printf "\\b"
          else if (v == 9)          printf "\\t"
          else if (v == 10)         printf "\\n"
          else if (v == 12)         printf "\\f"
          else if (v == 13)         printf "\\r"
          else if (v > 0 && v < 32) printf "\\u%04x", v
          else                      printf "%s", c
        }
      }
    '
  }
  RECORD=$(printf '{"ts":"%s","lane":"%s","tool":"%s","rule":"%s","message":"%s"}' \
    "$(_esc "$TIMESTAMP")" \
    "$(_esc "$LANE")" \
    "$(_esc "$TOOL_NAME")" \
    "$(_esc "$RULE")" \
    "$(_esc "$MESSAGE")")
fi

printf '%s\n' "$RECORD" >> "$LOG_FILE" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Step 4 — send ops escalation (best-effort)
# ---------------------------------------------------------------------------
# Use --no-nudge by default to avoid racing with the lane that just emitted
# the denial; ops receives via inbox poll within its normal monitoring cycle.
SUMMARY="Classifier denial: ${TOOL_NAME} blocked by ${RULE}"
if [ ${#SUMMARY} -gt 250 ]; then
  SUMMARY="${SUMMARY:0:250}..."
fi

if command -v uv >/dev/null 2>&1; then
  (
    cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
    uv run python scripts/internal/ops.py message send \
      --from "$LANE" \
      --to ops \
      --type escalation \
      --summary "$SUMMARY" \
      --priority high \
      --no-nudge \
      >/dev/null 2>&1
  ) || true
fi

# Return hook response and always exit 0.
printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "PermissionDenied", "retry": false}}'
exit 0
