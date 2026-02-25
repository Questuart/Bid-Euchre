# H2H Battery Schema v1

**Status:** Active
**Version:** 1
**Script:** scripts/internal/run_arc_d_h2h_battery.py

---

## Overview

The H2H battery artifact records results from all-vs-all bidder matchups in
head-to-head matrix mode. Each cell captures per-matchup metrics for competitive
validation of bidder performance under direct opposition.

Two-phase workflow:
- **QUICK:** All N^2 matchups at lower sample size (n_per=2000) for rapid triage.
- **FULL:** Targeted subset at higher sample size (n_per=10000) for publication-grade CIs.

## File Naming Convention

| File | Context |
|------|---------|
| `h2h_battery_quick.json` | QUICK phase results (all matchups, lower n) |
| `h2h_battery_full.json` | FULL phase results (subset, higher n) |

## Top-Level Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema` | str | Yes | Always `"h2h_battery_v1"` |
| `generated_at` | str | Yes | ISO 8601 timestamp (UTC) |
| `mode` | str | Yes | `"QUICK"` or `"FULL"` |
| `seed` | int | Yes | RNG seed for experiment |
| `n_per` | int | Yes | Deals per matchup |
| `roster` | array[str] | Yes | Ordered list of bidder names |
| `cells` | object | Yes | Map of matchup_id to cell entries (see below) |
| `quick_source` | str or null | Yes | Path to QUICK summary (FULL mode only) |
| `provenance` | object | Yes | Script and git SHA for traceability |

## Cell Entry Schema

Each cell is keyed by `matchup_id` (e.g., `"hybrid_olsa_vs_olsa"` or `"olsa_self_play"`).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bidder_a` | str | Yes | Bidder occupying seats 0,2 (or sole bidder for self-play) |
| `bidder_b` | str | Yes | Bidder occupying seats 1,3 (same as bidder_a for self-play) |
| `net_eppd_a` | float or null | Yes | Net expected points per deal for bidder_a |
| `net_eppd_b` | float or null | Yes | Net expected points per deal for bidder_b |
| `net_eppd_delta` | float or null | Yes | `net_eppd_a - net_eppd_b` (positive = a better) |
| `ci_low` | float or null | Yes | Bootstrap 95% CI lower bound for net_eppd_delta |
| `ci_high` | float or null | Yes | Bootstrap 95% CI upper bound for net_eppd_delta |
| `win_rate_a` | float or null | Yes | Fraction of deals where bidder_a's team scored more |
| `bid_rate_a` | float or null | Yes | Bid rate for bidder_a |
| `bid_rate_b` | float or null | Yes | Bid rate for bidder_b |
| `make_rate_a` | float or null | Yes | Make rate for bidder_a |
| `make_rate_b` | float or null | Yes | Make rate for bidder_b |
| `deals_total` | int | Yes | Total deals in this matchup |
| `pair_deals` | bool | Yes | Whether paired dealing was used |
| `run_id` | str or null | Yes | Run directory identifier |
| `config_sha` | str | Yes | SHA-256 prefix of the config dict |
| `matchup_id` | str | Yes | Unique matchup identifier |

## Matchup ID Convention

- Self-play: `{bidder}_self_play` (e.g., `hybrid_olsa_self_play`)
- Cross-matchup: `{bidder_a}_vs_{bidder_b}` where bidder_a occupies seats 0,2

For N bidders, expected matchup count is N^2 (N self-play + N*(N-1) cross-matchups
with both seat rotations).

## Provenance Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `script` | str | Yes | Script path that generated the artifact |
| `git_sha` | str | Yes | Git commit SHA at generation time |

## FULL Mode Subset Selection

When generating a FULL battery from a QUICK summary:
1. Always include cells involving key bidders (`hybrid_olsa`, `olsa`, `olsa_full`).
2. Include any cross-matchup cell where the QUICK CI crosses zero (`ci_low < 0 < ci_high`).

The `quick_source` field records which QUICK summary was used for selection.

## Null Values

Null cell metrics indicate the matchup config was generated but the experiment
has not yet been run and parsed. After experiment execution and parsing, all
numeric fields should be populated with float values.
