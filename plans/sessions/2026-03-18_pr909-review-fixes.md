# PR #909 Review Fix Plan

**PR:** `feat: per-contract extraction in comparator CIs pipeline`
**Branch:** `fix/behavior-by-contract-faceting`
**Date:** 2026-03-18

## Context

PR #909 adds per-contract (suit/high/low) extraction to `extract_comparator_cis.py`.
A review identified 2 correctness bugs, 2 design issues, and 1 process issue. All
findings validated against source code.

## Validated Findings

| # | Severity | Finding | Validated |
|---|----------|---------|-----------|
| F1 | CRITICAL | All-pass redeals use `dummy_ctype = "high"` (simulation.py:426), logged as `contract="high"` in JSONL. Extraction code counts these in `by_contract["high"]["deals_total"]` but skips adding points (bidder_position is None), deflating net_eppd/bid_rate for "high" contract. | ✅ Traced: simulation.py:426 → line 810 → log_hand_end:880 → extraction line 77-81 |
| F2 | HIGH | `by_contract` silently dropped in `--single-seat` mode. Merge dict (line 420-424) only aggregates 3 keys; `by_contract` from `_parse_jsonl_points` return is ignored. | ✅ Confirmed: merge loop lines 463-467 only touch 3 keys |
| F3 | MEDIUM | Per-contract `bid_rate` is vacuously 1.0 for suit/low (after F1 fix). Every deal with contract=X inherently had a bid, so denominator=numerator. | ✅ Semantic consequence of per-contract filtering |
| F4 | MEDIUM | Fixture `bidders_by_contract` has hand-crafted values (e.g., bid_rate=0.4667 for suit) that extraction code can't produce. Tests validate tables.py consumption, not extraction correctness. | ✅ No test covers `_parse_jsonl_points` directly |
| F5 | LOW | No schema version bump for `comparator_cis_v1`. | Additive, optional |
| F6 | PROCESS | Base branch targets merged `fix/reporting-refactor-status-correction`. | ✅ PR metadata confirms |

## Fix Plan

### Step 1: Retarget base branch
```bash
gh pr edit 909 --base main
```

### Step 2: Fix F1 — All-pass "high" poisoning

**File:** `scripts/internal/extract_comparator_cis.py`

**Change:** In `_parse_jsonl_points`, move per-contract `deals_total` increment
to AFTER the all-pass check. Only count deals in per-contract buckets if they
have a winning bid (i.e., are not all-pass redeals).

```python
# BEFORE (buggy): counts all-pass as "high"
deals_total += 1
contract = record.get("contract")
if contract in by_contract:
    by_contract[contract]["deals_total"] += 1

# Skip all-pass redeals
if winning_bid is None or bidder_position is None:
    continue

# AFTER (fixed): only count in per-contract after all-pass check
deals_total += 1
contract = record.get("contract")

winning_bid = record.get("winning_bid")
bidder_position = record.get("bidder_position")

# Skip all-pass redeals (no winning bid or bidder)
if winning_bid is None or bidder_position is None:
    continue

# Only count in per-contract for real bids (not all-pass)
if contract in by_contract:
    by_contract[contract]["deals_total"] += 1
```

**Consequence:** After this fix, per-contract `deals_total` = per-contract
`hands_with_bids`, making `bid_rate` = 1.0 for all contracts. This is
technically correct but uninformative — see Step 4 for documentation.

### Step 3: Fix F2 — Wire `by_contract` through single-seat merge

**File:** `scripts/internal/extract_comparator_cis.py`

**Change:** Add `by_contract` to the merged dict initialization and aggregate
it from each seat run.

```python
# Initialize merged with by_contract
merged = {
    "bidder_team_points": [],
    "net_bidder_team_points": [],
    "deals_total": 0,
    "by_contract": {
        ct: {"bidder_team_points": [], "net_bidder_team_points": [], "deals_total": 0}
        for ct in ("suit", "high", "low")
    },
}

# In seat loop, merge by_contract:
for ct in ("suit", "high", "low"):
    seat_ct = seat_data.get("by_contract", {}).get(ct, {})
    merged["by_contract"][ct]["bidder_team_points"].extend(
        seat_ct.get("bidder_team_points", [])
    )
    merged["by_contract"][ct]["net_bidder_team_points"].extend(
        seat_ct.get("net_bidder_team_points", [])
    )
    merged["by_contract"][ct]["deals_total"] += seat_ct.get("deals_total", 0)
```

