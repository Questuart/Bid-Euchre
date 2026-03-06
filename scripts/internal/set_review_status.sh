#!/bin/bash
# Publish a GitHub commit status for a review gate.
#
# Usage: set_review_status.sh <state> <description> [target_url] [context]
#   state:       pending | success | failure | error
#   description: short text (max 140 chars)
#   target_url:  optional link to review details (pass "" to skip)
#   context:     status context name (default: "reviewing-changes")
#                Use "codex-plan-review" for plan review status
#
# Examples:
#   set_review_status.sh pending "Review in progress"
#   set_review_status.sh success "Review passed — 0 blockers, 3 warnings"
#   set_review_status.sh failure "Review blocked — 2 blockers found"
#   set_review_status.sh success "Plan approved by Codex" "" "codex-plan-review"
#   set_review_status.sh success "Manual override"
set -euo pipefail

STATE="$1"
DESCRIPTION="$2"
TARGET_URL="${3:-}"
CONTEXT="${4:-reviewing-changes}"
SHA=$(git rev-parse HEAD)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Validate state
case "$STATE" in
  pending|success|failure|error) ;;
  *) echo "Error: state must be one of: pending, success, failure, error" >&2; exit 1 ;;
esac

# Truncate description to GitHub's 140-char limit
DESCRIPTION="${DESCRIPTION:0:140}"

# Build the API call
ARGS=(
  "repos/${REPO}/statuses/${SHA}"
  -f "state=$STATE"
  -f "description=$DESCRIPTION"
  -f "context=$CONTEXT"
)

if [ -n "$TARGET_URL" ]; then
  ARGS+=(-f "target_url=$TARGET_URL")
fi

gh api "${ARGS[@]}"

echo "Set status: context=$CONTEXT state=$STATE sha=${SHA:0:7}"
