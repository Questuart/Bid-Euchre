#!/bin/bash
# Enhanced worktree guard hook for UserPromptSubmit
# Automatically creates worktree when blocked, provides copy-paste cd command

set -euo pipefail

CURRENT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
MAIN_DIR="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"

# Only block if in main checkout on main branch
if [ "$CURRENT_DIR" = "$MAIN_DIR" ] && [ "$CURRENT_BRANCH" = "main" ]; then
  # Generate branch name from timestamp
  BRANCH_NAME="work-$(date +%Y%m%d-%H%M%S)"
  WORKTREE_DIR="../Bid-Euchre-$BRANCH_NAME"

  echo "🔧 Auto-creating worktree for you..."
  echo ""

  # Create branch and worktree
  if git branch "$BRANCH_NAME" 2>/dev/null && git worktree add "$WORKTREE_DIR" "$BRANCH_NAME" 2>/dev/null; then
    echo "✅ Worktree created successfully!"
    echo "   Branch: $BRANCH_NAME"
    echo "   Location: $WORKTREE_DIR"
    echo ""
    echo "⛔ Cannot work from main checkout. Please run:"
    echo ""
    echo "   cd $WORKTREE_DIR"
    echo ""
    echo "Then restart your Claude session in that directory."
  else
    echo "⚠️  Failed to create worktree automatically."
    echo "   Please create it manually:"
    echo ""
    echo "   git worktree add $WORKTREE_DIR $BRANCH_NAME"
    echo "   cd $WORKTREE_DIR"
  fi

  echo ""
  exit 1  # Block the prompt submission
fi

exit 0  # Allow prompt submission
