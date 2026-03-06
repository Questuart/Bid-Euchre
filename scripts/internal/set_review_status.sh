#!/bin/bash
# Publish a GitHub commit status for a review gate.
#
# Usage: set_review_status.sh <state> <description> [target_url] [context] [sha]
#   state:       pending | success | failure | error
#   description: short text (max 140 chars)
#   target_url:  optional link to review details (pass "" to skip)
#   context:     status context name (default: "reviewing-changes")
#                Use "codex-plan-review" for plan review status
#   sha:         commit SHA to attach status to (default: git rev-parse HEAD)
#                Override with REVIEW_STATUS_SHA env var or positional arg.
#                In GitHub Actions pull_request workflows, pass the PR head SHA
#                (e.g., ${{ github.event.pull_request.head.sha }}) since HEAD
#                may be the synthetic merge commit, not the PR head.
#
# Examples:
#   # Local (Claude session) — HEAD is the PR branch tip
#   set_review_status.sh pending "Review in progress"
#   set_review_status.sh success "Review passed — 0 blockers, 3 warnings"
#   set_review_status.sh failure "Review blocked — 2 blockers found"
#   set_review_status.sh success "Manual override"
#
#   # GitHub Actions — pass explicit PR head SHA
#   set_review_status.sh success "Plan approved" "" "codex-plan-review" "$PR_HEAD_SHA"
#
#   # Or via environment variable
#   REVIEW_STATUS_SHA="$PR_HEAD_SHA" set_review_status.sh pending "Review starting"
set -euo pipefail

STATE="$1"
DESCRIPTION="$2"
TARGET_URL="${3:-}"
CONTEXT="${4:-reviewing-changes}"
SHA="${5:-${REVIEW_STATUS_SHA:-$(git rev-parse HEAD)}}"
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
