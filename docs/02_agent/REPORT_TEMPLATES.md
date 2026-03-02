# Report Templates

Structural reference for the four recurring report types produced at each
rung. Each template documents the section structure, required JSON artifact
sources, and which sections need interpretation vs data extraction.

**Exemplars:** R0 reports in `docs/04_reports/r0/` are the canonical examples.

---

## 1. Promotion Report

**Purpose:** Formal gate decision document for each rung.
**Exemplar:** `docs/04_reports/r0/r0_promotion_report.md`
**Primary artifacts:** `promotion_decision_r{N}.json`, `rung_bundle_r{N}.json`,
  eval metric files (`eval_r{N}.json`, `eval_r{N}_s43.json`, `eval_r{N}_s44.json`)

### Section Structure

| # | Section | Source | Interpretation Needed |
|---|---------|--------|----------------------|
| 1 | **Header** | Bundle metadata | No — data extraction |
| 2 | **Executive Summary** | Decision + eval metrics | Yes — five-question narrative |
| 3 | **Gate Results** | `promotion_decision_r{N}.json` > tier_1_checks | Minimal — add one-line descriptions of each check |
| 4 | **Evaluation Metrics** | Eval files (3 seeds) | Moderate — multi-seed stability table + commentary |
| 5 | **Attribution Gap** | Decision > attribution_gap + eval metrics | Yes — explain direction and magnitude |
| 6 | **Comparator Context** | Summarize from comparator_rankings.md | Yes — summarize-and-link pattern |
| 7 | **Gate Thresholds** | `gate_thresholds_r{N+1}.json` (if recalibrated) | Moderate — explain threshold derivation |
| 8 | **Companion Reports** | Directory listing | No — cross-link table |
| 9 | **Provenance** | Bundle paths + timestamps | No — data extraction |

### Structural vs Rung-Specific

- **Structural (same every rung):** Header format, gate results table layout,
  provenance table, companion reports section
- **Rung-specific:** Executive summary narrative, attribution gap interpretation,
  comparator context numbers, threshold values

### Key Fields from `promotion_decision_r{N}.json`

```
decision: "PROMOTED" | "ADVANCED" | "HALT"
tier_1_checks: {check_name: "PASS" | "FAIL", ...}
gate_results: {gate_name: {metric, pass, note}, ...}
attribution_gap: float
challenger: {arm, metrics_seed42: {net_expected_points_per_deal, ...}}
olsa_arm: {arm, metrics_seed42: {net_expected_points_per_deal, ...}}
```

---

## 2. Comparator Rankings

**Purpose:** Absolute benchmarking of all bidders via single-seat comparator.
**Exemplar:** `docs/04_reports/r0/comparator_rankings.md`
**Primary artifacts:** `comparator_battery_r{N}_v4.json`, `comparator_cis_r{N}_v4.json`

### Section Structure (9 sections)

| # | Section | Source | Interpretation Needed |
|---|---------|--------|----------------------|
| 1 | **Summary** | Rankings data | Yes — tier identification, headline finding |
| 2 | **Methodology** | Structural | Minimal — update deal counts, bidder count |
| 3 | **Rankings Table** | `comparator_cis_r{N}.json` | No — data extraction with bootstrap CIs |
| 4 | **Contract-Type Rankings** | Per-contract data from comparator battery | Moderate — identify contract specialists |
| 5 | **Pairwise Statistical Significance** | Bootstrap CI overlap analysis | No — computed from CIs |
| 6 | **Behavioral Profiles** | Comparator metrics (bid_rate, make_rate) | Yes — characterize each bidder's strategy |
| 7 | **Key Observations** | Cross-rung comparison | Yes — rank changes, new findings |
| 8 | **Auction-Pressure Sensitivity** | 4-way mode data (if available) | Yes — methodology comparison |
| 9 | **Provenance & Reproduction** | Run metadata | No — data extraction |

### Structural vs Rung-Specific

- **Structural:** Methodology section (except deal counts), pairwise significance
  method, provenance table format
- **Rung-specific:** Rankings table values, behavioral profiles (bidder roster
  changes), key observations, contract-type breakdown

### Key Fields from `comparator_cis_r{N}.json`

```
{bidder_name: {
  net_eppd: float,
  ci_low: float,
  ci_high: float,
  n_deals: int,
  bid_rate: float,
  make_rate: float,
  ...
}}
```

---

## 3. H2H Battery Analysis