### Step 4: Fix F4 — Add extraction-level test with synthetic JSONL

**File:** `tests/unit/test_extract_comparator_cis.py` (new) or add to
existing test file.

**Test:** Create synthetic JSONL with:
- Normal suit/high/low bid hands
- All-pass redeals (winning_bid=None/0, bidder_position=None, contract="high")

Verify:
- `by_contract["high"]["deals_total"]` excludes all-pass hands
- `by_contract["suit"]["deals_total"]` counts only suit-contract deals
- Per-contract bid_rate = 1.0 for all contracts (expected after F1 fix)
- Pooled `deals_total` includes all-pass hands (unchanged behavior)

### Step 5: Document F3 — bid_rate semantics

Add a brief docstring note in `_compute_bidder_metrics` or in the per-contract
metrics section clarifying that per-contract bid_rate is always 1.0 by
construction (every deal in a contract bucket had a bid).

### Step 6 (optional): Schema annotation

Add `"bidders_by_contract"` to the schema string or bump to `comparator_cis_v2`.
Low priority — additive field, backwards-compatible.

## Plan Review Amendments

Incorporated from plan-reviewer findings (R1, P2, P5, P15, P2, P6, P7):

1. **R1 (CRITICAL):** Step 4 test MUST explicitly set `contract="high"` for
   all-pass records. The `_make_hand_end` helper defaults to `contract="suit"`,
   so without this the regression test would pass on unfixed code.

2. **P15:** Steps 2 and 3 are NOT safely independent at commit granularity.
   If F1 lands without F2, single-seat merge silently drops `by_contract`.
   Both MUST land atomically (same commit).

3. **P5:** The non-single-seat path (lines 471-489) already returns
   `by_contract` from `_parse_jsonl_points` and stores it directly in
   `all_data[name]`. No change needed — `by_contract` flows through
   naturally in non-single-seat mode.

4. **P2 (line 40):** The code snippet was illustrative. Implementation must
   restructure the existing loop body — move the `contract` read and
   per-contract increment below the all-pass guard, not duplicate variables.

5. **P2 (line 119):** Docstring note belongs in `_parse_jsonl_points` or at
   the per-contract call site, not in `_compute_bidder_metrics` (which handles
   both pooled and per-contract data).

6. **P6:** Add acceptance criterion for non-single-seat path.

7. **P7:** Promote schema annotation from optional to recommended.

## Execution Order

1. Step 1 (retarget) — independent, first
2. Steps 2+3 (F1+F2 fixes) — **atomic**, single commit
3. Step 4 (tests) — depends on Steps 2+3 (tests verify fixed behavior)
4. Steps 5+6 (docs + schema) — after tests pass
5. Tier 2 validation (`make check-quiet`)

## Acceptance Criteria

- [ ] All-pass redeals do NOT inflate `by_contract["high"]["deals_total"]`
- [ ] `--single-seat` mode produces `bidders_by_contract` in output
- [ ] Non-single-seat mode also produces `bidders_by_contract` in output
- [ ] Unit test with synthetic JSONL covers all-pass (contract="high") + real bids
- [ ] `make check-quiet` passes
- [ ] Base branch is `main`

## Outcome

**Completed 2026-03-18.** All fixes pushed to PR #909 branch `fix/behavior-by-contract-faceting`.

Commit `5a2fc88`:
- F1 fix: per-contract tracking moved after all-pass guard (lines 79-112)
- F2 fix: `by_contract` wired through single-seat merge (lines 445-512)
- Schema bumped to `comparator_cis_v2`
- Docstring added to `_parse_jsonl_points`
- 3 new regression tests: `test_by_contract_basic`, `test_all_pass_does_not_poison_high`,
  `test_per_contract_bid_rate_is_one`
- Branch cleaned from 18 stale stacked-base commits down to 3 focused commits
- Base retargeted from merged `fix/reporting-refactor-status-correction` to `main`
- `make check-quiet` passes, all 145 rung_tables tests + 9 extraction tests pass
