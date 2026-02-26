# Arc D Wave 2B — Review Fix Plan

> 6 issues across PRs #395 and #396. PR #394 (docs) is clean — merge first.

## Issue Inventory

| # | PR | File | Severity | Summary |
|---|-----|------|----------|---------|
| 1 | #395 | `src/bid_euchre/models/train_hybrid_olsa.py:203-234` | **Blocker** | Off/def split uses `seat.isin([0,2])` (team0/team1), not declarer-vs-defender |
| 2 | #395 | `src/bid_euchre/models/train_hybrid_olsa.py:216-217` | Major | Off/def residual variance skips `0 < σ² < 25` plausibility guard |
| 3 | #395 | `src/bid_euchre/models/train_hybrid_olsa.py:243-249` | Major | `training_metrics` populated from flat fit, not off/def sub-models |
| 4 | #396 | `src/bid_euchre/diagnostics/semantic_gate.py:1039-1043` | Major | `check_dual_arm_coherence` keys by `check_id` only — collapses faceted checks |
| 5 | #396 | `src/bid_euchre/reporting/arc_d_report.py:110-118`, `scripts/internal/generate_arc_dashboard.py:61-84` | Major | Attribution-gap trend is prose-only — no computed metric |
| 6 | #396 | `tests/unit/test_arc_d_reporting.py:198-204` | Major | Test hits bid-rate ceiling before dominance check — zero coverage of dominance path |

---

## Fix 1 (Blocker): Off/def split must use declaring-team label, not seat parity

**Problem:**
Line 205: `off_mask = train_df["seat"].isin([0, 2])` partitions by team, not by declaring role.
In bidless data, there IS no declaring team — all seats are symmetric.
The plan (`arc_d_execution_plan.md:1695`) says "fit separate OLS on declaring-team rows vs defending-team rows."

**Root cause:**
The bidless dataset join (`datasets/join.py:21-23`) assigns `tricks_won` by team (seats 0,2 → tricks_team0; seats 1,3 → tricks_team1), but does not record which team declared.
In a bidless context, no team declares — the concept doesn't exist until auction data (PR-R1a).

**Fix approach:**
The off/def training code should use a `"declaring"` column (boolean or 0/1) to partition rows, NOT seat indices.

1. Add a guard at the top of the `offensive_defensive` block:
   ```python
   if offensive_defensive:
       if "declaring" not in train_df.columns:
           raise ValueError(
               "offensive_defensive=True requires a 'declaring' column "
               "in the training data. Bidless datasets lack declaring-team "
               "labels — use auction data (PR-R1a) for off/def training."
           )
       off_mask = train_df["declaring"].astype(bool)
       def_mask = ~off_mask
   ```
2. Remove the `seat.isin([0, 2])` line entirely.
3. Update the comment from "Split into declaring (seats 0,2) and defending (seats 1,3)" to "Split into declaring and defending rows using the 'declaring' column."

**Test changes:**
- `test_training_offdef_produces_submodels` in `test_offdef_architecture.py` must add a `"declaring"` column to its synthetic data (e.g., randomly assign ~50% of rows as declaring).
- Add a new test: `test_training_offdef_rejects_bidless_data` — verify `ValueError` when `declaring` column is missing.

**Files modified:**
- `src/bid_euchre/models/train_hybrid_olsa.py` (lines 203–206)
- `tests/unit/test_offdef_architecture.py` (test data helper + 1 new test)

---

## Fix 2 (Major): Off/def residual variance plausibility guard

**Problem:**
Lines 216–217 compute `resid_off` and `resid_def` but skip the `0 < σ² < 25` guard that the flat path has at line 182.

**Fix:**
After lines 216–217, add the same guard for both sub-variances:

```python
resid_off = float(np.var(y_off - (X_off @ w_off + b_off)))
resid_def = float(np.var(y_def - (X_def @ w_def + b_def)))

for role, rv in [("offensive", resid_off), ("defensive", resid_def)]:
    if not (0 < rv < 25):
        raise ValueError(
            f"Residual variance out of bounds for {contract_family}/{role}: "
            f"{rv:.4f} (expected 0 < σ² < 25)"
        )
```

**Test changes:**
- Add `test_training_offdef_rejects_bad_variance` — craft synthetic data where one sub-model produces out-of-bounds variance, assert `ValueError`.

**Files modified:**
- `src/bid_euchre/models/train_hybrid_olsa.py` (after line 217)
- `tests/unit/test_offdef_architecture.py` (+1 test)

---

