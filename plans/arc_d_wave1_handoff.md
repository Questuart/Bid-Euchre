# Arc D Wave 1 — Implementation Handoff

**Created:** 2026-02-19
**Status:** Partially implemented, paused for later pickup. **Superseded by v3 plan** -- see reconciliation table below.
**Plan source:** `plans/arc_d_execution_plan.md` (v3, 2026-02-20)

---

## Overview

Arc D advances the OLSa bidder from sparse floor-based decisions to a
risk-adjusted EV bidder across 9 PRs in 5 waves. Wave 1 has 3 parallel
code-only PRs + 1 operational PR.

## Dependency Note

The plan's dependency table (section 2) lists HITL PR-2 (#371) as blocked.
This is **stale** — PR #372 (`feat/semantic-gate`) merged the same work and
is on main. The semantic gate dependency is resolved.

---

## Worktree Status

All 3 worktrees exist and have uncommitted partial work:

### 1. PR-D1a — `../Bid-Euchre-d1a` (branch: `feat/arc-d-d1a`)

**Status: ~90% complete — 8/8 tests pass, needs `make check` + commit**

Files modified/created:
- `scripts/train_olsa.py` — Added `--feature-config` and `--feature-budget` CLI flags (+34 lines)
- `src/bid_euchre/models/train_olsa.py` — Added `feature_config` param to `train_olsa()` (+10 lines)
- `src/bid_euchre/models/feature_selection.py` — **NEW** (104 lines) — `forward_select()` with CV R²
- `tests/unit/test_feature_selection.py` — **NEW** (89 lines) — 8 tests, all passing

**Remaining work:**
- [ ] Run full `SKIP=repo-linter,validate-configs make check` — may have ruff issues
- [ ] Verify backward compat: default (no flags) still uses hardcoded CONTRACT_FEATURES
- [ ] Commit + push + create PR

### 2. PR-D3a — `../Bid-Euchre-d3a` (branch: `feat/arc-d-d3a`)

**Status: ~50% complete — class written, missing wiring + tests**

Files modified:
- `src/bid_euchre/strategy/bidding.py` — Added `TwoStageHybridBidder` class (+131 lines)

**Remaining work:**
- [ ] Add to `src/bid_euchre/strategy/__init__.py` (import + `__all__`)
- [ ] Register in `src/bid_euchre/experiments/config.py`:
  - Import `TwoStageHybridBidder`
  - Add to `BIDDING_POLICY_REGISTRY` as `"TwoStageHybridBidder"`
  - Add to `BIDDING_REQUIRED_PARAMS` with `["artifact_path"]`
- [ ] Create `tests/unit/test_hybrid_bidder.py` (~12 tests per plan H-D3a):
  - loads v2 artifact
  - rejects v1 artifact (ValueError)
  - manual EV calculation matches (6dp)
  - sigma=0 above bid → returns mu
  - sigma=0 below bid → returns -bid_n
  - z-cap at 6.0 prevents overflow
  - all negative EV → PASS action
  - strong hand produces bid
  - risk_lambda=0 matches no-lambda
  - config registration works
  - reads embedded risk_lambda from artifact
  - explicit risk_lambda overrides artifact
- [ ] Run `make check`
- [ ] Commit + push + create PR

### 3. PR-I2 — `../Bid-Euchre-i2` (branch: `feat/arc-d-gate-runner`)

**Status: 0% — worktree created, no code written**

**What to implement:** (full spec in plan section 5, handoff H-I2)

Create `scripts/internal/run_arc_d_gate.py` with:
```python
def should_promote(challenger, control, rung_id, config) -> tuple[str, list[str]]:
```

Tier 1 checks (8, all rungs): split_hash, no_nan_inf, feature_count,
tricks_range, min_sample_size, schema_version, determinism, artifact_integrity

Tier 2 gates (rung-specific):
- R0: auto-promote (all metrics finite)
- R1/R3/R4: improvement gate (eppd > control + max(0.10, 1.5*SE))
- R2: equivalence gate (5 drift bands)
- R4 additional: strict cvar_5 improvement

Guardrails (non-R0): bid_rate [0.15,0.85], make_rate>=0.40, cvar_5 tolerance, dv ratio

Sensitivity gate (R1/R3/R4): both seeds 43+44 reversed → REJECT

Create `tests/unit/test_arc_d_gate.py` with 20+ tests.

