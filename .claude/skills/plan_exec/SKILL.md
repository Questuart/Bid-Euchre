# Plan Exec - Autonomous Plan-to-Implementation Pipeline

Execute implementation plans end-to-end with autonomous sub-agent orchestration and dependency coordination.

## Purpose

Your plan-then-implement workflow currently requires two sessions:
1. Session 1: Create detailed plan → save to file
2. Session 2: Read plan → implement → often hits context limits

This skill bridges the gap: read a finalized plan, decompose into work units, spawn autonomous agents for each unit, coordinate dependencies, and deliver complete PRs without context loss.

## Workflow

### Phase 1: Plan Decomposition
1. **Read plan file**: `docs/plans/[PLAN_FILE].md`
2. **Read MEMORY.md**: Current project state and context
3. **Decompose into work units**:
   - Each unit = 1 focused PR
   - Identify dependencies between units
   - Size each unit for single-session completion (~30-45 min)

### Phase 2: Dependency Graph
Build execution order:
- **Independent units**: Can run in parallel
- **Dependent units**: Must wait for prerequisite PRs
- **Example**: If B depends on A, A→B; if C is independent, run A+C in parallel

### Phase 3: Execute Work Units
For each work unit (respecting dependencies):

1. **Spawn sub-task agent** with focused mission:
   - Read plan file section for this unit
   - Read MEMORY.md for current state
   - Create git worktree: `git worktree add ../Bid-Euchre-<branch> <branch>`

2. **Agent implements changes**:
   - Follow all conventions in CLAUDE.md
   - Make only the changes specified in the plan
   - Write tests if specified

3. **Agent validates**:
   - Run `make check`
   - Fix any failures
   - Iterate until passing

4. **Agent creates PR**:
   - Use PR template
   - Reference plan file in description
   - Include repro commands if applicable

5. **Agent updates MEMORY.md**:
   - PR number and status
   - Any discoveries or deviations from plan
   - Blockers or follow-ups

### Phase 4: Coordination
- **After each unit completes**: Report progress to user
- **Before starting dependent unit**: Verify prerequisite PR exists
- **If unit fails**: Diagnose, attempt fix, continue if possible
- **Track progress**: TodoWrite for real-time status

### Phase 5: Final Summary
After all units complete:
- List all PRs created
- Note any plan deviations
- Update MEMORY.md with full status
- Suggest next steps if any

## Usage

```bash
/plan_exec docs/plans/bidding_refactor.md
```

Example prompts:
- "Execute the plan at docs/plans/arc_d_implementation.md autonomously"
- "Read docs/plans/phase1_models.md and implement all work units in order"
- "Implement the 6-unit plan at docs/plans/data_pipeline.md, respecting dependencies"

## Work Unit Template

Each agent receives:

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

### Parallel Execution
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

### Progress Tracking

Real-time TodoWrite updates:

```markdown
## Plan Execution: bidding_refactor.md

### Work Units Identified (6)
- [completed] Unit 1: Add ModeloEspecifico bidder class
- [completed] Unit 2: Add OLSa training pipeline
- [in_progress] Unit 3: Wire bidder in config.py
- [pending] Unit 4: Add integration tests (depends on 1,3)
- [pending] Unit 5: Add experiment configs
- [pending] Unit 6: Update documentation

### PRs Created
- PR #330: Add ModeloEspecifico bidder class
- PR #331: Add OLSa training pipeline
- (PR #332 in progress)

### Discoveries
- Unit 2 revealed missing dependency on scikit-learn (fixed)
- Unit 3 required minor schema adjustment (documented in PR)
```

## Anti-Patterns to Avoid

❌ Asking for confirmation between units
❌ Implementing units out of dependency order
❌ Skipping `make check` to save time
❌ Creating mega-PRs instead of focused units
❌ Ignoring plan deviations (document them!)

## Benefits

- ✅ Single session from plan to PRs (no context fragmentation)
- ✅ Automatic dependency coordination
- ✅ Parallel execution where possible
- ✅ Full quality gates on every unit
- ✅ Real-time progress visibility
- ✅ MEMORY.md always current

## Error Handling

If a work unit fails:
1. **Capture error details**
2. **Attempt automatic fix** (read error, fix code, retry)
3. **If still failing**: Report to user, continue with independent units
4. **Mark unit as blocked** in TodoWrite
5. **Update MEMORY.md** with blocker details

## Recovery from Blockers

If Unit C depends on blocked Unit A:
- Mark C as "blocked waiting for A"
- Continue with independent units
- Report blocking chain to user
- Suggest manual intervention for A

## Context Preservation

Unlike two-session workflow:
- ✅ Plan details never lost (agents read plan file)
- ✅ Project state always current (agents read MEMORY.md)
- ✅ No manual context reload needed
- ✅ Continuous execution (no session boundaries)

## Output Format

Progress updates after each unit:

```markdown
✅ Unit 1 Complete: Add ModeloEspecifico bidder class
   - PR #330 created and merged
   - Tests: 752 passing
   - MEMORY.md updated

⚙️  Unit 2 In Progress: Add OLSa training pipeline
   - Worktree created
   - Implementation phase...

⏸️  Unit 3 Waiting: Wire bidder in config.py
   - Dependency: Unit 1 (✅ complete)
   - Ready to start after Unit 2

---

Progress: 1/6 units complete, 1 in progress, 4 pending
Total PRs created: 1
Estimated time remaining: ~90 minutes
```

## Integration with Other Skills

Perfect combo workflow:
1. `/plan_init` - Create plan with verified APIs
2. User reviews and approves plan
3. `/plan_exec` - Autonomous implementation
4. (Agents use `/ship` internally for each PR)
5. `/memory_ref` - Verify final state

## Notes

- Plan file must exist at `docs/plans/[PLAN_FILE].md`
- Each work unit should be PR-sized (not too large)
- Dependencies should be explicit in the plan
- Agents operate with full autonomy (no confirmation prompts)
- Best for 3-6 unit plans (larger plans → use `/pr_chunk`)
- Requires worktree-based workflow
- Pairs with your existing hook system
