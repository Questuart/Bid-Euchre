#!/bin/bash
# Enhanced worktree guard hook for UserPromptSubmit
# Blocks edits on main, creates a worktree the first time, reuses on repeat.
#
# Fix for #943: session-level dedup prevents unbounded worktree creation
# when /loop or repeated prompts fire the hook from a main-checkout session.

set -euo pipefail

CURRENT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
MAIN_DIR="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"

# Only block if in main checkout on main branch
if [ "$CURRENT_DIR" = "$MAIN_DIR" ] && [ "$CURRENT_BRANCH" = "main" ]; then

  # --- Session dedup: reuse existing ephemeral worktree ---
  # Scan for any work-* worktree that already exists. If found, point to it
  # instead of creating yet another one. This prevents unbounded growth from
  # /loop or repeated prompts.
  EXISTING_WT=""
  while IFS= read -r wt_path; do
    wt_name=$(basename "$wt_path")
    if [[ "$wt_name" == Bid-Euchre-work-* ]]; then
      # Verify the directory actually exists on disk
      if [ -d "$wt_path" ]; then
        EXISTING_WT="$wt_path"
        break
      fi
    fi
  done < <(git worktree list --porcelain 2>/dev/null | grep "^worktree " | sed 's/^worktree //')

  if [ -n "$EXISTING_WT" ]; then
    echo "⛔ Cannot work from main checkout."
    echo ""
    echo "   Existing worktree available: $EXISTING_WT"
    echo ""
    echo "   cd $EXISTING_WT"
    echo ""
    echo "Then restart your Claude session in that directory."
    exit 1
  fi

  # --- First invocation: create a new worktree ---
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
