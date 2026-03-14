#!/bin/bash
# PostToolUse hook — advisory anti-pattern detection for Python files.
#
# Runs after Edit/Write on *.py files. Checks for known anti-patterns:
#   C1: Unseeded random.Random() or global random.* usage
#   C2: Falsy numeric guard (x = x or fallback)
#   X3: Leftover debug/cleanup markers (breakpoint, TODO-remove)
#   Import boundary: src/ files importing from experiments/ or tests/
#
# Always exits 0 (advisory only, never blocks).
set -uo pipefail

INPUT=$(cat)

# Extract file path from hook JSON
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Only check Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Only check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

findings=()

# C1: Unseeded random.Random() — constructor with no arguments
if grep -nP 'random\.Random\(\s*\)' "$FILE_PATH" >/dev/null 2>&1; then
    findings+=("C1: random.Random() without seed argument")
fi

# C1: Global random usage — random.choice/randint/shuffle/sample
if grep -nP '(?<!\.)random\.(choice|randint|shuffle|sample)\(' "$FILE_PATH" >/dev/null 2>&1; then
    # Exclude import lines and comments
    if grep -nP '^[^#]*(?<!\.)random\.(choice|randint|shuffle|sample)\(' "$FILE_PATH" >/dev/null 2>&1; then
        findings+=("C1: Global random.choice/randint/shuffle/sample usage (use local Random instance)")
    fi
fi

# C2: Falsy numeric guard — pattern like `x = x or default` or `val = val or 0`
# This catches the dangerous pattern where 0.0 is falsy
if grep -nP '^\s*\w+\s*=\s*\w+\s+or\s+' "$FILE_PATH" >/dev/null 2>&1; then
    findings+=("C2: Possible falsy numeric guard (x = x or fallback) — 0.0 is falsy in Python")
fi

# X3: Leftover debug/cleanup markers
if grep -nPi 'breakpoint\(\)' "$FILE_PATH" >/dev/null 2>&1; then
    findings+=("X3: breakpoint() call found")
fi
if grep -nPi 'TODO:\s*remove|TODO-remove' "$FILE_PATH" >/dev/null 2>&1; then
    findings+=("X3: TODO-remove marker found")
fi

# Import boundary: src/ files must not import from experiments/ or tests/
if [[ "$FILE_PATH" == */src/* ]]; then
    if grep -nP '^\s*(from|import)\s+(experiments|tests)[\.\s]' "$FILE_PATH" >/dev/null 2>&1; then
        findings+=("IMPORT-BOUNDARY: src/ file imports from experiments/ or tests/ (violates import boundary)")
    fi
fi

# Report findings if any
if [ ${#findings[@]} -gt 0 ]; then
    # Build warning message
    warning="Anti-pattern check on $(basename "$FILE_PATH"):"
    for f in "${findings[@]}"; do
        warning="$warning\n  - $f"
    done

    # Escape for JSON
    json_warning=$(echo -e "$warning" | jq -Rs .)

    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": $json_warning
  }
}
EOF
fi

exit 0
