# Operational Playbooks (PLAYBOOKS.md)

> Repeatable runbook-style procedures for recurring operations: lane
> restart, deploy rollback, rebase-conflict triage, etc. Each playbook
> is self-contained and verifiable — if a lane executes the steps and
> the verification passes, the outcome is known.
>
> **Commit policy (ADR 010):** promoted runbooks only. Session-scratch
> procedures that might become playbooks land in `knowledge/_candidates/`
> (gitignored) until promoted.
>
> **Schema:** each runbook is a `### <runbook name>` heading followed by
> three fields:
>
> - **When:** triggering condition — when to invoke this playbook
> - **Steps:** numbered procedure, each step one observable action
> - **Verification:** how to confirm success — command + expected output

---

## Worked example

### Clean up a merged PR's worktree

**When:** A PR authored from a `worktree-<branch>` directory has merged
on GitHub AND the working tree is clean AND the worktree is not in the
protected list at `.claude/rules/75_worktree_protection.md`.

**Steps:**

1. Verify the worktree is not protected:
   `grep -q "<worktree-dir-name>" .claude/rules/75_worktree_protection.md`
   — if the grep matches, abort (never remove a protected worktree).
2. Verify the worktree is clean:
   `git -C <worktree-path> status --short` — output must be empty.
3. Verify the branch is merged:
   `gh pr list --state merged --head <branch> --json number` — must
   return ≥1 match.
4. Remove the worktree:
   `git worktree remove <worktree-path>`.
5. Prune the branch reference locally (optional):
   `git branch -D <branch>`.

**Verification:** `git worktree list` no longer shows the worktree; the
worktree directory is gone.

---

## Promoted runbooks

_(promoted entries accumulate below)_
