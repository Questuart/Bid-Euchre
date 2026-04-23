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

## Test Criteria
<!-- Define specific, verifiable conditions that prove this PR is done.
     Not just "tests pass" — what observable outcome proves the feature works? -->
- **Pass condition:** <!-- e.g., "grep -c audit_reply src/bid_euchre/ops/*.py returns >= 1" -->
- **Verification command:** <!-- exact command to run -->
- **Expected result:** <!-- what the output should look like -->

## Tests
- [ ] `PYTHONPATH=src python -m pytest -m "not slow" tests/`
- [ ] Integration (if engine/rules changed): `PYTHONPATH=src python -m pytest tests/integration/`
- [ ] Other:

## Verification Performed
<!--
  Pattern 10 (§10.9 of the steward-platform governing plan) requires every
  slice to name the verification surface it satisfied and paste evidence
  that the surface was actually exercised. Include this section whenever
  the PR touches a trigger path under §3.3 of
  `plans/steward_platform/verification_contract/shaping.md`
  (src/**, scripts/internal/**, .claude/hooks/**, .claude/skills/**,
  .claude/rules/prompt_policy/**, plans/_templates/**, .claude/settings.json,
  or creates/modifies ADRs/plan deliverables).

  This section is also the fallback verification-surface home that V2 / V5
  prechecks in `scripts/internal/deterministic_prechecks.py` recognize.

  Per-surface evidence protocol:
  - named test       → paste pass output
  - named command    → paste stdout (elide stable noise)
  - review prompt    → paste prompt + observed result
  - event-schema query → paste query + matching event record shape
  - canary reference → name run ID + link dashboard snapshot
  - rollback test    → paste forward-then-reverse outputs
-->

**Surface:** <!-- e.g., `tests/unit/test_foo.py::test_bar`, or `make check-gated`, or "operator review: <specific observable>" -->

**Evidence:**
```
(paste test/command output, review result, event record, canary run ID, or rollback outputs here)
```

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

## Issue Linkage
<!-- Use 'Fixes #N' ONLY when this PR fully resolves the issue — merge will auto-close it.
     Use 'Refs #N' when the PR partially addresses or relates to the issue without resolving it.
     See .claude/rules/deferred/55_issue_closure.md for the tiered closure policy. -->
-

## Checklist
- [ ] No generated artifacts committed (`data/runs`, `data/reports`)
- [ ] If behavior changed, tests updated/added to lock it
- [ ] PR is focused (one concept)
- [ ] Issue linkage uses correct keyword (`Fixes` vs `Refs`) per closure policy
