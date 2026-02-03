# Summary
-

# Why
-

# Reproduce Command
```
<command with config path and --seed if relevant>
```

# Tests Run
```
<test commands>
```

# Expected Metrics Impact
- None / TBD

# Worktree Proof
```
git rev-parse --show-toplevel
git branch --show-current
```

# PR URL
- <paste `gh pr view --json url --jq .url` output>

# Checklist
- [ ] One concept per PR; diff is focused
- [ ] No generated artifacts committed under `data/runs/` or `data/reports/`
- [ ] Behavior changes have matching tests
- [ ] If reporting/eval changed, METRICS.md compliance verified
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

## Checklist
- [ ] No generated artifacts committed (`data/runs`, `data/reports`)
- [ ] If behavior changed, tests updated/added to lock it
- [ ] PR is focused (one concept)
