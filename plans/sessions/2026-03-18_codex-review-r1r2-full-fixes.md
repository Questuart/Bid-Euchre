# Codex Review Fix Plan — R1/R2 FULL Bundle Findings

**Date:** 2026-03-18
**Author:** author-b
**Scope:** Address valid findings from Codex review of R1/R2 FULL bundles (commit 9dbc2c5)

## Finding Triage

### Valid Findings Requiring Code/Artifact Fixes

| # | Finding | Root Cause | Fix |
|---|---------|-----------|-----|
| F1 | Seeds: [] in all manifests | `generate_evidence_manifest()` loads `h2h_battery.json` / `comparator_cis.json` by canonical name, but multi-seed FULL artifacts use suffixed names (`h2h_battery_full_42.json`, `comparator_cis_r1_42.json`) | Add filename-based seed extraction fallback in manifest.py |
| F2 | Case-insensitive mode comparison | `_extract_advancement_decision()` compared `mode` directly without normalizing case; orchestrator passes lowercase `"quick"` / `"full"` | Already fixed in worktree — `mode = mode.upper()` added |

### Invalid/Non-Actionable Findings

| # | Finding | Why Dismissed |
|---|---------|--------------|
| R1 (CRITICAL) | Synthetic outcome_distributions.csv | **Data availability, not a code bug.** Parquet files are not committed (`data/runs/` policy). Code already: (a) writes `.status` file marking degradation, (b) adds Data Quality Note to §10 of 01_results.md, (c) chart 9 renders synthetic fallback. This is the designed graceful degradation path. |
| R2 | "Mode: QUICK" and "Class: None" | **Factually incorrect.** Actual manifests show `Mode: full` and populated Class columns (e.g., `GBTActionValueBidder`, `ActionValueBidder`). Only Seeds: [] is a real gap (covered by F1). |
| R3 | Absolute artifact paths | **Factually incorrect.** All artifact paths are repo-relative (e.g., `data/artifacts/arc_d_v2/r2/comparator_battery_r2_42.json`). No machine-specific paths found. |
| R4 | "Rung ? (QUICK)" in r2/full 02_decision.md | **Factually incorrect.** Actual title is `# Rung r2 (full) — Decision Report` with `**PENDING**` (correct for FULL without hypothesis outcomes). |
| R5 | Charts 16-18 absent, §5 not populated | **Data availability, not a code bug.** Charts 16-18 require prediction-level parquet data. §5 requires cross-model decision comparison artifacts. Placeholders are correct. |
| R6 | Pooled-only behavior_by_contract.csv / aggregate bid_levels.csv | **Data availability, not a code bug.** Per-contract metrics require `bidders_by_contract` in comparator_cis artifact. Per-bid-level distributions require parquet with `bid_n` column. Code degrades gracefully to pooled/aggregate. |

## Implementation Plan

### Step 1: Add seed extraction from artifact filenames (manifest.py)

**File:** `src/bid_euchre/arc_d_v2/manifest.py`
**Location:** After the `seed_*` directory fallback (line ~243), before mode resolution

Add a fallback that scans `rung_dir/*.json` for seed suffixes in artifact names:
- Pattern: `comparator_battery_<rung>_<seed>.json` or `h2h_battery_<mode>_<seed>.json`
- Extract `<seed>` as integer
- Deduplicate and sort

**API signature:** No change — existing `generate_evidence_manifest()` gains richer seed discovery.

### Step 2: Patch committed manifests (r1/full, r2/full, r1/quick, r2/quick)

Update `Seeds: []` → `Seeds: [42, 123, 456]` for r1, `Seeds: [42]` for r2.
Determine correct seeds from artifact filenames in each manifest.

**Files:**
- `docs/04_reports/arc_d_v2/r1/full/00_manifest.md`
- `docs/04_reports/arc_d_v2/r1/quick/00_manifest.md`
- `docs/04_reports/arc_d_v2/r2/full/00_manifest.md`
- `docs/04_reports/arc_d_v2/r2/quick/00_manifest.md`

### Step 3: Commit existing case-sensitivity fix

**Files already modified:**
- `src/bid_euchre/arc_d_v2/report.py` — `mode = mode.upper()` in `_extract_advancement_decision()`
- `tests/unit/test_rung_report.py` — `test_quick_lowercase_mode_returns_preliminary()`

### Step 4: Add test for manifest seed extraction

**File:** `tests/unit/test_manifest.py` (or relevant existing test file)

Test that `generate_evidence_manifest()` extracts seeds from artifact filenames
when canonical `h2h_battery.json` and `comparator_cis.json` are absent.

### Step 5: Validate

- `uv run python -m pytest tests/unit/test_rung_report.py tests/unit/test_manifest.py`
- `make check-quiet`

### Step 6: Create PR

Single PR covering F1 + F2 fixes — bounded scope, one concept (metadata correctness).

## Outcome

_To be filled after implementation._
