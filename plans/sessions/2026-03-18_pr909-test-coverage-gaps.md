# PR #909 Post-Merge Test Coverage Gaps

**Date:** 2026-03-18
**Parent PR:** #909 (`feat: per-contract extraction in comparator CIs pipeline`)
**Trigger:** Post-merge review identified 3 WARNING-level test coverage gaps

## Context

PR #909 added per-contract extraction to `scripts/internal/extract_comparator_cis.py`.
All correctness bugs were fixed pre-merge (plan: `plans/sessions/2026-03-18_pr909-review-fixes.md`).
Post-merge review found 3 untested behaviors — all code paths are correct but lack
regression protection.

## Findings to Address

| # | Finding | Risk | File |
|---|---------|------|------|
| G1 | No test for absent `contract` field in JSONL records (pre-contract-field era logs) | Low — `.get("contract")` returns `None`, `None not in by_contract` is `True`, silently excluded | `test_extract_comparator_cis.py` |
| G2 | Schema version bump `comparator_cis_v1` → `v2` not verified by test assertion | Low — string is hardcoded at line 675, but no test locks it | `test_extract_comparator_cis.py` |
| G3 | No CLI integration test for non-single-seat path asserting `bidders_by_contract` in output JSON | Medium — the non-single-seat path flows `by_contract` through naturally (line 529) but has no end-to-end coverage | `test_extract_comparator_cis.py` |

## Plan

### Step 1: G1 — Test absent `contract` field

**Where:** `tests/unit/test_extract_comparator_cis.py`, class `TestParseJsonlPoints`

**Test:** `test_missing_contract_field_excluded_from_by_contract`
- Create synthetic JSONL with 3 records: 1 suit, 1 high, 1 with NO `contract` key
- All three have valid `winning_bid` and `bidder_position` (not all-pass)
- Assert `by_contract["suit"]["deals_total"] == 1`
- Assert `by_contract["high"]["deals_total"] == 1`
- Assert `by_contract["low"]["deals_total"] == 0`
- Assert pooled `deals_total == 3` (missing-contract record still counted in pool)

**Helper change:** `_make_hand_end` currently defaults `contract="suit"`. Add
`contract=_SENTINEL` pattern so caller can explicitly omit the field by passing
`contract=None`. When `contract is None`, don't include the key in the record dict.

### Step 2: G2 — Assert schema version string

**Where:** `tests/unit/test_extract_comparator_cis.py`, new class `TestSchemaVersion`

**Test:** `test_output_schema_is_v2`
- Import the module
- Assert that the schema string `"comparator_cis_v2"` appears in `main` function source
  OR (preferred) run a minimal CLI invocation and check `output["schema"]`
- Since `main()` requires real filesystem args, the simplest approach: add this to
  an existing CLI test class (`TestCLISkipRunContract`) or create a focused subprocess test

**Pragmatic approach:** Add the assertion to the G3 integration test (Step 3) since that
test already produces output JSON. Check `output["schema"] == "comparator_cis_v2"`.

### Step 3: G3 — CLI integration test for non-single-seat path

**Where:** `tests/unit/test_extract_comparator_cis.py`, class `TestCLISkipRunContract`
or new class `TestCLINonSingleSeat`

**Test:** `test_non_single_seat_produces_bidders_by_contract`
- Create 2 synthetic bidder run directories matching pattern
  `auction_comparator_{name}_{seed}_{timestamp}`
- Each contains `game_log.jsonl` with suit + high + low records
- Each contains `meta.json` with matching seed
- Create a battery JSON referencing both bidders
- Run CLI via subprocess: `python extract_comparator_cis.py --artifacts-dir ... --runs-dir ... --seed 42 --n-bootstrap 100 --output ...`
  (no `--single-seat` flag)
- Parse output JSON
- Assert `"bidders_by_contract"` key exists
- Assert each contract type has expected `deals_total`
- Assert `output["schema"] == "comparator_cis_v2"` (covers G2)

**Helper:** Use `_make_meta_json` (line 85) for meta.json creation. Create a
minimal battery JSON with `net_eppd` and `eppd` values matching what the synthetic
JSONL will produce, so validation passes (or use `--force`).

## Execution Order

1. Step 1 (G1) — unit test, no dependencies
2. Step 3 (G3 + G2) — CLI integration test, independent of Step 1
3. Tier 1 validation: `uv run python -m pytest tests/unit/test_extract_comparator_cis.py -v`
4. Tier 2 validation: `make check-quiet`

## Acceptance Criteria

- [ ] Missing `contract` field records excluded from `by_contract` but counted in pool
- [ ] Schema string `"comparator_cis_v2"` locked by test assertion
- [ ] Non-single-seat CLI path produces `bidders_by_contract` in output
- [ ] All existing tests still pass
- [ ] `make check-quiet` passes

## Outcome

**Completed 2026-03-18.** All 3 coverage gaps addressed in a single commit.

- G1: `test_missing_contract_field_excluded_from_by_contract` — verifies absent `contract`
  field records are excluded from per-contract buckets but counted in pooled total
- G2: Schema assertion `output["schema"] == "comparator_cis_v2"` embedded in G3 CLI test
- G3: `test_non_single_seat_produces_bidders_by_contract` — full CLI integration test
  with synthetic run directories, verifying `bidders_by_contract` in output and correct
  per-contract deal counts

45 tests pass (43 original + 2 new). `make check-quiet` passes.