**Purpose:** Competitive ordering via head-to-head matchups.
**Exemplar:** `docs/04_reports/r0/h2h_battery_analysis.md`
**Primary artifacts:** `h2h_battery_quick_v2.json`, `h2h_battery_full_v2.json`,
  `gate_thresholds_r{N+1}.json`

### Section Structure (8 sections)

| # | Section | Source | Interpretation Needed |
|---|---------|--------|----------------------|
| 1 | **What Was Done** | Run metadata | Moderate — campaign inventory + methodology |
| 2 | **C33 Ablation** | H2H subset (if applicable) | Yes — wrapper effect interpretation |
| 3 | **Comparator Summary** | Summarize from comparator_rankings.md | Minimal — summarize-and-link |
| 4 | **H2H Full Matrix** | Battery JSON cells | Moderate — dominance ordering, surprises |
| 5 | **Gate Threshold Calibration** | `gate_thresholds_r{N+1}.json` | Yes — explain derivation method |
| 6 | **Artifact Inventory** | File listing | No — data extraction |
| 7 | **Conclusions** | Synthesis | Yes — overall findings, implications |
| 8 | **Reproduction** | Run commands | No — commands with seeds |

### Structural vs Rung-Specific

- **Structural:** Methodology description, matrix table format, threshold
  derivation method, artifact inventory format
- **Rung-specific:** Campaign inventory, matrix values, threshold values,
  conclusions, C33 ablation (R0 only)

### Key Fields from `h2h_battery_*.json`

```
cells: [{
  bidder_a: str,
  bidder_b: str,
  net_eppd_delta: float,
  ci_low: float,
  ci_high: float,
  n_deals: int,
  ...
}]
roster: [str, ...]
mode: "QUICK" | "FULL"
```

### Team Breakout Requirement

H2H summary tables MUST show team0 and team1 metrics separately. In H2H
runs both teams bid; in comparator runs only one team bids. Team-level
breakout makes this asymmetry visible.

---

## 4. Measurement Integrity Review

**Purpose:** Methodology limitations and deferral cost analysis.
**Exemplar:** `docs/04_reports/r0/measurement_integrity_r0.md`
**Primary artifacts:** All artifacts (cross-cutting review)
**Template:** `docs/02_agent/MEASUREMENT_INTEGRITY_REVIEW.md`

### Section Structure

| # | Section | Source | Interpretation Needed |
|---|---------|--------|----------------------|
| 1 | **Header** | Metadata | No — standard table |
| 2 | **Evaluation Batteries** | All run scripts | No — inventory table |
| 3 | **Known Methodological Limitations** | Review findings | Yes — identify and classify |
| 4 | **Deferral Cost Descriptions** | Per-limitation analysis | Yes — three-cost framework |
| 5 | **Conclusion** | Synthesis | Yes — overall assessment |

### Structural vs Rung-Specific

- **Structural:** Header format, limitation classification scheme ((a)/(b)/(c)),
  three-cost framework (fix-now / fix-later / never-fix)
- **Rung-specific:** Specific limitations, resolution status, deferral costs

### Limitation Categories

Per `.claude/rules/35_integrity.md`:

- **(a) Accepted limitation** — inherent to design, documented, no action needed
- **(b) Deferred limitation** — fixable but deferred; requires cost analysis
- **(c) Blocker** — must be fixed before promotion (always immediate)

### Carry-Forward Rule

At each rung, carry forward unresolved (b)-class items from the previous
rung. Update resolution status and reassess deferral costs.

---

## Artifact-to-Report Mapping

Which artifacts feed which reports:

| Artifact | Promotion | Comparator | H2H | Measurement |
|----------|-----------|------------|-----|-------------|
| `promotion_decision_r{N}.json` | Primary | - | - | Reference |
| `rung_bundle_r{N}.json` | Primary | - | Reference | Reference |
| `eval_r{N}*.json` (3 seeds) | Primary | - | - | Reference |
| `comparator_battery_r{N}.json` | Summarize | Primary | Reference | Reference |
| `comparator_cis_r{N}.json` | Summarize | Primary | - | - |
| `h2h_battery_quick*.json` | - | - | Primary | Reference |
| `h2h_battery_full*.json` | - | - | Primary | Reference |
| `gate_thresholds_r{N+1}.json` | Reference | - | Primary | Reference |

---

## Graceful Degradation

When artifacts are missing, reports should degrade gracefully:

- **Missing artifact:** Include a placeholder: `*[Section] — artifact not
  yet available: {artifact_name}*`
- **Partial data:** Generate what's possible, flag missing sections
- **Draft suffix:** Use `_DRAFT` suffix for reports generated before all
  artifacts are available. Rename to final after review.