**Key imports the gate runner needs:**
- `bid_euchre.models.splits.verify_split_manifest`
- `bid_euchre.models.freeze.verify_frozen`
- `bid_euchre.diagnostics.semantic_gate.compute_semantic_gate` (already merged in #372)

---

## PR-D0 (Operational — Not Started)

**Status: Not started, no worktree**

This is the operational PR: train OLSa-v1 on canonical glutton run, freeze,
run 3-seed evaluation, create auto-promote record and registry doc.

Requires `data/runs/canonical_bidless_dataset_glutton_42_20260204_222713`
(lives in main checkout, gitignored — symlink into worktree).

See plan section 5, handoff H-D0 for full steps.

---

## Key Codebase Findings (from exploration)

These findings save the next agent from re-exploring:

1. **`scripts/train_olsa.py`** is a thin CLI wrapper; core logic is `src/bid_euchre/models/train_olsa.py`
2. **`CONTRACT_FEATURES`** hardcoded at line 32-36 of `train_olsa.py`: suit=[bowers,trump_count,offsuit_aces], high=[offsuit_aces], low=[offsuit_tens_count]
3. **`OLSaBidder`** at lines 680-751 of `bidding.py` — last class in file. Checks `artifact_type == "olsa_v1"`
4. **`BIDDING_POLICY_REGISTRY`** in `config.py` lines 47-56 maps string → class
5. **`BIDDING_REQUIRED_PARAMS`** in `config.py` lines 62-66
6. **`strategy/__init__.py`** exports all bidding classes + `__all__` list
7. **`verify_frozen()`** in `freeze.py` returns bool (True if frozen + hash matches)
8. **`verify_split_manifest()`** in `splits.py` returns bool (re-runs split, checks hashes)
9. **`compute_semantic_gate()`** in `semantic_gate.py` returns dict with checks list
10. **`data/artifacts/` does NOT exist** — needs `mkdir -p` when creating
11. **`scripts/internal/`** exists with 5 existing scripts
12. **`docs/03_TODO/`** exists with 5 existing docs
13. **sklearn is available** (used for KFold in feature_selection.py)
14. **scipy is available** (used for norm.cdf/pdf in TwoStageHybridBidder)

## v1 -> v3 PR ID Reconciliation

The v1 plan (this handoff) used different PR IDs than the v3 execution plan.
This table maps between them for context recovery:

| v1 ID | v1 Concept | v3 ID | v3 Concept | Worktree | Status |
|-------|-----------|-------|-----------|----------|--------|
| PR-D1a | Training pipeline + feature selection | PR-R0a | Hybrid training pipeline + feature selection + arm-mode + bundle | `../Bid-Euchre-d1a` | ~90% (needs v3 alignment: arm-mode, bundle writing) |
| PR-D3a | TwoStageHybridBidder | PR-I1 | HybridOLSaBidder + schema + linter | `../Bid-Euchre-d3a` | ~50% (class name changed, EV formula changed to net-differential) |
| PR-I2 | Gate runner (PROMOTE/REJECT) | PR-I2 | Gate runner (PROMOTED/ADVANCED/HALT) + bundle validator + registry updater | `../Bid-Euchre-i2` | 0% (scope significantly expanded in v3) |
| PR-D0 | R0 baseline lock | PR-R0b | R0 baseline lock (both arms) | none | Not started (expanded: dual-arm, net_eppd, bundles) |
| -- | -- | PR-P0 | Switch metric to net_eppd | -- | NEW in v3 |
| -- | -- | PR-I4 | Reporting extensions + semantic gate additions | -- | NEW in v3 |

### Worktree Recommendations

- **`../Bid-Euchre-d1a`**: Significant v3 delta (arm-mode, bundle writing). Consider starting fresh on a new branch `feat/arc-d-r0a` rather than adapting partial work. Reuse `feature_selection.py` if tests still pass.
- **`../Bid-Euchre-d3a`**: Class renamed from `TwoStageHybridBidder` to `HybridOLSaBidder`, EV formula changed to net-differential. Start fresh on `feat/arc-d-i1`.
- **`../Bid-Euchre-i2`**: No code written. Start fresh on `feat/arc-d-i2` with expanded scope.
- Clean up old worktrees after confirming no reusable code.

## Pickup Instructions (updated for v3)

To resume:
1. Read this file AND `plans/arc_d_execution_plan.md` (v3)
2. Start with PR-P0 (new in v3 -- switch metric to net_eppd)
3. Then PR-I1 (was PR-D3a -- HybridOLSaBidder, start fresh)
4. Then PR-R0a (was PR-D1a -- training pipeline, start fresh with arm-mode)
5. Wave 2: PR-I2, PR-I3, PR-I4, PR-R5a in parallel
6. After Wave 2: update MEMORY.md with PR numbers
