# R0 → R1 Experiment Runs Execution Plan

> **Purpose:** Execute all experiment runs needed to produce R1-ready artifacts.
> All code is merged (C33 #439, C50 #440, D23 #441). This plan is **operations only** —
> no code changes unless a run reveals a bug.
>
> **Estimated wall-clock:** ~15–25 minutes total (mostly C50 FULL).

## Prerequisites

All verified:
- [x] Model artifacts: `hybrid_r0.json` (constrained), `hybrid_r0_full.json` (full)
- [x] Existing comparator runs: 5 bidders (missing `olsa`, `olsa_full`)
- [x] Scripts merged: `run_arc_d_h2h_battery.py`, `calibrate_arc_d_thresholds.py`
- [x] OLSaBidder dual-format loading (C33)

## Dependency Graph

```
Step 1 (C33 ablation)  ─────────────────────────────────────────┐
Step 2 (expanded comparators)  ──────────────────────────────────┤
Step 3 (C50 QUICK, 49 matchups)  ───> Step 4 (D23 calibrate) ──┤
                                  └─> Step 5 (C50 FULL subset) ─┤
                                                                 ├─> Step 7 (reports)
Step 4 + Step 5  ───> Step 6 (drift check)  ────────────────────┤
Step 7 (reports) ───> Step 8 (exit gate notebooks)  ────────────┘
```

**Parallelism:** Steps 1, 2, and 3 are independent — run concurrently.
Step 4 requires Step 3. Step 5 requires Step 3. Step 6 requires Steps 4+5.

---

## Step 1: C33 Ablation Run (mini-H2H)

**What:** 4 matchups × 10k deals = 40k hands. Tests Gaussian EV wrapper vs floor-based OLSa.
**Runtime:** ~1–2 minutes.

```bash
uv run python experiments/run_experiment.py \
  --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml
```

**Output:** Run dir under `data/runs/arc_d_r0_c33_ablation_42_*`

**Parse results:** The H2H battery runner can parse this, or inspect JSONL directly.
Key question: does `hybrid_olsa` outperform `olsa` on the same coefficients?

---

## Step 2: Expanded Comparator Battery (7 bidders)

**What:** Add `olsa` and `olsa_full` to the existing 5-bidder comparator battery.
**Runtime:** ~2–3 minutes (2 new self-play runs × 10k deals each).

```bash
# Run the expanded comparator battery (adds olsa + olsa_full)
PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml \
  --seed 42 \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder \
  --bidder-name hybrid_olsa \
  --output-format json \
  --output data/artifacts/arc_d/r0/comparator_battery_r0_v2.json
```

Then extract CIs:
```bash
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 \
  --runs-dir data/runs \
  --seed 42 \
  --n-bootstrap 10000 \
  --output data/artifacts/arc_d/r0/comparator_cis_r0_v2.json \
  --battery-file comparator_battery_r0_v2.json
```

**Output:** `comparator_battery_r0_v2.json` + `comparator_cis_r0_v2.json`

**Validation:** All 7 bidders present in output. Rankings should show
`modeloespecifico` > `hybrid_olsa` > `olsa` ≈ `olsa_full` by net_eppd (expected ordering).

---

## Step 3: C50 QUICK — Full H2H Matrix (49 matchups)

**What:** 7 bidders all-vs-all: 7 self-play + 21 pairs × 2 rotations = 49 cells.
**Budget:** 2,000 deals/cell × 49 = ~98k hands.
**Runtime:** ~2–4 minutes.

```bash
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK \
  --seed 42 \
  --n-per 2000 \
  --output data/artifacts/arc_d/r0/h2h_battery_quick.json
```

**Output:** `h2h_battery_quick.json` (h2h_battery_v1 schema)

**Validation:**
- 49 cells present in output
- Self-play cells: `net_eppd_delta ≈ 0`, `win_rate ≈ 0.50`
- All cells have `deals_total == 2000`
- `cvar_5` populated for all cells

---

## Step 4: D23 Calibration — Threshold Artifact from QUICK

**Depends on:** Step 3 complete.

**What:** Extract null signal from self-play diagonals + seat-swap residuals.
**Runtime:** <10 seconds.

```bash
PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
  --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
  --seed 42 \
  --output data/artifacts/arc_d/r0/gate_thresholds_r1.json
```

**Output:** `gate_thresholds_r1.json` (gate_thresholds_v1 schema)

**Validation:**
- `delta_floor >= 0.01` (floor)
- `regression_threshold >= 0.05` (floor)
- `cvar5_tolerance >= 0.05` (floor)
- `null_distribution_n >= 28` (7 self-play + 21 seat-swap residuals)
- All threshold values are finite and positive

---

## Step 5: C50 FULL — Targeted Rerun

**Depends on:** Step 3 complete (needs QUICK summary for subset selection).

**What:** Rerun key matchups at 10k deals/cell. Subset = all cells involving
`{hybrid_olsa, olsa, olsa_full}` + any QUICK cells whose CI crosses zero.
**Budget:** ~25–35 cells × 10k = ~250–350k hands.
**Runtime:** ~5–10 minutes.

```bash
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode FULL \
  --seed 42 \
  --n-per 10000 \
  --quick-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
  --output data/artifacts/arc_d/r0/h2h_battery_full.json
```

**Output:** `h2h_battery_full.json` (merged QUICK+FULL, h2h_battery_v1 schema)

**Validation:**
- FULL cells have `deals_total == 10000`
- Non-FULL cells retained from QUICK at `deals_total == 2000`
- Self-play sanity: `net_eppd_delta ≈ 0` at FULL budget
- CIs narrower than QUICK (√5 improvement expected)

---

## Step 6: D23 Drift Check — QUICK vs FULL

**Depends on:** Steps 4 + 5 complete.

**What:** Re-derive null quantiles from FULL data, compare to QUICK thresholds.
**Runtime:** <10 seconds.

```bash
PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
  --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
  --full-summary data/artifacts/arc_d/r0/h2h_battery_full.json \
  --seed 42 \
  --output data/artifacts/arc_d/r0/gate_thresholds_r1.json
```

**Decision logic:**
- If `drift_ratio <= 0.25`: retain QUICK thresholds, record drift check pass
- If `drift_ratio > 0.25`: recalibrates from FULL data automatically

**Output:** Updated `gate_thresholds_r1.json` with `drift_check` section populated.

**Validation:**
- `drift_check.drift_ratio` is finite
- If recalibrated: `calibration_source` changes to FULL artifact path

---

## Step 7: Update Reports + Bundle

**Depends on:** Steps 1–6 complete.

**What:** Summarize results. Lightweight — not a code PR, just artifact inspection.

1. **C33 ablation findings:** Extract `hybrid_olsa` vs `olsa` paired delta from Step 1.
   Document whether Gaussian EV layer adds measurable value.

2. **Expanded comparator rankings:** Review `comparator_cis_r0_v2.json` for
   7-bidder ranking with CIs. Compare to prior 5-bidder ranking.

3. **H2H heatmap data:** Inspect `h2h_battery_full.json` for:
   - Dominance ordering (is it transitive or rock-paper-scissors?)
   - Positional bias (seat-swap deltas)
   - Key matchup CIs

4. **Threshold values:** Record calibrated `delta_floor`, `regression_threshold`,
   `cvar5_tolerance` for documentation.

---

## Step 8: Phase 2 Exit Gate — Notebook Run

**Depends on:** Steps 1–7 complete (notebooks may read new artifacts).

**What:** Execute all R0 notebooks in SMOKE mode to verify they still run cleanly.
**Runtime:** ~30–60 seconds.

```bash
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

**Validation:**
- All notebooks execute without error
- No assertion failures in notebook cells

---

## Artifact Inventory (Expected After All Steps)

| Artifact | Step | Schema |
|----------|------|--------|
| `data/runs/arc_d_r0_c33_ablation_42_*` | 1 | Run dir (JSONL) |
| `data/artifacts/arc_d/r0/comparator_battery_r0_v2.json` | 2 | `arc_d_comparator_v1` |
| `data/artifacts/arc_d/r0/comparator_cis_r0_v2.json` | 2 | `comparator_cis_v1` |
| `data/artifacts/arc_d/r0/h2h_battery_quick.json` | 3 | `h2h_battery_v1` |
| `data/artifacts/arc_d/r0/gate_thresholds_r1.json` | 4→6 | `gate_thresholds_v1` |
| `data/artifacts/arc_d/r0/h2h_battery_full.json` | 5 | `h2h_battery_v1` |

None of these are committed to git (data policy).

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| H2H runner crashes on real data | Step 3 uses `--config-only` first to validate YAML, then run |
| QUICK sample too small for stable CIs | Step 5 (FULL) reruns key cells at 5× budget |
| Drift check triggers recalibration | Step 6 handles automatically; re-inspect thresholds |
| Notebook reads old artifact paths | Step 8 catches via assertion failures |
| C33 ablation shows no wrapper effect | Valid finding — document in report, doesn't block R1 |

---

## Post-Completion

After all 8 steps pass:
- Update MEMORY.md: mark all transition items complete, set status to "Ready for PR-R1a"
- The experiment artifacts (not code) support the R1 training + gate cycle
- PR-R1a can begin (new training data, R1 model training, R1 bundle + gate)
