# PR Chunk - Batched Multi-PR Implementation

Execute multi-PR plans in manageable chunks to maintain quality and avoid context length issues.

## Purpose

Large multi-PR plans (5-8+ PRs) often hit context limits or degrade in quality toward the end. This skill enforces chunking to 3-4 PRs per session with mandatory MEMORY.md checkpoints.

## Workflow

1. **Identify the chunk scope** from the larger plan
   - Typically PRs 1-3, then 4-6, then 7-8
   - Must be explicitly specified in the prompt

2. **Implement each PR in the chunk** with full quality checks:
   - Create worktree for each PR
   - Implement changes following the plan
   - Run `make check` - full test suite + lint
   - Write proper PR description using template
   - Get CI passing before merging
   - Clean up worktree after merge

3. **After completing the chunk**:
   - Update MEMORY.md with PR numbers and status
   - Document what was completed vs. what remains
   - Note any discoveries or blockers
   - **STOP** - do not continue to next chunk

4. **Quality gates** (enforced per PR):
   - ✅ All tests passing
   - ✅ Lint clean (ruff check + format)
   - ✅ PR description complete with repro command
   - ✅ CI green before merge

## Usage

```bash
/pr_chunk 1-3 of 8-PR plan [plan file reference]
```

Example prompts:
- "We're implementing PRs 1-3 of the 8-PR architecture refactor. After completing these 3, update MEMORY.md with status and stop."
- "Execute PR chunk 4-6 from the plan at plans/bidding_refactor.md. Stop after PR 6."

## Anti-Patterns to Avoid

❌ Attempting all 8 PRs in one session (context limit risk)
❌ Skipping `make check` to "save time"
❌ Moving to next chunk without MEMORY.md update
❌ Partial PR implementations ("I'll finish it later")

## Benefits

- ✅ Maintains quality throughout (no late-session degradation)
- ✅ Prevents context length failures
- ✅ Creates natural checkpoint boundaries
- ✅ Easier to resume if blocked
- ✅ Each chunk is a complete, shippable unit

## Output Format

At the end of the chunk:

```markdown
## PR Chunk Complete: PRs 1-3 of 8

### Completed
- PR #XXX: [title] - merged
- PR #YYY: [title] - merged
- PR #ZZZ: [title] - merged

### Status
✅ All tests passing
✅ Lint clean
✅ CI green on all PRs
✅ MEMORY.md updated

### Next Chunk
PRs 4-6 remain. Resume with: `/pr_chunk 4-6 of 8-PR plan [plan reference]`

### Discoveries
- [Any new findings, blockers, or adjustments needed]
```

## Notes

- Maximum 3-4 PRs per chunk recommended
- Always update MEMORY.md between chunks
- Each chunk should take ~30-45 minutes
- Consider pairing with `/plan_init` to verify plan details before starting
