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

## Codex Review
- [ ] Codex auto-review received (or N/A if not yet enabled)
- [ ] Blocking Codex comments addressed
- [ ] Non-blocking Codex findings captured as follow-up issues (if any)

## Checklist
- [ ] No generated artifacts committed (`data/runs`, `data/reports`)
- [ ] If behavior changed, tests updated/added to lock it
- [ ] PR is focused (one concept)
