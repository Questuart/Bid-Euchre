# PR Rules

> **Authoritative sources:**
> - @docs/02_agent/REVIEW_CHECKLIST.md
> - @.github/pull_request_template.md

## PR Template Required

Every PR must use the template from `.github/pull_request_template.md`.

Required sections:
- **Summary** — what changed (1-3 bullets)
- **Why** — motivation
- **Repro / Validation** — exact command with seed/config
- **Tests** — which test commands were run
- **Worktree proof** — `pwd`, `git rev-parse --show-toplevel`, `git worktree list`

## Hard Gates (Pre-PR Checklist)

From @docs/02_agent/REVIEW_CHECKLIST.md:

- [ ] Branch based on main
- [ ] Scope lock — only touched declared files
- [ ] `make check-gated` (or `make check`) passes
- [ ] No artifacts in `data/runs/` or `data/reports/`
- [ ] Exact repro command in PR description
- [ ] Contract compliance (if touching rules/logging/metrics)

## Key Constraints

1. **One concept per PR** — no mixed refactor + feature
2. **Worktree-only workflow** — never commit from main checkout
3. **PR URL required** — don't claim PR exists without citing URL
4. **Tests must lock behavior** — if you changed outcomes, add tests

See @docs/02_agent/AGENTS.md §2 for Definition of Done.
