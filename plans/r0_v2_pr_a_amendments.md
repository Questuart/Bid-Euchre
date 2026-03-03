# R0 v2 PR-A Amendments

Post-review amendments to the R0 Canonical v2 plan, applied during PR-A
(#493). Addresses six review findings (F1–F6) from plan quality review.

---

## Amendment A — Lambda Injection (F1: HIGH)

**Problem:** Config-pinned YAML entries for `HybridOLSaBidder` had
`bid_level_search: true` but no `risk_lambda`. After Track D selects
the optimal lambda, there was no specified mechanism to inject it into
canonical battery runs.

**Fix (config-pinned approach):** Add explicit `risk_lambda: 0.0` as a
placeholder in all canonical config surfaces:

| Config location | File |
|----------------|------|
| Auction comparator | `experiments/configs/auction_comparator.yaml` |
| C33 ablation | `experiments/configs/arc_d_r0_c33_ablation.yaml` |
| H2H battery roster | `scripts/internal/run_arc_d_h2h_battery.py` (`DEFAULT_ROSTER`) |

**Lambda flow:** After Track D selects the optimal lambda value, all three
locations must be updated with the selected value before running Tracks A/B/C.
This is consistent with the config-pinning principle — the lambda is explicitly
visible in YAML diffs and code diffs, keeping artifacts immutable.

**Status:** Applied in PR-A commit `e4f0127`.

---

## Amendment B — Schema Versioning for Contract-Type Metrics (F3: HIGH)

**Problem:** The plan calls for adding per-contract-type (CT) metrics to
comparator CI, comparator battery, and H2H summary artifacts. This changes
the artifact shape, but no schema version bump or backward-compatibility
plan existed.

### Current schemas

| Artifact | Script | Schema ID | Line |
|----------|--------|-----------|------|
| Comparator CIs | `scripts/internal/extract_comparator_cis.py` | `comparator_cis_v1` | 591 |
| Comparator battery | `scripts/internal/run_auction_comparator.py` | `arc_d_comparator_v1` | 313 |
| H2H battery summary | `scripts/internal/run_arc_d_h2h_battery.py` | `h2h_battery_v2` | 384 |
| Batch manifest | `scripts/internal/run_auction_comparator.py` | `batch_manifest_v1` | 97 |

### Version bump plan (PR-D scope)

When PR-D adds per-contract-type metrics to extraction outputs:

| Artifact | Current | New | Key addition |
|----------|---------|-----|-------------|
| Comparator CIs | `comparator_cis_v1` | `comparator_cis_v2` | `by_contract_type` dict per bidder with suit/high/low breakout |
| Comparator battery | `arc_d_comparator_v1` | `arc_d_comparator_v2` | Per-CT metrics per bidder (if battery gains CT fields) |
| H2H battery summary | `h2h_battery_v2` | `h2h_battery_v3` | Per-CT bid_rate, make_rate, net_eppd per matchup |
| Batch manifest | `batch_manifest_v1` | Unchanged | Manifest doesn't carry metric data |

### Backward compatibility strategy

1. **Readers/loaders:** Accept both old and new schema versions.
   Pattern: `if schema in ("comparator_cis_v1", "comparator_cis_v2"):`.
   Old artifacts load without CT fields; new artifacts include them.

2. **Bundle schema:** `arc_d_rung_bundle_v1` is unchanged. The bundle
   references artifact file paths, not their internal schemas. Bundle
   validation checks file existence, not artifact schema version.

3. **CT validator gating:** `validate_contract_type_breakout()` checks
   the artifact's `schema` field first. It only validates CT presence
   for v2+/v3+ schemas and silently skips older schemas.

4. **Tightening timeline:** After all v2 canonical artifacts are produced
   and validated, a follow-up PR may tighten readers to require new schemas
   only. This is non-blocking and can be deferred to post-freeze cleanup.

### CT metrics schema shape (for reference)

```json
{
  "by_contract_type": {
    "suit": {"bid_rate": 0.45, "make_rate": 0.72, "net_eppd": 0.85},
    "high": {"bid_rate": 0.01, "make_rate": 0.40, "net_eppd": -0.12},
    "low":  {"bid_rate": 0.01, "make_rate": 0.38, "net_eppd": -0.15}
  }
}
```

For CI artifacts, each CT entry also includes `ci_lower` and `ci_upper`.

**Status:** Plan documented here. Code changes deferred to PR-D.

---

## Amendment C — C33 3-Arm Attribution Design (F4: MEDIUM)

**Problem:** PR-A added `bid_level_search: true` to `hybrid_olsa` in
the C33 config. This conflates the Gaussian EV wrapper effect with the
bid-level search effect — a positive C33 result could be attributed to
either innovation or both.

**Fix:** Expand C33 from 2-arm/4-matchup to 3-arm/9-matchup design:

| Arm | Bidder class | bid_level_search | What it tests |
|-----|-------------|-----------------|---------------|
| `olsa` | OLSaBidder | N/A (always floor) | Floor baseline |
| `hybrid_olsa_floor` | HybridOLSaBidder | `false` | Gaussian EV wrapper only |
| `hybrid_olsa` | HybridOLSaBidder | `true` | Wrapper + bid-level search |

### Attribution decomposition

| Comparison | Measures |
|-----------|----------|
| `hybrid_olsa_floor - olsa` | Wrapper effect (Gaussian EV vs floor-only) |
| `hybrid_olsa - hybrid_olsa_floor` | Search effect (exhaustive vs single-level) |
| `hybrid_olsa - olsa` | Combined effect (full hybrid policy vs baseline) |

### Matchup matrix (9 total)

3 self-play + C(3,2) x 2 directional cross = 3 + 6 = 9 matchups.
At n_per=10,000: 9 x 10,000 = 90,000 hands (was 40,000 with 2-arm design).

All three arms use the same artifact (`hybrid_r0.json`, constrained arm)
so differences are attributable only to the decision layer, not the model.

**Status:** Applied in PR-A commit `e4f0127`.

---

## Amendment D — Threshold→Lambda Sequential Ordering (Post-PR-B Review)

**Context:** The R0 v2 session plan (Phase 3a/3b) initially grouped threshold
and lambda tuning as potentially parallel. The pre-registered protocols
(`r0_v2_threshold_protocol.md` §4, `r0_v2_lambda_tuning_protocol.md` §4)
specify **strict sequential ordering**: threshold first, then lambda.

**Governing decision:** Threshold→lambda sequential is the canonical ordering
for R0 v2 execution. This explicitly overrides any prior "parallel" framing
in session plans or discussion.

**Rationale:** Threshold controls which hands enter the bidding pool (the
selection boundary). Lambda controls the risk penalty applied to hands already
in the pool. Tuning threshold with lambda=0.0 isolates the selection effect.
Then lambda is tuned conditional on the selected threshold, preserving causal
clarity in the 2-stage hyperparameter search.

**Execution sequence:**
1. Track C: Tune `pass_threshold` with `risk_lambda=0.0` → yields `t*`
2. Track D: Tune `risk_lambda` with `pass_threshold=t*` → yields `lambda*`
3. Both values applied to all canonical configs before battery runs

**Status:** Documented here as governing override. Both protocol docs
already specify this ordering.

---

## Resolved Findings (No Code Changes Needed)

| Finding | Severity | Resolution |
|---------|----------|-----------|
| F2: `compute_best_bid()` contract incomplete | HIGH | Already resolved in PR-A initial implementation. Function includes `risk_lambda: float = 0.0` and `seed: int = 42` params. |
| F5: Hardcoded 7→8 migration under-scoped | MEDIUM | Already resolved in PR-A. Tests (6 updated in `test_h2h_battery.py`), notebooks (`40_r0_baseline.py`, `45_comparator_deep_dive.py`), and paired `.ipynb` files all updated. |
| F6: `MASTER_PLAN.md` path inconsistency | LOW | Plan text refers to `MASTER_PLAN.md`; actual repo path is `plans/MASTER_PLAN.md`. Cosmetic; noted in plan amendments section. |
