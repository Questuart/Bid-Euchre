# Fix Report Bundle Provenance Quality
**Date:** 2026-03-19
**Goal:** Fix confirmed evidence manifest and decision report quality issues across the Arc D v2 report bundles.

## Context

A comprehensive review of 538 report files (4 rungs × 3 modes) identified 20 findings.
Validation confirmed 19/20 (F2 not confirmed). After triage:

- **5 findings are actionable in this PR** (code + data fixes)
- **6 findings are informational / by-design** (F7, F8, F17, F18, F19 — no action needed)
- **9 findings are deferred** (F1, F5, F6, F9, F11, F12, F13, F14 — require missing artifacts or new features)

## Findings Addressed

| ID | Finding | Severity | Scope |
|----|---------|----------|-------|
| F3/F16 | Absolute machine paths in evidence_manifest.json and 00_manifest.md | HIGH | 4 canonical bundles |
| F10 | R2 FULL 02_decision.md references nonexistent `04_rung_decision.md` | HIGH | 1 file |
| F15 | Mode casing inconsistency (QUICK vs quick, FULL vs full) | LOW | 9 manifest JSON files |
| F20 | `class_name: null` for all roster entries in canonical manifests | LOW | 4 canonical bundles |
| F4 | R1 canonical decision report missing WARNING caveat for sanity checks | LOW | 1 file |

### Root Cause Analysis

**F3/F16 (absolute paths):** The `_to_repo_relative()` function in `manifest.py`
compares the current `git rev-parse --show-toplevel` (the worktree) against the
artifact paths (which came from the main checkout). When the worktree path
(`Bid-Euchre-steward-*`) doesn't match the main checkout path (`Bid-Euchre/`),
the prefix comparison fails and the absolute path passes through unchanged.
Only canonical bundles are affected because quick/full manifests were regenerated
later from a worktree context where the fix worked.

**F15 (mode casing):** The manifest generator defaults to `"QUICK"` (uppercase) for
`detected_mode`. Newer regenerations passed explicit lowercase mode from CLI.
All 4 canonical manifests say "QUICK", R0 quick says "QUICK" (vs R1-R3 "quick"),
and all 4 full manifests say "FULL".

**F20 (class_name null):** The roster.json files lack `class_name`, `class`, and
`model_class` fields for entries. The fallback chain in `generate_evidence_manifest()`
returns `""` but the committed JSONs show `null` (from a prior code version).
Quick/full manifests were regenerated with improved code that populates class_name.

**F10 (dangling reference):** R2 FULL 02_decision.md references `04_rung_decision.md`
but that file was never generated. The override rationale should be inline.

**F4 (missing WARNING caveat):** R0 canonical correctly says "all checks passed
(some with WARNINGs — see caveats below)". R1 canonical says "all checks passed"
with no caveat, despite `data_sanity.csv` having WARN entries. The report
generator only flags FAILs, not WARNs, in the data_sanity summary line.

## Plan

### Step 1: Fix generator code in manifest.py

File: `src/bid_euchre/arc_d_v2/manifest.py`

1a. **Fix `_to_repo_relative()`** — Handle cross-worktree path resolution.
    The function currently does simple string prefix matching. Add a fallback:
    if the path doesn't start with the worktree root, try to identify the common
    `docs/` or `data/` prefix and strip everything before it. Also try resolving
    symlinks.

    ```python
    def _to_repo_relative(path_str: str) -> str:
        """Convert an absolute path to repo-relative if possible."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
            repo_root = result.stdout.strip()
            if repo_root and path_str.startswith(repo_root):
                return path_str[len(repo_root):].lstrip("/")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: strip any absolute prefix up to a known repo-relative root
        for marker in ("data/", "docs/", "src/", "plans/", "experiments/"):
            idx = path_str.find(marker)
            if idx >= 0:
                return path_str[idx:]
        return path_str
    ```

1b. **Normalize mode to lowercase** — After `resolved_mode = explicit_mode or detected_mode`,
    add `resolved_mode = resolved_mode.lower()`.

1c. **Populate class_name fallback from training artifacts** — After building
    `roster_entries` from roster.json, attempt to supplement missing class_name
    by loading `training_artifact_{model_name}.json` from rung_dir and reading
    `model_class`.

### Step 2: Fix generator code in report.py

File: `src/bid_euchre/arc_d_v2/report.py`

2a. **Include WARN count in data sanity summary** — In the PRELIMINARY triage section
    (line ~582-589), when data_sanity has no FAILs, check for WARNs and include
    the count: "all checks passed (N WARNINGs)" instead of plain "all checks passed".

### Step 3: Fix committed canonical manifests

Write a one-shot fix script (`scripts/internal/fix_canonical_manifests.py`) that:
- Reads each of the 4 canonical `evidence_manifest.json` files
- Replaces absolute path prefix `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/`
  with empty string (making paths repo-relative)
