#!/bin/bash
# Session start hook to warn about main checkout
# Runs at session start to provide early guidance

set -euo pipefail

CURRENT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
MAIN_DIR="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"

if [ "$CURRENT_DIR" = "$MAIN_DIR" ] && [ "$CURRENT_BRANCH" = "main" ]; then
  # Print warning (not blocking, just informational)
  cat << 'EOF'
⚠️  SESSION NOTICE: You're in main checkout on main branch.

   All code changes will be blocked by the UserPromptSubmit hook.
   If you want to make changes, you'll need to switch to a worktree.

   The hook will auto-create a worktree when blocked, or you can
   create one manually now:

     git worktree add ../Bid-Euchre-<branch-name> <branch-name>
     cd ../Bid-Euchre-<branch-name>

EOF

  # Provide additional context to Claude via JSON
  # Note: This may not work with all Claude Code versions, but doesn't hurt
  echo '{"additionalContext": "IMPORTANT: User is in main checkout on main branch. All code changes will be blocked by UserPromptSubmit hook. If they want to make changes, suggest creating a worktree first using the auto-created branch or a custom branch name."}'
fi

exit 0  # Never block session start
