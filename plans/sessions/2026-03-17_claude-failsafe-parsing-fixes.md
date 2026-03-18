<!-- review-tier: small -->
# Fix Claude Failsafe Parsing — 3 Bugs Causing 100% Fallback Failure

## Problem

11 of 13 plan reviews (85%) fail. When Codex CLI fails (timeout or unparseable
output), the Claude failsafe path also fails **every time**, resulting in 0%
fallback recovery. A synthetic CRITICAL "plan has not been reviewed" finding is
injected for every failed review.

## Confirmed Bugs (reproduced locally)

### Bug 1: Code fence wrapper breaks JSON parsing

`_parse_claude_json_output()` in `codex_plan_review_adapter.py:738` does
`json.loads(raw_output.strip())`. Claude CLI wraps JSON in markdown code fences:

```
```json
[...]
```
```

This fails with `JSONDecodeError`. Confirmed: `findings=0, expected=1`.

### Bug 2: Claude returns wrong schema fields

The prompt asks for `severity/category/file/line/description/check_id`.
Claude actually returns `severity: "BLOCK"/"WARN"`, `rule:`, `message:`.
`PlanReviewFinding.from_dict()` raises `TypeError: missing 5 required positional
arguments`. Confirmed: `findings=0, expected=2`.

### Bug 3: Empty findings (clean review) treated as total failure

`plan_review_driver.py:358`:
```python
if fallback_result.success and fallback_result.findings:
```
`[]` is falsy, so `success=True, findings=[]` hits the else branch and injects
a synthetic CRITICAL. Confirmed.

## Files to Change

| File | Change | Bug |
|------|--------|-----|
| `scripts/internal/codex_plan_review_adapter.py` | `_parse_claude_json_output()` — strip code fences before `json.loads` | 1 |
| `scripts/internal/codex_plan_review_adapter.py` | `_parse_claude_json_output()` — normalize Claude schema (BLOCK→CRITICAL, WARN→WARNING, rule→category, message→description, synthesize missing file/line/check_id) | 2 |
| `scripts/internal/plan_review_driver.py` | Line 358 — separate clean review from actual failure | 3 |
| `tests/unit/test_codex_plan_review_adapter.py` | New tests for code fence stripping and schema normalization | 1,2 |
| `tests/unit/test_plan_review_driver.py` | New test for clean-review fallback path (success=True, findings=[]) | 3 |

## Implementation Steps

### Step 1: Fix `_parse_claude_json_output()` — code fence stripping (Bug 1)

Add a helper to strip markdown code fences before JSON parsing:
- Strip leading ```` ```json ```` or ```` ``` ```` and trailing ```` ``` ````
- Handle optional language tag (`json`, `JSON`, no tag)
- Handle whitespace/newlines around fences
- Fall back to the raw string if no fences found

### Step 2: Fix `_parse_claude_json_output()` — schema normalization (Bug 2)

After parsing JSON, normalize each finding dict before constructing `PlanReviewFinding`:
- Map severity: `BLOCK`→`CRITICAL`, `WARN`→`WARNING`, pass through valid values
- Map fields: `message`→`description`, `rule`→`category`
- Synthesize missing required fields: `file`="(plan)", `line`=0, `check_id`=None
- Keep existing valid-schema items working (no regression)

### Step 3: Fix fallback clean-review path (Bug 3)

Change `plan_review_driver.py:358` from:
```python
if fallback_result.success and fallback_result.findings:
```
to:
```python
if fallback_result.success:
    if fallback_result.findings:
        # Has findings — record them
        ...
    else:
        # Clean review — no findings
        loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
        loop_state.transition(PlanReviewState.REVIEW_COMPLETE)
```

### Step 4: Add tests

**`test_codex_plan_review_adapter.py`:**
- `test_parse_json_with_code_fences` — JSON wrapped in ```` ```json ```` fences
- `test_parse_json_with_bare_fences` — JSON wrapped in ```` ``` ```` (no language tag)
- `test_parse_json_with_preamble_and_fences` — Claude adds text before the fence
- `test_parse_json_normalizes_claude_schema` — BLOCK/WARN + rule/message fields
- `test_parse_json_mixed_schema` — mix of canonical and Claude schema items
- `test_parse_json_bare_valid_still_works` — regression: bare valid JSON unchanged

**`test_plan_review_driver.py`:**
- `test_fallback_clean_review` — success=True, findings=[] → READY (not NOT_READY)

### Step 5: Validate

- Run `uv run python -m pytest tests/unit/test_codex_plan_review_adapter.py tests/unit/test_plan_review_driver.py -v`
- Run `make check-quiet`

## Outcome

PR #TBD — `fix/claude-failsafe-parsing`

All three bugs confirmed via reproduction scripts before implementation.
100 tests pass (68 adapter + 32 driver), including 20 new tests.
`make check-quiet` passes.
