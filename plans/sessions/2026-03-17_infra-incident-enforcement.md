<!-- review-tier: medium -->

# Infra Incident Enforcement

**Date:** 2026-03-17
**Status:** COMPLETE
**Scope:** Add mechanical enforcement for infra changes without tests, introduce lightweight infra-incident PR metadata, reuse GitHub Issues as the repeat-incident ledger, and standardize minimal status/log output for unattended infra scripts.

---

## Goal

Reduce repeated infrastructure breakages that are fixed ad hoc and then forgotten by making the durable parts of the response enforceable in CI:

1. Infra changes to existing automation must ship with regression tests.
2. Repeat infra incidents must have a durable issue trail.
3. Unattended infra scripts must expose enough machine-readable state for debugging.

## PR Breakdown

### PR 1: Linter hard gate for infra changes without tests
- `scripts/lint_repo.py` — `check_infra_changes_require_tests()` + `list_changed_files_with_status()`
- `tests/unit/test_lint_repo.py` — 21 new tests

### PR 2: PR template + docs policy
- `.github/pull_request_template.md` — `## Infra Incident` section
- `docs/TESTING_STRATEGY.md` — Infrastructure Testing Policy section

### PR 3: Governance metadata checker
- `scripts/check_infra_pr_metadata.py` — advisory checker for infra PR metadata
- `tests/unit/test_check_infra_pr_metadata.py` — 25 tests
- `.github/workflows/governance.yml` — wired as advisory step
- `docs/01_core/ARCHITECTURE.md` — registered new script

### PR 4: Infra-incident issue dedupe workflow
- `.github/workflows/infra_incident_dedupe.yml` — manual dispatch, create-or-comment

### PR 5: Minimal unattended state/log contract rollout
- `.claude/hooks/README.md` — Unattended State Contract section + conformance audit

## Outcome

- Result: COMPLETE
- PRs: #812, #813, #814, #816, #817 (all merged 2026-03-18)
- Notes: Plan file was lost from main checkout during a `git stash --include-untracked` and re-created post-merge with outcome filled in.