## Fix 3 (Major): Off/def training metrics must reflect sub-model fit

**Problem:**
Lines 243–249 populate `training_metrics[contract_family]` with `metrics_train["r2"]` and `metrics_test["r2"]` from the FLAT fit (computed at lines 190–191, before the `if offensive_defensive:` branch). When off/def is active, these metrics are stale — they describe the flat model, not the off/def sub-models.

**Fix:**
When `offensive_defensive=True`, recompute metrics for each sub-model and report them:

```python
if offensive_defensive:
    # ... existing off/def fitting code ...

    # Compute off/def-specific metrics on train subsets
    y_pred_off = X_off @ w_off + b_off
    y_pred_def = X_def @ w_def + b_def
    metrics_off = _compute_metrics(y_off, y_pred_off)
    metrics_def = _compute_metrics(y_def, y_pred_def)

    training_metrics[contract_family] = {
        "r2_train_offensive": metrics_off["r2"],
        "r2_train_defensive": metrics_def["r2"],
        "mae_train_offensive": metrics_off["mae"],
        "mae_train_defensive": metrics_def["mae"],
        "r2_train_flat": metrics_train["r2"],  # Keep flat as reference
        "r2_test": metrics_test["r2"],          # Test is always flat (full data)
        "mae_test": metrics_test["mae"],
        "n_train": len(train_df),
        "n_train_offensive": len(X_off),
        "n_train_defensive": len(X_def),
        "n_test": len(test_df),
    }
else:
    # ... existing flat path ...
    training_metrics[contract_family] = {
        "r2_train": metrics_train["r2"],
        "r2_test": metrics_test["r2"],
        # ... etc ...
    }
```

Move the `training_metrics` population INSIDE the `if/else` branches instead of after them.

**Test changes:**
- Update `test_training_offdef_produces_submodels` to assert `training_metrics` contains off/def keys (e.g., `r2_train_offensive`).

**Files modified:**
- `src/bid_euchre/models/train_hybrid_olsa.py` (lines 203–249, restructure)
- `tests/unit/test_offdef_architecture.py` (additional assertions)

---

## Fix 4 (Major): `check_dual_arm_coherence` must use composite key

**Problem:**
Lines 1039–1043 build dicts keyed by `check_id` alone:
```python
primary_checks = {c["check_id"]: c["status"] for c in gate_primary.get("checks", [])}
```
But many checks are faceted by `contract_type` — e.g., `r_squared_floor` appears 3 times (suit/high/low) with different statuses. Using `check_id` as the sole key collapses these to the LAST value, undercounting divergence.

**Fix:**
Use a composite key `(check_id, contract_type)`:

```python
def _check_key(c: dict) -> tuple:
    """Composite key for check deduplication: (check_id, contract_type)."""
    return (c["check_id"], c.get("contract_type"))

primary_checks = {_check_key(c): c["status"] for c in gate_primary.get("checks", [])}
secondary_checks = {_check_key(c): c["status"] for c in gate_secondary.get("checks", [])}
```

The rest of the function (shared_ids, mismatch counting) works unchanged since it operates on dict keys.

**Test changes:**
- Add `test_dual_arm_coherence_faceted_checks` — supply gate artifacts with per-contract-type checks where facets diverge, verify mismatch count is correct (not collapsed).
- Existing `test_dual_arm_coherence_low_divergence_pass` and `test_dual_arm_coherence_high_divergence_warn` should still pass (they use non-faceted check data).

**Files modified:**
- `src/bid_euchre/diagnostics/semantic_gate.py` (lines 1039–1043)
- `tests/unit/test_arc_d_reporting.py` (+1 test)

---

## Fix 5 (Major): Attribution-gap must compute actual metric, not just prose

**Problem:**
`arc_d_report.py:110-118` emits descriptive text about attribution gap but never computes it from the bundle data. The dashboard (`generate_arc_dashboard.py:61-84`) shows a table with features and SHAs but no `net_eppd` values or attribution gap column.

The plan (`arc_d_execution_plan.md:1379,1389`) requires "attribution_gap tracking" and "attribution_gap trend."

**Fix for `arc_d_report.py`:**
Read `net_eppd` from both arms in the bundle and compute the gap:

