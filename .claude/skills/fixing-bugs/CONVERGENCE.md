# Convergence Strategy

When combining fixes from parallel agents:

1. **Apply diffs in order** (by module, then by line number)
2. **Watch for conflicts**:
   - Same file, different sections: Auto-merge
   - Same file, same section: Manual review
   - Different files: Always safe to combine
3. **Run full suite** to detect interactions
4. **Fix interactions** if detected (rare)

## Recovery from Failures

If an agent fails:
- Review agent output
- Manually fix in that worktree
- Continue with other agents
- Converge fixes at the end

If convergence fails:
- Identify conflicting fixes
- Resolve manually in unified branch
- Re-run full suite
