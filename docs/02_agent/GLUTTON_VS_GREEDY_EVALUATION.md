# Glutton vs Greedy Play Policy Evaluation

> **Historical As-Of:** Evidence collected 2026-02-04. Git SHA: ea55269. Canonical run registry version: v1.

## Purpose

Formal evaluation of Glutton vs Greedy play strategies to determine which to freeze as the default play policy for bidder evaluation work. This is a prerequisite gate for the bidding model development pipeline.

## Methodology

- **Gate script:** `scripts/play_policy_gate.py`
- **Seeds:** 42, 43, 44 (3 independent runs)
- **N per scenario per seed:** 20,000 hands
- **Scenarios:** 6 per direction (suit×4 + high + low)
- **Total samples per direction per seed:** 120,000
- **Metric:** Advantage (mean tricks difference)
- **Bootstrap:** 95% CI via percentile method

## Results

### Overall Gate: PASS

All 3 seeds pass in both directions (glutton_vs_greedy and greedy_vs_glutton).

### Aggregate Advantage (glutton playing against greedy)

| Seed | Direction | Advantage | 95% CI | N | Status |
|------|-----------|-----------|--------|---|--------|
| 42 | glutton_vs_greedy | +0.211 | [0.188, 0.232] | 120,000 | PASS |
| 42 | greedy_vs_glutton | +0.186 | [0.164, 0.208] | 120,000 | PASS |
| 43 | glutton_vs_greedy | +0.194 | [0.171, 0.216] | 120,000 | PASS |
| 43 | greedy_vs_glutton | +0.210 | [0.187, 0.233] | 120,000 | PASS |
| 44 | glutton_vs_greedy | +0.196 | [0.173, 0.218] | 120,000 | PASS |
| 44 | greedy_vs_glutton | +0.210 | [0.188, 0.233] | 120,000 | PASS |

All advantages are positive and CIs exclude zero, confirming Glutton is consistently superior.

### Per-Scenario Breakdown (seed=42)

| Scenario | Advantage | 95% CI |
|----------|-----------|--------|
| glutton_vs_greedy/suit_C | +0.310 | [0.258, 0.364] |
| glutton_vs_greedy/suit_D | +0.273 | [0.220, 0.328] |
| glutton_vs_greedy/suit_H | +0.226 | [0.173, 0.279] |
| glutton_vs_greedy/suit_S | +0.273 | [0.220, 0.328] |
| glutton_vs_greedy/high | +0.131 | [0.082, 0.179] |
| glutton_vs_greedy/low | +0.053 | [0.003, 0.101] |

**Key observations:**
- Largest advantage in suit contracts (0.22-0.31 tricks)
- Moderate advantage in HIGH (0.13 tricks)
- Small but significant advantage in LOW (0.05 tricks, CI barely excludes 0)

## Conclusions

1. **Glutton is strictly better** than Greedy across all contract types and seeds
2. The advantage is most pronounced in suit contracts (~0.25 tricks) where trump management matters
3. HIGH/LOW contracts show smaller advantages, as expected (less strategic play differentiation)
4. **Decision:** Freeze Glutton as the default play policy for bidder evaluation

## How to Regenerate

```bash
uv run python scripts/play_policy_gate.py --seeds 42,43,44 --n-per 20000
```

If results change after code modifications, update this document with new evidence and timestamps.

## Source Data

- Gate aggregate: `data/runs/play_policy_gate_aggregate_20260204_221656.json`
- Individual runs: `data/runs/glutton_vs_greedy_head_to_head_{42,43,44}_20260204_*/`
