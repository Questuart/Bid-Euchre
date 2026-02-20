---
name: chunking-prs
description: Executes multi-PR plans in manageable chunks of 3-4 PRs per session with mandatory MEMORY.md checkpoints. Use when a plan has 5+ PRs that risk context limit degradation if attempted in one session.
disable-model-invocation: true
---

# Batched Multi-PR Implementation

Execute multi-PR plans in manageable chunks to maintain quality and avoid context length issues.

## Workflow

1. **Identify the chunk scope** from the larger plan
   - Typically PRs 1-3, then 4-6, then 7-8
   - Must be explicitly specified in the prompt

2. **Implement each PR in the chunk** with full quality checks:
   - Create worktree for each PR
   - Implement changes following the plan
   - Run `make check` — full test suite + lint
   - Write proper PR description using template
   - Get CI passing before merging
   - Clean up worktree after merge

3. **After completing the chunk**:
   - Update MEMORY.md with PR numbers and status
   - Document what was completed vs. what remains
   - Note any discoveries or blockers
   - **STOP** — do not continue to next chunk

4. **Quality gates** (enforced per PR):
   - All tests passing
   - Lint clean (ruff check + format)
   - PR description complete with repro command
   - CI green before merge

## Output Format

```markdown
## PR Chunk Complete: PRs 1-3 of 8

### Completed
- PR #XXX: [title] - merged
- PR #YYY: [title] - merged
- PR #ZZZ: [title] - merged

### Status
All tests passing, lint clean, CI green, MEMORY.md updated.

### Next Chunk
PRs 4-6 remain. Resume with: `/chunking-prs 4-6 of 8-PR plan [plan reference]`

### Discoveries
- [Any new findings, blockers, or adjustments needed]
```

## Error Handling

If a PR in the chunk fails `make check`:
1. Read the failure output and fix the code
2. Re-run `make check` until passing
3. If unfixable, document the blocker in MEMORY.md and move to the next independent PR

If CI fails after push:
1. Check CI output with `gh pr checks <PR_NUMBER>`
2. Fix locally, push again
3. If CI issue is unrelated to your changes, note it and proceed

If a PR depends on a failed earlier PR in the chunk:
- Skip the dependent PR
- Document the dependency chain in MEMORY.md
- Report to user at chunk end

## Anti-Patterns to Avoid

- Attempting all 8 PRs in one session (context limit risk)
- Skipping `make check` to "save time"
- Moving to next chunk without MEMORY.md update
- Partial PR implementations ("I'll finish it later")

## Notes

- Maximum 3-4 PRs per chunk recommended
- Always update MEMORY.md between chunks
- Consider pairing with `/planning-code-first` to verify plan details before starting
