---
name: fixing-bugs
description: Parallelizes independent bug fixes across worktree agents for cascading test failures. Use when multiple test failures need resolution or when sequential debugging is too slow.
disable-model-invocation: true
---

# Parallel Test-Driven Bug Resolution

Execute parallel bug fixes for cascading test failures using isolated worktree agents.

## Workflow

### Phase 1: Identify Failures
1. Run `make check` to capture all failures
2. Categorize failures by type and module
3. Identify independent failure categories (can be fixed in parallel)

### Phase 2: Spawn Parallel Agents
For each independent failure category:
1. **Create isolated worktree**: `git worktree add ../Bid-Euchre-bugfix-X <new-branch>`
2. **Spawn sub-task agent** — see [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) for instructions format
3. **Track progress** with TaskCreate/TaskUpdate

### Phase 3: Converge Fixes
1. Collect all agent diffs
2. Create unified fix branch
3. Apply all diffs — see [CONVERGENCE.md](CONVERGENCE.md) for strategy
4. Run full `make check` to verify no interactions
5. Resolve any interactions between fixes
6. Create single PR with all fixes

### Phase 4: Cleanup
1. Remove all temporary worktrees
2. Delete temporary branches
3. Update MEMORY.md with PR number

## Parallel Execution Strategy

- **Independent fixes**: Spawn agents in parallel (max 4-5 agents)
- **Dependent fixes**: Serialize (e.g., if test B depends on fix A)
- **Shared code conflicts**: Detected in Phase 3 convergence

## Anti-Patterns to Avoid

- Fixing issues sequentially (misses parallelization opportunity)
- Over-engineering fixes (keep them minimal)
- Skipping full suite verification after convergence
- Leaving temporary worktrees behind
- Creating multiple PRs instead of one unified fix

## Notes

- Best used when multiple independent failures exist
- Maximum 4-5 parallel agents recommended
- Each agent operates autonomously
- Final PR is atomic (all fixes or none)
