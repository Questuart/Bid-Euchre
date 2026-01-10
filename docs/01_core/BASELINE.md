# Baseline Specification

## Purpose

**Baseline is a health check and regression anchor**, not research-grade benchmarking.

Baseline runs:
- Must be **deterministic** (seed required unless explicitly opting out via `--allow-nondeterministic`)
- Provide a **regression guard** to catch changes in simulation, strategy, or RNG behavior
- Are **fast enough** for frequent execution (developer workflow + CI)

Baseline is not:
- A substitute for comprehensive experiments
- Optimized for statistical significance or publication-ready metrics
- A replacement for domain-specific testing

---

## Baseline Tiers

### `baseline_tiny` (This Spec)

**Purpose**: Developer-friendly, CI-friendly health check

**Contract**:
- **Play-only** (no bidding strategies)
- **Default seed**: `42`
- **Default n_per**: `20` (hands per scenario)
- **Total hands**: ~760 (completes in seconds)
- **Scenarios**: Full coverage (6 scenarios: 4 suit contracts + high + low)
- **Strategies**: RandomLegal (sanity), Greedy (anchor), multi-strategy comparison

**Execution**:
- **Now (manual)**: Via `experiments/run_experiment.py` (3 invocations)
- **PR #20+**: Via suite runner `scripts/run_suite.py`

**Outputs**: Always under `data/runs/<run_id>/` (never committed)

---

### `baseline_full` (Manual: Strategy Interactions + Auction Plumbing)

**Purpose**: Broader regression net beyond `baseline_tiny` (interaction effects + wiring)

**Contract**:
- **Strategy interactions**: 4x4 matchup matrix (16 matchups including self-play controls)
- **Auction plumbing**: Bidding mode smoke test
- **Default seed**: `42`
- **Default n_per**: `500` (hands per matchup/scenario)
- **Total hands**: ~120,000 (16 × 6 × 500)
- **Strategies**: greedy, random_legal, always_highest, always_lowest
- **Scenarios**: Full coverage (6 scenarios: 4 suit contracts + high + low)

**When to run**: Before merging changes to sim/core/scoring/strategy/runner (manual)

**How to run**:

```bash
PYTHONPATH=src python scripts/run_suite.py \
  --suite experiments/suites/baseline_full.yaml
```

**Expected runtime**: ~5 minutes (adjust n_per via `--n-per` if needed)

**Outputs**: Rollup directory under `data/runs/suite_<timestamp>/` (never committed)

---

## `baseline_tiny` Contents

The `baseline_tiny` suite includes **3 experiment configs** (3 invocations of `run_experiment.py`):

### 1. `quick_test_random.yaml` — Ultra-fast sanity check

**Purpose**: RandomLegalStrategy seed path + minimal scenario coverage

**Details**:
- **Strategies**: 1 (RandomLegalStrategy only)
- **Scenarios**: 2 (suit with trump Hearts, high)
- **Hands** (with `n_per=20`): 1 × 2 × 20 = **40 hands**

**Why include?**:
- Validates RandomLegalStrategy determinism (auto-seeded per seat)
- Fastest possible sanity check
- Exercises basic runner + RNG paths

---

### 2. `baseline_greedy.yaml` — Single-strategy anchor

**Purpose**: Greedy strategy performance across full scenario grid

**Details**:
- **Strategies**: 1 (GreedyStrategy only)
- **Scenarios**: 6 (4 suit contracts: C/D/H/S, high, low)
- **Hands** (with `n_per=20`): 1 × 6 × 20 = **120 hands**

**Why include?**:
- Regression anchor for Greedy strategy
- Full scenario coverage
- Baseline for trick-taking performance

---

### 3. `strategy_comparison.yaml` — Multi-strategy surface area

**Purpose**: Compare 5 strategies on common deals

**Details**:
- **Strategies**: 5 (greedy, improved_greedy, random_legal, always_lowest, always_highest)
- **Scenarios**: 6 (full grid)
- **Hands** (with `n_per=20`): 5 × 6 × 20 = **600 hands**

**Why include?**:
- Validates strategy comparison logic
- Exercises common deals (same seed across strategies)
- Largest surface area for regression detection

---

### Total: ~760 hands

**Estimated runtime**: Seconds (exact timing depends on hardware)

---

## How to Run `baseline_tiny` (Manual)

Run these commands **in order** (copy/paste):

### 1. Quick random sanity (2 scenarios)

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test_random.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none
```

---

### 2. Greedy anchor (full scenario set)

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/baseline_greedy.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none
```

---

### 3. Multi-strategy comparison (full scenario set, common deals)

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none
```

---

## Suite Definition (PR #20+)

Starting in PR #20, `baseline_tiny` will be runnable via the suite runner:

```bash
PYTHONPATH=src python scripts/run_suite.py \
  --suite experiments/suites/baseline_tiny.yaml
```

The suite definition is at: `experiments/suites/baseline_tiny.yaml`

The suite runner will:
- Invoke `experiments/run_experiment.py` once per config
- Apply suite-level parameter overrides (`--seed 42 --n_per 20`)
- Optionally generate a rollup summary (PR #20 scope TBD)

---

## Output Contract

Every baseline run follows the standard run output contract:

**Run directory**: `data/runs/<run_id>/`

**Required files/directories**:
- `meta.json` (run metadata)
- `config_effective.yaml` (resolved configuration snapshot)
- `results/`, `logs/`, `reports/`, `splits/`, `artifacts/` (subdirectories)

See `docs/01_core/DATA_CONTRACT.md` and `docs/01_core/EXPERIMENTS.md` for full details.

**Critical**: Baseline outputs are **never committed**. The `data/runs/` directory is gitignored.

---

## Determinism Requirements

Baseline runs **must be deterministic** (repeatable with same seed):

1. **Explicit seed required**: `--seed 42` (or via suite parameters)
2. **Common deals enabled**: Strategies see the same hands (when seeded)
3. **Strategy RNG seeded**: RandomLegalStrategy auto-seeded per seat (derived from run seed)

See `docs/01_core/REPRODUCIBILITY.md` for full determinism details.

---

## Regression Detection

Baseline is designed to catch:

- **Simulation bugs**: Changes to trick-taking logic, contract rules, or scoring
- **Strategy regressions**: Greedy no longer plays optimally, etc.
- **RNG changes**: Deal generation or strategy RNG differs across runs
- **Config resolution bugs**: Effective config doesn't match expected
- **Output contract violations**: Missing files, changed structure

**How to use baseline for regression testing**:

1. Run `baseline_tiny` on a known-good commit (e.g., `main`)
2. Save `results/**/*.json` and `config_effective.yaml` as fixtures
3. Run `baseline_tiny` on your branch
4. Compare results (exact equality for deterministic artifacts)

Future PRs may add automated fixture-based tests for baseline runs.

---

## Notes

- **Play-only**: Baseline does not include bidding strategies (bidding is out of scope)
- **Not statistical**: `n_per=20` is too small for confidence intervals; use for regression only
- **Fast by design**: Baseline should complete quickly enough for frequent execution
- **Extensible**: Additional tiers (e.g., `baseline_medium`, `baseline_full`) can be added later

---

## References

- **Suite definition**: `experiments/suites/baseline_tiny.yaml`
- **Run output contract**: `docs/01_core/DATA_CONTRACT.md`
- **Experiment workflows**: `docs/01_core/EXPERIMENTS.md`
- **Determinism details**: `docs/01_core/REPRODUCIBILITY.md`