```python
# --- Attribution gap ---
sections.append("## Attribution Gap")
sections.append("")
olsa_eppd = bundle.get("olsa", {}).get("net_eppd")
full_eppd = bundle.get("olsa_full", {}).get("net_eppd")
if olsa_eppd is not None and full_eppd is not None:
    gap = full_eppd - olsa_eppd
    sections.append(f"| Arm | net_eppd |")
    sections.append(f"|-----|----------|")
    sections.append(f"| OLSa (constrained) | {olsa_eppd:.4f} |")
    sections.append(f"| OLSa_Full (promotional) | {full_eppd:.4f} |")
    sections.append(f"| **Attribution Gap** | **{gap:+.4f}** |")
    sections.append("")
    if gap > 0:
        sections.append("Positive gap: feature selection improves bidding quality.")
    elif gap < 0:
        sections.append("Negative gap: constrained arm outperforms — investigate overfitting.")
    else:
        sections.append("Zero gap: arms perform identically.")
else:
    sections.append("*Attribution gap not yet available — eval results pending.*")
sections.append("")
```

This requires passing the `bundle` dict into `generate_arc_d_rung_report()` (currently it only receives paths to sub-components). Check the function signature and add `bundle` as a parameter if needed.

**Fix for `generate_arc_dashboard.py`:**
Add `net_eppd` and `Attribution Gap` columns to the dashboard table:

```python
sections.append(
    "| Rung | OLSa net_eppd | OLSa_Full net_eppd | Gap"
    " | OLSa Features | OLSa_Full Features | Bundle Path |"
)
# ... per-row: extract net_eppd from each arm, compute gap ...
```

**Test changes:**
- Update `test_rung_report_has_sections` to verify the attribution gap table is present when bundle has `net_eppd` values.
- Add `test_rung_report_attribution_gap_pending` — verify placeholder text when `net_eppd` is missing.
- Update `test_dashboard_reads_bundles` to verify `net_eppd` column appears.

**Files modified:**
- `src/bid_euchre/reporting/arc_d_report.py` (lines 110–118, plus function signature)
- `scripts/internal/generate_arc_dashboard.py` (table header + row format)
- `tests/unit/test_arc_d_reporting.py` (+2 tests, 1 updated)

---

## Fix 6 (Major): Test must isolate dominance detection path

**Problem:**
`test_bid_distribution_single_contract_dominates` (line 198–204) creates data via `_make_balanced_df()` where `bid_won = (seat == 0)`, so every hand has exactly 1 bid → `bid_rate = 1.0`. The rate check (`bid_rate > max_rate=0.95`) fires at line 980 BEFORE the dominance check at line 997. The test asserts `FAIL` but validates the wrong failure path.

**Fix:**
Adjust the test data to have a realistic bid rate (~50%) while concentrating all bids on a single contract type:

```python
def test_bid_distribution_single_contract_dominates():
    """Single contract > 80% of bids -> FAIL via dominance check."""
    df = _make_balanced_df()
    # Set ~50% bid rate to pass the rate check
    rng = np.random.RandomState(99)
    no_bid_hands = set(rng.choice(df["hand_id"].unique(), size=250, replace=False))
    df["bid_won"] = False
    bid_hands = set(df["hand_id"].unique()) - no_bid_hands
    # Assign bids to seat 0 only for non-excluded hands
    df.loc[(df["hand_id"].isin(bid_hands)) & (df["seat"] == 0), "bid_won"] = True
    # Force ALL bids to "suit" contract — 100% dominance
    df.loc[df["bid_won"], "contract_type"] = "suit"
    result = check_bid_distribution_sanity(df, "FULL")
    assert result["status"] == "FAIL"
    assert "dominat" in result["detail"].lower()  # Verify correct failure path
```

The key addition is asserting on `result["detail"]` to confirm the failure came from the dominance check, not the rate check.

**Files modified:**
- `tests/unit/test_arc_d_reporting.py` (lines 198–204)

---

## Execution Plan

### Merge Order
1. **PR #394 (I3 docs)** — clean, merge immediately
2. **PR #395 (R5a)** — apply fixes 1, 2, 3, rebase on main (after #394), push, re-verify
3. **PR #396 (I4)** — apply fixes 4, 5, 6, rebase on main (after #394), push, re-verify

PRs #395 and #396 touch disjoint files, so fixes can proceed in parallel.

### Verification
For each fixed PR:
- `make check` must pass
- All new + existing tests green
- `gh pr diff` reviewed for correctness

### Worktrees
- `../Bid-Euchre-arc-d-i3` — PR #394 (no changes needed)
- `../Bid-Euchre-arc-d-r5a` — PR #395 (fixes 1, 2, 3)
- `../Bid-Euchre-arc-d-i4` — PR #396 (fixes 4, 5, 6)
