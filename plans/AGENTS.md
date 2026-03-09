# Review Guidelines — Plans

These guidelines apply to all files under `plans/`.

Codex: when reviewing PRs that touch this directory, apply these checks.

## Plan Audit Checks

- Treat nonexistent file references as P1 (new files being created are exempt).
- Treat contradictory execution steps as P1.
- Treat unenforceable merge gates as P1.
- Treat workflows that can deadlock branch protection as P1.
- Treat missing testing strategy for code PRs as P1.

## What NOT to Flag

- File paths marked as "new" or "to be created" — these don't exist yet by design.
- Outcome sections that say "to be filled" — these are completed post-implementation.
- Plan scope decisions — these are the author's prerogative, not a review target.
