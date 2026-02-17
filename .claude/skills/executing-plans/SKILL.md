---
name: executing-plans
description: Reads a finalized plan file, decomposes it into work units, spawns autonomous agents for each unit, coordinates dependencies, and delivers complete PRs. Use when a plan document exists and needs end-to-end implementation.
---

# Autonomous Plan-to-Implementation Pipeline

Read a finalized plan, decompose into work units, spawn autonomous agents for each unit, coordinate dependencies, and deliver complete PRs without context loss.

## Workflow

### Phase 1: Plan Decomposition
1. **Read plan file**: `docs/plans/[PLAN_FILE].md`
2. **Read MEMORY.md**: Current project state and context
3. **Decompose into work units**:
   - Each unit = 1 focused PR
   - Identify dependencies between units
   - Size each unit for single-session completion

### Phase 2: Dependency Graph
Build execution order:
- **Independent units**: Can run in parallel
- **Dependent units**: Must wait for prerequisite PRs

### Phase 3: Execute Work Units
For each work unit (respecting dependencies):
1. **Spawn sub-task agent** — see [WORK_UNIT_TEMPLATE.md](WORK_UNIT_TEMPLATE.md) for instructions format
2. **Agent implements changes** following CLAUDE.md conventions
3. **Agent validates**: Run `make check` → fix → iterate until passing
4. **Agent creates PR** referencing the plan file
5. **Agent updates MEMORY.md** with PR number and any deviations

### Phase 4: Coordination
- After each unit: Report progress to user
- Before dependent unit: Verify prerequisite PR exists
- If unit fails: Diagnose → attempt fix → continue with independent units
- Track progress with TodoWrite

### Phase 5: Final Summary
- List all PRs created
- Note any plan deviations
- Update MEMORY.md with full status

## Output Format

Progress updates after each unit:

```markdown
✅ Unit 1 Complete: [title]
   - PR #NNN created
   - Tests: N passing
   - MEMORY.md updated

⚙️  Unit 2 In Progress: [title]
⏸️  Unit 3 Waiting: [title] (depends on Unit 1 ✅)

Progress: 1/6 units complete, 1 in progress, 4 pending
```

## Anti-Patterns to Avoid

- Asking for confirmation between units
- Implementing units out of dependency order
- Skipping `make check` to save time
- Creating mega-PRs instead of focused units
- Ignoring plan deviations (document them!)

## Error Handling

If a work unit fails:
1. Capture error details
2. Attempt automatic fix (read error, fix code, retry)
3. If still failing: Report to user, continue with independent units
4. Mark unit as blocked in TodoWrite
5. Update MEMORY.md with blocker details

If Unit C depends on blocked Unit A:
- Mark C as "blocked waiting for A"
- Continue with independent units
- Report blocking chain to user

## Notes

- Plan file must exist at `docs/plans/[PLAN_FILE].md`
- Each work unit should be PR-sized
- Agents operate with full autonomy (no confirmation prompts)
- Best for 3-6 unit plans (larger plans → use `/chunking-prs`)
