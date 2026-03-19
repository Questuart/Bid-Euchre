# Skills Expansion Execution Handoff
**Date:** 2026-03-19
**Goal:** Implement the READY skills-expansion plan in one docs/skills PR, from fresh worktree through validation and PR creation.

## Primary References

- `plans/sessions/2026-03-19_skills-expansion.md`
- `plans/sessions/2026-03-19_skills-expansion-review-handoff.md`
- `.claude/CLAUDE.md` (`Implementation Handoff Protocol`)
- `.claude/rules/25_task_lists.md`

## Current State

- The implementation plan at `plans/sessions/2026-03-19_skills-expansion.md` has already been reviewed and is now `READY`.
- There is **no PR yet** for this work.
- The currently open PR `#978` is unrelated. Do not stack on it or modify its branch.
- Use the **explicit file lists below as the source of truth**. If any summary counts in the plan drift, prefer the concrete paths.

## Mandatory Execution Sequence

Before any code or docs edits, do this in order:

1. Read the plan file and this handoff fully.
2. Refresh or draft a concrete execution plan for this PR slice.
3. Spawn at least one reviewer agent to review that refreshed execution plan before major edits.
4. Create and maintain a task list covering implementation, validation, and PR shipment.
5. Assess safe parallelism and delegate only disjoint write scopes.
6. Execute the work end to end autonomously:
   - implement
   - validate
   - commit
   - open the PR
   - include `Validation Performed` evidence in the PR body

Do not skip directly from reading the plan to editing files.

## Branch / Worktree Setup

Start from `main` in a fresh worktree and use a `codex/` branch name.

Suggested pattern:

```bash
git fetch origin main
git worktree add ../Bid-Euchre-skills-expansion -b codex/skills-expansion origin/main
```

If that path or branch already exists, choose a nearby variant, but keep the branch prefixed with `codex/`.

## Scope

### In Scope

- Create 7 new skills.
- Create 3 supporting progressive-disclosure files.
- Retire 3 stale skills.
- Update existing skills for stale tool/task references.
- Add gotchas sections to 5 existing skills.
- Clean up the live `/reviewing-plans` references called out in the plan.

### Out of Scope

- Any Python source changes.
- Any workflow-hook behavior change for skill-usage logging (`.claude/settings.json` remains deferred).
- Any update to frozen/historical Arc D lineage plans beyond what the implementation plan explicitly calls live cleanup.
- Any unrelated cleanup beyond the files listed below.

## Source-of-Truth File List

### New Files

- `.claude/skills/running-experiments/SKILL.md`
- `.claude/skills/running-experiments/QUICK_REFERENCE.md`
- `.claude/skills/analyzing-results/SKILL.md`
- `.claude/skills/analyzing-results/CHECKLIST.md`
- `.claude/skills/debugging-ci/SKILL.md`
- `.claude/skills/debugging-ci/SYMPTOM_TABLE.md`
- `.claude/skills/managing-worktrees/SKILL.md`
- `.claude/skills/validating-changes/SKILL.md`
- `.claude/skills/adding-strategies/SKILL.md`
- `.claude/skills/triaging-issues/SKILL.md`

### Deleted Files

- `.claude/skills/reviewing-plans/SKILL.md`
- `.claude/skills/drafting-rung-reports/SKILL.md`
- `.claude/skills/narrating-reports/SKILL.md`

### Modified Files

- `.claude/skills/reviewing-changes/SKILL.md`
- `.claude/skills/executing-plans/SKILL.md`
- `.claude/skills/shipping-changes/SKILL.md`
- `.claude/skills/planning-code-first/SKILL.md`
- `.claude/skills/recovering-context/SKILL.md`
- `.claude/skills/fixing-bugs/SKILL.md`
- `.claude/skills/summarizing-sessions/SKILL.md`
- `.claude/skills/reviewing-repo/SKILL.md`
- `docs/02_agent/PLAN_REVIEW_RUBRIC.md`
- `.claude/hooks/README.md`

## Non-Negotiable Content Requirements

### New Skill Quality Bar

For each new `SKILL.md`:

