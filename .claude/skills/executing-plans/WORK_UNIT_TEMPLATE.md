# Work Unit Template

Each agent receives instructions in this format:

```markdown
## Work Unit: [Unit Name]

**Plan File**: docs/plans/[PLAN_FILE].md
**Section**: [Section in plan for this unit]
**Dependencies**: [List of prerequisite PRs, if any]

**Your Mission**:
1. Read plan section for this work unit
2. Read MEMORY.md for current project state
3. Create worktree: `git worktree add ../Bid-Euchre-<branch> <branch>`
4. Implement changes per plan
5. Follow all CLAUDE.md conventions
6. Run `make check` until passing
7. Create PR with plan reference
8. Update MEMORY.md with completion status

**Exit Criteria**:
- All changes implemented
- `make check` passing
- PR created
- MEMORY.md updated
```

## Dependency Coordination

```
Plan:
  Unit A: Add models.py (independent)
  Unit B: Add features.py (independent)
  Unit C: Wire models in experiments.py (depends on A)

Execution:
  [Parallel] Launch A + B
  [Wait] For A to complete
  [Serial] Launch C
```
