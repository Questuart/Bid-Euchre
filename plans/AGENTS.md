# Review Guidelines — Plans

These guidelines apply to all files under `plans/`.

Codex: when reviewing PRs that touch this directory, apply these checks.

## Plan Audit Checks

- Treat nonexistent file references as P1 (new files being created are exempt).
- Treat contradictory execution steps as P1.
- Treat unenforceable merge gates as P1.
- Treat workflows that can deadlock branch protection as P1.
- Treat missing testing strategy for code PRs as P1.
- Treat sub-plans missing required fields (see `docs/02_agent/AGENTS.md` section 12.3) as P1.
- Treat sub-plans not registered in their initiative's `sub_plan_registry.md` as P1.

## What NOT to Flag

- File paths marked as "new" or "to be created" — these don't exist yet by design.
- Outcome sections that say "to be filled" — these are completed post-implementation.
- Plan scope decisions — these are the author's prerogative, not a review target.
- Template files in `_templates/` — these contain placeholder values by design.

## Tiered Plan Review

Plans are reviewed at three tiers based on complexity and scope.
See `docs/02_agent/PLAN_REVIEW_TIERS.md` for the full specification.

| Tier | Scope | Checks |
|------|-------|--------|
| Small | <=3 files, single-PR, <80 lines | 7 convention checks (P1,P2,P3,P5,P6,P9,R4) |
| Medium | 4-10 files, multi-PR, 80-300 lines | 15 convention + 5 risk flags |
| Governing | Multi-rung/phase, research plans | Full 16-dimension rubric + 8 hard gates |

Codex: when reviewing plan files, classify the plan tier and apply the
appropriate depth. Default to the existing Plan Audit Checks above for
any plan that doesn't clearly fit a tier.

## Plan Hierarchy

For the governing plan framework (governing plans, sub-plans, registries,
checkpoints), see `docs/02_agent/AGENTS.md` section 12.