- Replaces `"class_name": null` with Python class names (matching the regenerated quick/full manifests):
  - modeloespecifico → "ModeloEspecifico"
  - selected_two_stage_av → "TwoStageActionValueBidder"
  - gbt_av → "GBTActionValueBidder"
  - constrained_ols_av → "ActionValueBidder"
  - selected_ols_av → "ActionValueBidder"
  - full_ols_av → "ActionValueBidder"
  - stricthellraiser → "StrictHellRaiser"
  - rankthetank → "RanktheTank"
- Normalizes `"mode": "QUICK"` → `"mode": "quick"`
- Writes the fixed JSON
- Regenerates `00_manifest.md` from the fixed manifest dict using `render_manifest_markdown()`

Run the script, verify output, commit the fixed files, then delete the script.
**Rollback:** If verification fails, `git checkout -- docs/04_reports/arc_d_v2/` recovers all committed report files.

### Step 4: Fix mode casing in quick/full manifests

Targeted edits (no regeneration needed):
- `docs/04_reports/arc_d_v2/r0/quick/evidence_manifest.json`: "QUICK" → "quick"
- `docs/04_reports/arc_d_v2/{r0-r3}/full/evidence_manifest.json`: "FULL" → "full"
- `docs/04_reports/arc_d_v2/r0/quick/00_manifest.md`: mode line fix
- `docs/04_reports/arc_d_v2/{r0-r3}/full/00_manifest.md`: mode line fix

### Step 5: Fix decision reports

5a. `docs/04_reports/arc_d_v2/r2/full/02_decision.md` — Replace the dangling
    `04_rung_decision.md` reference with an inline note: "Override to ADVANCE — H2
    (suit R-squared) failed narrowly (0.604 vs 0.621 threshold, a 2.7% miss on a
    secondary diagnostic metric). H8 skipped (LA-4 roster trim)."

5b. `docs/04_reports/arc_d_v2/r1/canonical/02_decision.md` — Add WARNING caveat:
    "all checks passed (some with WARNINGs — see caveats below)" to match R0's wording.

### Step 6: Validate and tests

- Run existing manifest/report unit tests: `uv run python -m pytest tests/unit/test_evidence_manifest.py tests/unit/test_report_template.py tests/unit/test_reporting_pipeline_smoke.py -v`
- Run `make lint` on changed source files
- Verify no absolute paths remain: `grep -r '/Users/' docs/04_reports/arc_d_v2/`
- Verify no null class_name in canonical: `grep -c '"class_name": null' docs/04_reports/arc_d_v2/*/canonical/evidence_manifest.json`
- Verify mode casing is lowercase: `grep '"mode":' docs/04_reports/arc_d_v2/*/*/evidence_manifest.json`

## Files

### Source code (generator fixes)
- `src/bid_euchre/arc_d_v2/manifest.py` — `_to_repo_relative()` fallback, mode normalization, class_name fallback
- `src/bid_euchre/arc_d_v2/report.py` — WARN count in data sanity summary

### Report data fixes
- `docs/04_reports/arc_d_v2/{r0,r1,r2,r3}/canonical/evidence_manifest.json` — paths, class_name, mode (4 files)
- `docs/04_reports/arc_d_v2/{r0,r1,r2,r3}/canonical/00_manifest.md` — regenerated (4 files)
- `docs/04_reports/arc_d_v2/r0/quick/evidence_manifest.json` — mode casing (1 file)
- `docs/04_reports/arc_d_v2/r0/quick/00_manifest.md` — mode casing (1 file)
- `docs/04_reports/arc_d_v2/{r0,r1,r2,r3}/full/evidence_manifest.json` — mode casing (4 files)
- `docs/04_reports/arc_d_v2/{r0,r1,r2,r3}/full/00_manifest.md` — mode casing (4 files)
- `docs/04_reports/arc_d_v2/r2/full/02_decision.md` — dangling reference (1 file)
- `docs/04_reports/arc_d_v2/r1/canonical/02_decision.md` — WARNING caveat (1 file)

**Total: 2 source files + 20 report files = 22 files**

## Deferred Findings (follow-up issues)

| ID | Finding | Reason for Deferral |
|----|---------|-------------------|
| F1 | R2 canonical comparator_rankings.csv stale | Requires original R2 artifacts to regenerate |
| F5/F6 | R2/R3 FULL manifests missing h2h_battery_full/advance_check entries | Requires FULL artifacts |
| F9 | No SHA256 hashes in manifests | Design enhancement, not a bug |
| F11 | R0 dataset_provenance 25-row smoke entries | Historical artifact, document only |
| F12 | cross_rung_deltas.csv empty | Cross-rung extractor never wired (new feature) |
| F13 | Empty governance metadata fields | Requires plan data unavailable in artifacts |
| F14 | R3 FULL missing feature_importance.png | Requires chart regeneration |

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
