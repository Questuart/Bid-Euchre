---
name: analyzing-results
description: Guides statistical analysis of experiment results: reading comparator output, interpreting metrics, checking significance, and producing committed evidence artifacts. Use when analyzing experiment runs or preparing statistical claims for reports.
---

# Statistical Analysis Guide

Analyze experiment results with the rigor standards this repo requires. Every inference claim needs statistical backing — no visual-only validation.

## Phase 1 — Load Results

1. Identify the run directory:
   ```bash
   ls data/runs/<run_id>/
   ```

2. Read run metadata for config, seed, and deal count:
   ```bash
   cat data/runs/<run_id>/metadata.json
   ```

3. For comparator output, check for existing artifacts:
   ```bash
   ls data/artifacts/arc_d_v2/ 2>/dev/null
   ```

## Phase 2 — Statistical Checklist

Before making ANY inference claim, verify:

- [ ] **Sample size adequate** (see minimums table below)
- [ ] **Hypothesis test included** (ANOVA, t-test, chi-square as appropriate)
- [ ] **Confidence intervals computed** (bootstrap or parametric)
- [ ] **Effect sizes reported** (R², Cohen's d — not just p-values)
- [ ] **Multiple comparison correction** if testing >3 hypotheses
- [ ] **Confounders identified** (seat balance, contract type distribution)

See [CHECKLIST.md](CHECKLIST.md) for the full gold-standard rigor checklist.

## Phase 3 — Key Metrics

| Metric | Script | Minimum N | What it measures |
|--------|--------|-----------|-----------------|
| net_eppd | `scripts/compare_runs.py` | 2,000 | Expected points per deal delta |
| CVaR | `scripts/compare_runs.py` | 5,000 | Tail risk (worst-case performance) |
| H2H win rate | `scripts/internal/run_arc_d_h2h_battery.py` | 2,000 | Head-to-head match win percentage |
| R² | `scripts/compare_runs.py` | 1,000 | Variance explained by model |
| bid_rate | `scripts/compare_runs.py` | 2,000 | Bidding frequency |
| make_rate | `scripts/compare_runs.py` | 2,000 | Bid success rate |

Sample size thresholds:
- **Bias detection** (seat/suit): ≥2,000 deals
- **Feature correlation**: ≥1,000 samples per group
- **Tail analysis** (CDF/CCDF): ≥5,000 samples
- **Production reports**: ≥50,000 samples

## Phase 4 — Artifact Commitment

Decision-critical analysis must be traceable to committed artifacts:

1. If analysis runs in a notebook, export results to committed JSON:
   ```python
   import json
   with open("data/artifacts/<name>.json", "w") as f:
       json.dump(results, f, indent=2)
   ```

2. Report claims must reference committed artifacts — not notebook cell outputs
3. Include reproduction commands with seeds in any report

## Gotchas

- Visual-only validation is a **blocker** per `05_rigor.md` — always pair charts with statistical tests
- N < 2,000 is insufficient for bias detection; N < 50,000 insufficient for production claims
- Notebook outputs (`.ipynb` cell results) are gitignored — trace claims to committed JSON artifacts
- Effect sizes (Cohen's d, R²) are REQUIRED alongside p-values — significance without magnitude is meaningless
- Multiple comparison corrections needed when testing >3 hypotheses simultaneously
- "Looks balanced" is never acceptable — use ANOVA or chi-square

## References

- `docs/01_core/METRICS.md` — Metric definitions and scoring fields
- `.claude/rules/deferred/05_rigor.md` — Statistical rigor requirements
- `.claude/rules/deferred/45_notebook_boundary.md` — Notebook traceability rules
