# Contributing (AI + Human)

This repo is a **Bid Euchre simulation + strategy evaluation lab**. Contributions should improve one of:
- correctness of the game simulation
- modularity/comparability of strategies
- interpretability of reporting
- reliability/reproducibility of experiments
- hand evaluation signals/features for strategies + models

If your change doesn’t clearly help one of those, don’t do it.

---

## Ground rules (read this first)

### 1) Reproducibility is mandatory
- All simulations must be rerunnable from a **seed** + **config**.
- If you introduce randomness inside strategies, it must be seeded and recorded.
- Any experiment output should include strategy set name + seed + run-id/config hash.

### 2) Strategies must be comparable
- No strategy can “peek” at hidden information.
- Keep strategy interfaces consistent (same inputs, same outputs).
- Avoid global state. Prefer pure decision functions.

### 3) Reporting must explain *why*, not just *what*
Win rate alone is insufficient. Prefer outputs that reveal:
- contract make/set rates
- trick distributions
- variance/tail losses
- behavior differences (bid frequency/level, suit choice, etc.)

---

## What to work on (priority order)

1) **Reports & run identity**
   - Ensure outputs are uniquely named (no overwrites).
   - Add summary tables that compare strategies cleanly.
   - Add distribution plots (not only means).

2) **Hand evaluation stability**
   - Keep tuple score definitions stable and documented.
   - Add model-friendly feature dict output.
   - Add analysis linking hand_eval → realized tricks/EV.

3) **Simple strategies**
   - Add/adjust greedy/risk heuristics (explainable rules).
   - Keep changes small and measurable.

4) **Regression baseline (only after above is stable)**
   - Model bidding decisions first (bid vs pass, level selection).
   - Use explicit feature sets from `hand_eval`.

---

## Branch / change hygiene

### Make one “unit of change” per PR
Examples:
- “Add run-id naming to plot outputs”
- “Add new metric: contract success rate”
- “Add greedy variant with X rule”

Avoid mixed PRs like “refactor everything + add model + new plots.”

### Keep refactors earned
Refactor only if it:
- reduces duplication AND
- is directly needed for the next planned step AND
- doesn’t change behavior (unless explicitly intended)

---

## Standard experiment protocol

When you add or change a strategy/report:
1) Run a small deterministic simulation (e.g., 200–1,000 hands) with a fixed seed.
2) Run a larger simulation (e.g., 10k+ hands) if performance permits.
3) Generate the same report set as baseline.
4) Compare:
   - win rate / EV
   - contract make rate
   - trick distribution
   - bid frequency + bid levels

### Always record in outputs
Each run should embed:
- `seed`
- `strategy_set` (or both strategies being compared)
- `hand_eval_mode`
- `run_id` (timestamp + short config signature)

---

## Output conventions (required)

Write outputs to:
`outputs/<run_id>/...`

Where `<run_id>` should include:
- `YYYYMMDD_HHMMSS`
- `seed`
- short config hash (or abbreviated config name)

Examples:
- `outputs/20251215_221530_seed42_greedy-v1_evaltupleA/summary.csv`
- `outputs/20251215_221530_seed42_greedy-v1_evaltupleA/plots/score_vs_tricks.png`

Do not overwrite prior results by default.

---

## Strategy interface (recommended)

Strategies should expose two decision functions (or methods):

- `choose_bid(game_state, hand, hand_eval) -> bid`
- `choose_card(game_state, hand, trick_state, hand_eval) -> card`

Requirements:
- Deterministic given inputs (unless explicitly randomized with seed).
- No mutation of shared objects.
- Optional debug trace hooks are fine, but must be off by default.

---

## Hand evaluation requirements

### Tuple scores
If `hand_eval` returns a tuple score:
- document each field and ordering
- keep it stable unless you bump a version and update plots/reports accordingly

### Feature dict for models
Prefer a function like:
`hand_features(hand, context) -> dict[str, float|int|bool]`

This is the canonical input for any regression/ML.

---

## Reporting checklist (minimum)

Every major comparison should include:
- `summary.csv` (one row per strategy)
- contract success rate (made vs set)
- mean + distribution of tricks taken
- bid frequency + avg bid level
- variance/tail metrics (e.g., 5th percentile outcome)

Plots should be:
- labeled with strategies + eval mode + seed/run-id
- distribution-based where possible (hist/ECDF/box)

---

## Testing expectations (lightweight but real)

At minimum, before merging:
- A short deterministic run completes (fixed seed).
- No strategy crashes on edge hands.
- Report scripts run end-to-end and write outputs.

If you have tests:
- Update them when behavior changes intentionally.
- Add tests when fixing a bug that could regress.

---

## Common failure modes (avoid these)

- “Greedy improved win rate” but outputs got overwritten → cannot validate.
- Strategy change also changes rules/scoring silently → comparisons invalid.
- Plots show averages only → hides fat-tail losses.
- Hand evaluation changed but old plot labels remain → misleading results.

---

## If you’re an AI assistant contributing here
You should:
- propose the smallest change that can be measured
- state what files you will touch and why
- ensure deterministic re-run instructions exist
- keep outputs versioned and labeled
- avoid speculative changes that aren’t requested or measurable

---

## Experiment Standards (MANDATORY - Added 2026-01-04)

**Before adding any new experiment script, follow these rules:**

### 1. Can this use `run_experiment.py`?

**If YES** → Create YAML config only (no new script needed)  
**If NO** → Proceed to steps 2-5

### 2. Create Config File FIRST

```yaml
# experiments/configs/my_experiment.yaml
experiment_name: my_experiment
parameters:
  n_hands: 10000
  seed: 42
  # All parameters here - NO HARDCODING in Python!
```

### 3. Accept `--config` Argument

```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True)
args = parser.parse_args()
config = load_config(args.config)
```

### 4. Write Integration Test

```python
# tests/test_my_experiment.py
def test_runs_with_small_data():
    # Test with 10 hands, assert no crashes
    pass
```

### 5. Update Registry

Add entry to `experiments/REGISTRY.yaml`

### Red Flags 🚩

- Hardcoded parameters in Python
- No config file
- No tests
- Can't reproduce from config alone

### Green Lights ✅

- Config file exists
- Accepts `--config`
- Has integration test
- In REGISTRY.yaml
- Outputs include metadata

