## Plan
<!-- Link to the plan file that authorized this PR, or N/A for trivial changes -->
-

## Summary
-

## Why
-

## Repro / Validation
**Command(s) run:**
-

**Config (if applicable):**
-

**Seed (if applicable):**
-

## Tests
- [ ] `PYTHONPATH=src python -m pytest -m "not slow" tests/`
- [ ] Integration (if engine/rules changed): `PYTHONPATH=src python -m pytest tests/integration/`
- [ ] Other:

## Expected impact
- Metrics impact (if any):
- Runtime impact (if any):

## Risk level
- [ ] Low (docs/tests only)
- [ ] Medium (strategy/experiments)
- [ ] High (core rules/sim/scoring)

## Worktree proof (required)
**Paste outputs; PRs missing this may be rejected.**

`pwd`:
```
(paste output here)
```

`git rev-parse --show-toplevel`:
```
(paste output here)
```

`git worktree list`:
```
(paste output here)
```

## Report Provenance (required for PRs touching `docs/04_reports/`)
<!-- Delete this section if not a report PR -->
- Analysis script/notebook path:
- Artifact path (if any):
- Provenance SHA:
- Formal gate result:
- Override/adjudication rationale (if any):
- Repro command:

## Review Loop
- [ ] Autonomous review loop completed (Codex CLI)
- [ ] Blocking findings addressed
- [ ] Non-blocking findings captured as follow-up issues (if any)

## Infra Incident (optional — fill when fixing infra breakage)
<!-- Delete this section if not an infra-incident PR -->
- Issue: <!-- Link to GitHub issue with `infra-incident` label, or N/A -->
- First occurrence or repeat: <!-- "first" or link to prior issue -->
- Regression test: <!-- Path to new/updated test, e.g., tests/unit/test_ci_poller.py -->
- Detection/logging note: <!-- How was this detected? What monitoring exists now? -->

## Checklist
- [ ] No generated artifacts committed (`data/runs`, `data/reports`)
- [ ] If behavior changed, tests updated/added to lock it
- [ ] PR is focused (one concept)
