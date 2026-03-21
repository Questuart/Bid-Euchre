# Post-PR4 Proving — Ops Handoff

**Lane Direction:** `ops` owns the proving window after PR4. Do not edit the cutover files during proving unless a blocking defect forces a follow-up PR.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_post-pr4-proving-checklist.md`
**Dependencies:** PR4 merged

## Your Mission

Run the proving checklist against real PR traffic before declaring the new gate stable.

## Required Sequence

1. Select or queue real PRs that cover:
   - clean pass
   - blocked then fixed
   - stale SHA invalidation
2. Capture evidence for each run.
3. Confirm the legacy local loop is no longer merge-authoritative.
4. Record any proving failures as explicit follow-up issues or session notes.

## What To Watch

- request packet missing or not created on PR update
- verdict written for the wrong SHA
- stale verdict still satisfying merge guard
- `error` collapsing to `clean`
- operators needing raw runtime-file inspection for normal cases
- old auto-merge path still active anywhere

## Escalation Rule

If the proving window finds a defect that weakens merge safety:

- stop treating the new gate as settled
- queue a bounded follow-up PR
- do not expand scope into PR5 delegation/docs work until merge safety is restored

## Deliverables

- completed proving checklist with evidence
- explicit go / no-go recommendation for PR5
- follow-up issues or PRs for any failures found

## Exit Criteria

- proving evidence exists for the required scenarios
- merge safety is demonstrated on real PR traffic
- any residual issues are explicit, bounded, and owned
