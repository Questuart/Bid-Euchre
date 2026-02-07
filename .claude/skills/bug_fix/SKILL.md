# Bug Fix - Parallel Test-Driven Bug Resolution

Execute parallel bug fixes for cascading test failures using isolated worktree agents.

## Purpose

Cascading bug-fix cycles are time-consuming:
- Fix one issue → reveals another → fix that → reveals another...
- Sequential debugging takes hours for 5+ issues
- Each fix requires full context reload

This skill parallelizes independent bug fixes across separate worktree agents, converging on a unified fix branch.

## Workflow

### Phase 1: Identify Failures
1. Run `make check` to capture all failures
2. Categorize failures by type and module:
   - `ZeroDivisionError in module X`
   - `KeyError in module Y`
   - `AssertionError in module Z`
3. Identify independent failure categories (can be fixed in parallel)

### Phase 2: Spawn Parallel Agents
For each independent failure category:
1. **Create isolated worktree**: `git worktree add ../Bid-Euchre-bugfix-X <new-branch>`
2. **Spawn sub-task agent** with focused mission:
   - Read failing test and source code
   - Implement minimal fix
   - Run affected tests only
   - If cascading failure revealed, fix that too
   - Report final diff back
3. **Track progress** with TodoWrite

### Phase 3: Converge Fixes
1. **Collect all agent diffs**
2. **Create unified fix branch**
3. **Apply all diffs** to the unified branch
4. **Run full `make check`** to verify no interactions
5. **Resolve any interactions** between fixes
6. **Create single PR** with all fixes

### Phase 4: Cleanup
1. Remove all temporary worktrees
2. Delete temporary branches
3. Update MEMORY.md with PR number

## Usage

```bash
/bug_fix
```

That's it! The skill handles everything from test execution through PR creation.

Example scenarios:
- "Fix all failing tests in parallel"
- "Debug the cascading notebook failures using parallel agents"
- "Run bug_fix to resolve all test suite failures"

## Agent Instructions Template

Each spawned agent receives:

```markdown
## Bug Fix Agent: [Category]

**Failure**: [error type] in [module]

**Your Mission**:
1. Read the failing test: [test file path]
2. Read relevant source: [source file path]
3. Implement minimal fix (don't over-engineer)
4. Run affected tests: `uv run pytest tests/path/to/test.py::test_name`
5. If fix reveals cascading failure, fix that too
6. Report final diff

**Constraints**:
- Fix only what's broken
- Prefer simple solutions
- Don't refactor unrelated code
- Run tests after each change

**Exit Criteria**:
All affected tests passing, diff reported back.
```

## Parallel Execution Strategy

- **Independent fixes**: Spawn agents in parallel (max 4-5 agents)
- **Dependent fixes**: Serialize (e.g., if test B depends on fix A)
- **Shared code conflicts**: Detected in Phase 3 convergence

## TodoWrite Tracking

Real-time progress tracking:

```markdown
## Bug Fix Pipeline

### Failures Identified (4)
- [pending] ZeroDivisionError in diagnostics/health_checks.py
- [pending] KeyError in notebooks/phase0_bidless/30_outcome_health_checks.py
- [pending] TypeError in reporting/evaluator.py
- [pending] AssertionError in tests/unit/test_splits.py

### Agents Spawned (4)
- [in_progress] Agent 1: ZeroDivisionError fix
- [in_progress] Agent 2: KeyError fix
- [in_progress] Agent 3: TypeError fix
- [in_progress] Agent 4: AssertionError fix

### Fixes Converged
- [pending] Apply all diffs to unified branch
- [pending] Run full test suite
- [pending] Create PR

### Cleanup
- [pending] Remove temporary worktrees
- [pending] Update MEMORY.md
```

## Convergence Strategy

When combining fixes:

1. **Apply diffs in order** (by module, then by line number)
2. **Watch for conflicts**:
   - Same file, different sections: Auto-merge
   - Same file, same section: Manual review
   - Different files: Always safe to combine
3. **Run full suite** to detect interactions
4. **Fix interactions** if detected (rare)

## Anti-Patterns to Avoid

❌ Fixing issues sequentially (misses parallelization opportunity)
❌ Over-engineering fixes (keep them minimal)
❌ Skipping full suite verification after convergence
❌ Leaving temporary worktrees behind
❌ Creating multiple PRs instead of one unified fix

## Benefits

- ✅ 5+ cascading bugs fixed in parallel (minutes vs. hours)
- ✅ Isolated fixes = no context pollution
- ✅ Full test coverage maintained
- ✅ Single coherent PR at the end
- ✅ Automatic cleanup of temp worktrees

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

## Example Session Flow

```markdown
User: /bug_fix

[1/4] Running make check...
❌ 5 failures detected:
   - ZeroDivisionError in health_checks.py
   - KeyError in notebook 30
   - TypeError in evaluator.py
   - AssertionError in test_splits.py
   - AttributeError in train_olsa.py

[2/4] Spawning 5 parallel agents...
✅ Agent 1: Worktree created at ../Bid-Euchre-bugfix-zerodiv
✅ Agent 2: Worktree created at ../Bid-Euchre-bugfix-keyerror
✅ Agent 3: Worktree created at ../Bid-Euchre-bugfix-typeerror
✅ Agent 4: Worktree created at ../Bid-Euchre-bugfix-assertion
✅ Agent 5: Worktree created at ../Bid-Euchre-bugfix-attribute

[3/4] Agents executing...
✅ Agent 1: Fixed ZeroDivisionError (1 cascading fix applied)
✅ Agent 2: Fixed KeyError
⚠️  Agent 3: Revealed cascading TypeError → fixed
✅ Agent 4: Fixed AssertionError
✅ Agent 5: Fixed AttributeError

[4/4] Converging fixes...
✅ All diffs applied to unified branch
✅ Full test suite: PASSED (744 tests)
✅ PR created: #XXX "fix: resolve 5 cascading test failures"
✅ Cleanup complete

Total time: 12 minutes (vs. ~2 hours sequential)
```

## Notes

- Best used when multiple independent failures exist
- Requires worktree-based workflow
- Maximum 4-5 parallel agents recommended
- Each agent operates autonomously
- Final PR is atomic (all fixes or none)
- Pairs well with `/memory_ref` and `/ship`
