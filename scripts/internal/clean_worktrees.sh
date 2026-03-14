#!/bin/bash
# clean_worktrees.sh — Remove worktrees and branches whose remote is [gone].
#
# Usage:
#   scripts/internal/clean_worktrees.sh            # execute cleanup
#   scripts/internal/clean_worktrees.sh --dry-run   # preview only
#   scripts/internal/clean_worktrees.sh --help       # show help
#
# Workflow:
#   1. git fetch --prune  (sync remote tracking state)
#   2. Find local branches marked [gone] (remote deleted)
#   3. Remove associated worktrees, then delete branches
set -euo pipefail

DRY_RUN=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Remove git worktrees and local branches whose upstream remote has been deleted
(marked [gone] by git).

Options:
  --dry-run   List what would be removed without making changes
  --help      Show this help message

Examples:
  $(basename "$0")            # Clean up stale worktrees and branches
  $(basename "$0") --dry-run  # Preview what would be removed
EOF
}

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$arg'" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# Step 1: Sync remote tracking state
echo "Fetching and pruning remote tracking branches..."
if [ "$DRY_RUN" = false ]; then
    git fetch --prune 2>/dev/null || true
else
    echo "  (dry-run: skipping git fetch --prune)"
fi

# Step 2: Find branches marked [gone]
# git branch -v marks branches whose upstream is deleted with [gone]
gone_branches=()
while IFS= read -r line; do
    # Strip leading whitespace and +/* prefix characters (worktree/current markers)
    branch=$(echo "$line" | sed 's/^[[:space:]]*[+*]*[[:space:]]*//' | awk '{print $1}')
    if [ -n "$branch" ]; then
        gone_branches+=("$branch")
    fi
done < <(git branch -v 2>/dev/null | grep '\[gone\]' || true)

if [ ${#gone_branches[@]} -eq 0 ]; then
    echo "No [gone] branches found. Nothing to clean up."
    exit 0
fi

echo "Found ${#gone_branches[@]} [gone] branch(es): ${gone_branches[*]}"
echo ""

worktrees_removed=0
branches_deleted=0

# Build worktree list once for efficiency
worktree_list=$(git worktree list 2>/dev/null || true)

for branch in "${gone_branches[@]}"; do
    # Step 3a: Check if a worktree exists for this branch
    # git worktree list output format: /path/to/worktree  <sha> [branch-name]
    worktree_path=""
    while IFS= read -r wt_line; do
        if echo "$wt_line" | grep -q "\\[${branch}\\]"; then
            worktree_path=$(echo "$wt_line" | awk '{print $1}')
            break
        fi
    done <<< "$worktree_list"

    if [ -n "$worktree_path" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [dry-run] Would remove worktree: $worktree_path (branch: $branch)"
        else
            echo "  Removing worktree: $worktree_path (branch: $branch)"
            if git worktree remove --force "$worktree_path" 2>/dev/null; then
                worktrees_removed=$((worktrees_removed + 1))
            else
                echo "    WARNING: Failed to remove worktree $worktree_path" >&2
            fi
        fi
    fi

    # Step 3b: Delete the branch
    if [ "$DRY_RUN" = true ]; then
        echo "  [dry-run] Would delete branch: $branch"
    else
        echo "  Deleting branch: $branch"
        if git branch -D "$branch" 2>/dev/null; then
            branches_deleted=$((branches_deleted + 1))
        else
            echo "    WARNING: Failed to delete branch $branch" >&2
        fi
    fi
done

echo ""
if [ "$DRY_RUN" = true ]; then
    echo "Dry run complete. ${#gone_branches[@]} branch(es) would be processed."
else
    echo "Cleanup complete: $worktrees_removed worktree(s) removed, $branches_deleted branch(es) deleted."
fi
