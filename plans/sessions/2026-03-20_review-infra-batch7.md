# Review Infra — Batch 7 from triage plan

## Context

2 issues assigned to Batch 7 (review infrastructure improvements).

## #829 — Review driver should checkout PR branch before Codex

**Assessment: Close as deferred architectural improvement.**

This is a significant architectural change to the review driver. The current
workarounds (PR #826) are effective:
- RC1 (empty diff) → detected as clean review
- RC3 (PV2 false positive) → demoted to P2 warning

The review driver already documents this limitation (lines 471, 808).
The fix (ephemeral worktree per review) adds complexity and risk to a
system that's advisory-only. The cost/benefit doesn't justify the change
while the workarounds are in place.

Close with explanation and recommendation to revisit if the workarounds
prove insufficient.

## #830 — Port reversed-format parser to plan review adapter

**Assessment: Implement.**

Port `_REVERSED_FINDING_RE` and `_parse_reversed_format()` from
`codex_review_adapter.py` to `codex_plan_review_adapter.py`.

### Files

| File | Change |
|------|--------|
| `scripts/internal/codex_plan_review_adapter.py` | Add `_REVERSED_FINDING_RE`, `_parse_reversed_format()`, wire into parser |
| `tests/unit/test_codex_plan_review_adapter.py` | Add reversed-format parsing tests |

### Implementation

1. Copy `_REVERSED_FINDING_RE` regex from `codex_review_adapter.py` (line 127)
2. Adapt `_parse_reversed_format()` for `PlanReviewFinding` return type
3. Wire into `parse_plan_findings()` as a fallback before prose parsing
4. Port line-range handling (`90-95` → extract `90`)
5. Add tests matching the review adapter test patterns

### Validation

- `uv run python -m pytest tests/unit/test_codex_plan_review_adapter.py -v`
- `make check-quiet`

## Outcome

_(To be filled after implementation)_
