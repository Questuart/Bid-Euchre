#!/bin/bash
# Helper script to create worktree and start Claude session
# Usage: ./claude-worktree.sh [branch-name]
#        If no branch name provided, generates one from timestamp

set -euo pipefail

MAIN_DIR="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"
BRANCH_NAME="${1:-work-$(date +%Y%m%d-%H%M%S)}"
WORKTREE_DIR="../Bid-Euchre-$BRANCH_NAME"

# Must run from main checkout
CURRENT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ "$CURRENT_DIR" != "$MAIN_DIR" ]; then
  echo "Error: Must run from $MAIN_DIR"
  echo "Current location: $CURRENT_DIR"
  exit 1
fi

echo "Creating worktree for branch: $BRANCH_NAME"

# Create branch if it doesn't exist
if git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
  echo "Branch $BRANCH_NAME already exists, using it"
else
  echo "Creating new branch: $BRANCH_NAME"
  git branch "$BRANCH_NAME"
fi

# Create worktree
echo "Creating worktree at: $WORKTREE_DIR"
git worktree add "$WORKTREE_DIR" "$BRANCH_NAME"

# Move to worktree
cd "$WORKTREE_DIR"

echo ""
echo "✅ Worktree ready at: $(pwd)"
echo ""
echo "Starting Claude session..."
echo ""

# Start Claude session in the worktree
exec claude
