# Review Guidelines — Reports

These guidelines apply to all files under `docs/04_reports/`.

Codex: when reviewing PRs that touch this directory, apply these checks.

## Report Audit Checks

- Treat provenance SHA mismatches as P1.
- Treat published metrics without a committed generating script/notebook as P1.
- Treat formal gate-result mismatches or hidden overrides as P1.
- Treat unsupported reproduction claims as P1.
- Treat referenced artifact paths that do not exist (and have no repro command) as P1.

## What NOT to Flag

- Prose style, grammar, or formatting — these are not P0/P1 issues.
- Missing sections that are explicitly marked as placeholders.
- References to `data/runs/` paths — these are gitignored by policy.
