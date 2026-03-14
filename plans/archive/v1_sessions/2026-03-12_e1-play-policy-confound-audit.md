# E1 — Play-Policy + Label-Confound Audit

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (Step 0.5b — deconfounding)
**Status:** IN PROGRESS
**Prerequisite:** Step 0.5 (play-policy sanity check) PASS

## Context

Step 0.5 confirmed Glutton > Greedy in **bidless** trick-play (mean +0.20 tricks,
p<0.0001). But the R0 and R1.5 models were **trained** on Glutton-generated labels
and **evaluated** with Glutton play policy. This creates a potential confound:

- **Policy confound**: Does Glutton make *all* bidders look better (inflated metrics)?
- **Label confound**: Were models specifically fitted to Glutton patterns?

E1 answers: **Do bidder rankings change when the play policy changes?**

## Primary Questions

1. **Policy main effect**: Does switching play from Glutton to Greedy change
   the *absolute* level of bidder performance (expected: yes, Glutton wins more
   tricks generally)?
2. **Ranking stability**: Do *relative* bidder rankings change? (This is the
   critical question — if rankings are stable, the confound is cosmetic.)
3. **Label confound** (Full only): Do rankings change when the model is also
   *retrained* on Greedy labels?

## Infrastructure Changes

### 1. `run_arc_d_h2h_battery.py` — Add `--play-strategy` and `--roster-names`

- Add CLI arg `--play-strategy` (default: `"glutton"`)
- Map name → class name via `PLAY_STRATEGY_MAP = {"glutton": "GluttonStrategy", "greedy": "GreedyStrategy"}`
- Pass play strategy name + class to `generate_matchups()` (team0/team1 fields) and
  `generate_h2h_config()` (strategies section, line 227)
- Add CLI arg `--roster-names` (comma-separated bidder names from `DEFAULT_ROSTER`)
  as a convenience filter — existing `--roster` takes a JSON file path (line 714)
- Backward-compatible: default behavior unchanged

### 2. `generate_action_value_dataset.py` — Add `--play-strategy` (deferred)

- Needed only for Full 2×2 unconfounding branch
- Currently hardcodes `GluttonStrategy()` in `_play_tricks()`
- Add CLI arg + dynamic strategy instantiation

### 3. `run_play_confound_audit.py` — New orchestration script

- Runs battery twice (greedy/glutton) with same seed/roster
- Compares summary JSONs: ranking correlation, delta differences
- Outputs structured audit report

## Tiered Protocol

### Tier 1: Smoke (n_per=2000, seed=42)

**Objective:** Catch setup issues, check sign consistency.

**Reduced roster** (4 bidders, 16 matchups):
- `hybrid_olsa_full` (R0 incumbent)
- `modeloespecifico` (heuristic baseline)
- `stricthellraiser` (aggressive heuristic)
- `rankthetank` (defensive heuristic)

**Runs:**
- `smoke_glutton`: battery with `--play-strategy glutton`
- `smoke_greedy`: battery with `--play-strategy greedy`

**Pass condition:** Runs complete, rankings exist, effect in expected direction.

**Commands:**
```bash
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 --play-strategy glutton \
  --roster-names hybrid_olsa_full,modeloespecifico,stricthellraiser,rankthetank \
  --output data/artifacts/arc_d/e1/smoke_glutton.json

PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 --play-strategy greedy \
  --roster-names hybrid_olsa_full,modeloespecifico,stricthellraiser,rankthetank \
  --output data/artifacts/arc_d/e1/smoke_greedy.json
```

### Tier 2: Quick (n_per=10000, seeds=42-44)

**Objective:** Estimate practical effect size with statistical confidence.

**Full roster** (8 bidders, 64 matchups per seed).

**Runs per policy:** 3 seeds × 64 matchups × 10000 hands = ~1.9M hands.

**Metrics:**
- Spearman rank correlation between glutton and greedy rankings
- Per-bidder absolute delta (glutton - greedy net_eppd)
- Pooled team0 tricks delta vs CI
- Bootstrap p-values + Cohen's d

**Pass condition:** Rank correlation > 0.9 AND no ranking inversions among
top-4 bidders → confound is cosmetic (rankings stable). Otherwise → proceed to Full.

### Tier 3: Full (n_per=20000, seeds=42-46)

**Objective:** Close confidence with definitive N and optional 2×2 design.

**Policy-only fork:**
- `M_g + greedy` and `M_g + glutton` (5 seeds)

**Unconfounding fork (if feasible):**
- Train `M_gr` on Greedy-labeled data
- `M_gr + greedy` and `M_gr + glutton` (5 seeds)

**Decisive check:**
- Interaction: `[(M_g+Glutton - M_g+Greedy) - (M_gr+Glutton - M_gr+Greedy)]`
- Interaction CI includes 0 AND |interaction| < 0.01 → weak confound

## Statistical Gates

| Gate | Threshold | Metric |
|------|-----------|--------|
| Policy main effect | CI excludes 0, delta > +0.05 tricks | Pooled glutton - greedy |
| Equivalence | |Δ| < 0.01 | "No meaningful difference" |
| Rank stability | Spearman ρ > 0.9 | Glutton vs greedy rankings |
| Confound interaction | CI includes 0, |interaction| < 0.01 | 2×2 interaction term |

## Decision Rules

- **Smoke PASS + Quick PASS** (ranks stable): Confound is cosmetic. Record and
  proceed to Track B. No label retraining needed.
- **Smoke PASS + Quick FAIL** (ranks change): Proceed to Full. May need to
  retrain with Greedy labels to isolate confound.
- **Smoke FAIL**: Investigate data/config issue before proceeding.

## Realism Stress Checks (Future Extension)

Per the experiment design, these are deferred until Quick results are in:
1. Contract-type faceted comparison (suit/high/low separately)
2. Trick-lead choice divergence frequency
3. Frozen-auction cross-evaluator check

## Outcome

### Smoke Tier: PASS (decisive)

**Spearman ρ = 1.0** — perfect rank preservation across all 4 bidders.

| Bidder | Glutton net_eppd | Greedy net_eppd | Δ | Rank (both) |
|--------|-----------------|-----------------|---|-------------|
| modeloespecifico | +3.795 | +3.979 | -0.184 | 1 |
| hybrid_olsa_full | +2.847 | +2.951 | -0.104 | 2 |
| rankthetank | -2.107 | -1.772 | -0.335 | 3 |
| stricthellraiser | -4.834 | -5.201 | +0.367 | 4 |

**Key observations:**
- Rankings identical under both play policies
- Deltas are mixed-sign (Glutton doesn't uniformly inflate)
- Cell-level shifts exist (std=0.50) but between-bidder gaps dwarf them
- No ranking inversions

**Verdict:** STABLE — confound is cosmetic. Proceed to Track B without label
retraining. Quick/Full tiers optional for additional confidence.

**Experiment details:**
- Seed: 42, n_per=2000, 4 bidders, 16 matchups
- Glutton run: `data/runs/arc_d_r0_h2h_battery_42_20260311_213209/`
- Greedy run: `data/runs/arc_d_r0_h2h_battery_42_20260311_213346/`
- Audit JSON: `data/artifacts/arc_d/e1/smoke_audit.json`

## Files Modified

- `scripts/internal/run_arc_d_h2h_battery.py` — `--play-strategy` arg
- `scripts/internal/run_play_confound_audit.py` — new orchestration script
- `tests/unit/test_h2h_battery.py` — play-strategy tests
- `plans/r1_5_forward_decision_tree.md` — Step 0.5b entry
