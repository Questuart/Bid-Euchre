## Summary
Fix doc/code mismatches that cause agent mis-execution by aligning DRIFT.md, ARCHITECTURE.md, and experiments/README.md with current codepaths.

## Why
Documentation contained outdated CLI usage, references to deleted directories, and incorrect counts that could mislead users and automation.

## Repro / Validation
**Command(s) run:**
- `PYTHONPATH=src python scripts/run_suite.py --help` (verified CLI format)
- `PYTHONPATH=src python scripts/compare_rollup.py --help` (verified CLI format)
- `ls experiments/suites/` (verified suite file count)
- `make lint` (validation)

**Config (if applicable):**
N/A

**Seed (if applicable):**
N/A

## What changed
- `docs/01_core/DRIFT.md`: Fixed CLI example to use `--suite <path-to-yaml>` format
- `docs/01_core/ARCHITECTURE.md`: Removed references to non-existent directories, added canonical entrypoints
- `experiments/README.md`: Updated suite count from (1 YAML) to (2 YAML)

## Scope
- In scope:
  - `docs/01_core/DRIFT.md`
  - `docs/01_core/ARCHITECTURE.md`
  - `experiments/README.md`

- Out of scope:
  - Any code changes
  - Any fixture changes

## Notes
All changes are documentation-only to align docs with current repository structure and CLI interfaces.

## Release / rollout
No impact - documentation improvements only.

## Validation checklist
- [ ] Unit: `PYTHONPATH=src python -m pytest tests/unit/`
- [ ] Integration (if engine/rules changed): `PYTHONPATH=src python -m pytest tests/integration/`
- [x] Other: `make lint`

## Expected impact
- Metrics impact (if any): N/A
- Runtime impact (if any): N/A

## Risk level
- [x] Low (docs/tests only)
- [ ] Medium (strategy/experiments)
- [ ] High (core rules/sim/scoring)

## Checklist
- [x] No generated artifacts committed (`data/runs`, `data/reports`)
- [ ] If behavior changed, tests updated/added to lock it
- [x] PR is focused (one concept)