- Frontmatter must include correct `name` and `description`.
- Descriptions must be **trigger-oriented**, not generic summaries.
- Guidance must stay specific to this repo and its workflows.
- References should point to authoritative repo docs for progressive disclosure.
- Gotchas must be concrete and project-specific.

### Existing Skill Updates

- Replace `TodoWrite` references with `TaskCreate` / `TaskUpdate` where planned.
- Replace stale `Task tool` wording with `Agent tool` in:
  - `.claude/skills/summarizing-sessions/SKILL.md`
  - `.claude/skills/reviewing-repo/SKILL.md`
- Add gotchas sections to the 5 planned existing skills using repo-specific failure modes, not generic agent advice.

### Retirement Cleanup

- Remove the three retired skill files listed above.
- Update live `/reviewing-plans` references in:
  - `docs/02_agent/PLAN_REVIEW_RUBRIC.md`
  - `.claude/hooks/README.md`
- Do **not** expand cleanup into frozen/history-only references unless the work is trivial and clearly in scope.

## Safe Parallelism Guidance

Parallelize only across disjoint write scopes.

Good splits:

- Worker A: `running-experiments/`, `analyzing-results/`
- Worker B: `debugging-ci/`, `managing-worktrees/`, `validating-changes/`
- Worker C: `adding-strategies/`, `triaging-issues/`
- Main agent: deletions, shared skill edits, doc cleanup, integration, validation, PR

Keep these with the main agent:

- final wording consistency across new skills
- retired-skill deletions
- `PLAN_REVIEW_RUBRIC.md` and `.claude/hooks/README.md`
- final validation
- commit / PR body / PR creation

Do not have multiple agents edit the same existing skill file.

## Recommended Execution Flow

1. Verify `main` base and create the worktree/branch.
2. Refresh the execution plan and get one reviewer-agent pass on it.
3. Create the task list.
4. Implement the new skill folders and support docs.
5. Update existing skills and docs.
6. Delete retired skills.
7. Run validation.
8. Fix any validation failures.
9. Commit and open the PR.
10. Update the plan `## Outcome` section if appropriate once the PR exists.

## Validation Requirements

Minimum required:

- `make check`

Required grep / sanity checks:

```bash
rg -n "TodoWrite|Task tool" .claude/skills
```

Expected result:

- no remaining live hits in the shipped skill set

```bash
rg -n "/reviewing-plans" docs/02_agent/PLAN_REVIEW_RUBRIC.md .claude/hooks/README.md
```

Expected result:

- no remaining live hits in those two files

```bash
find .claude/skills -maxdepth 2 -name SKILL.md | sort
```

Use this to confirm the retired skills are gone and the new skill directories exist.

Manual validation required:

- spot-check each new skill description for trigger specificity
- verify gotchas are repo-specific
- verify references in each new skill point to real docs/scripts
- verify the overlap boundary is still clear for:
  - `validating-changes` vs `debugging-ci`
  - `running-experiments` vs `analyzing-results`

## PR Guidance

Open one PR from the new `codex/` branch.

The PR body should include:

- plan path: `plans/sessions/2026-03-19_skills-expansion.md`
- confirmation that the implementation followed the reviewed plan
- concise file-group summary:
  - new skills
  - retired skills
  - existing-skill updates
  - live reference cleanup
- `Validation Performed` with the exact commands run
- note that `.claude/settings.json` skill-usage logging was intentionally deferred

After `gh pr create`, expect the normal post-PR review hook flow to run.

## Deliverables

1. Branch in a dedicated worktree.
2. All planned file edits complete and committed.
3. PR opened.
4. Short completion note with:
   - PR number / link
   - validation performed
   - whether any scope was deferred
   - any remaining follow-up risk

## Success Condition

This handoff is complete when one PR has:

- added the 7 new skills and 3 support docs
- retired the 3 stale skills
- updated the planned existing skills and live docs references
- passed `make check`
- removed the targeted stale `TodoWrite`, `Task tool`, and live `/reviewing-plans` references in the scoped files
- shipped with a PR body that includes clear validation evidence
