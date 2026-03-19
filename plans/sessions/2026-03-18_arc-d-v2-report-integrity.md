# Arc D v2 Report Integrity Remediation
**Date:** 2026-03-18
**Goal:** Fix 5 validated report-integrity findings: artifact path bug, provenance placeholders, cross-rung decision contamination, R2 seed-label mismatch, and H4 hypothesis text/metric mismatch.

## Context

An external review identified data-integrity issues in the Arc D v2 report bundles.
All 3 P1 findings and 2 of 3 P2 findings were validated against actual files.
The lineage is COMPLETE — these are report/metadata fixes, not experiment reruns.

### Findings Addressed

| ID | Severity | Finding | Fix Strategy |
|----|----------|---------|-------------|
| F1 | P1 | `artifact_inventory.csv` maps all models to `training_artifact_av.json` | Fix `generate_artifact_inventory()` path logic |
| F2 | P1 | `dataset_provenance.csv` has blank n_rows, empty-SHA hashes, and R3 worktree paths | Fix `generate_dataset_provenance()` to populate real data and normalize paths |
| F3 | P1 | R1 `04_rung_decision.md` contains R2 model names/metrics; R2 omits 4/8 models | Regenerate decision reports from canonical CSVs |
| F4 | P1 | R2 FULL label but only seed 42 was run (contract requires 42/123/456) | Relabel R2 to single-seed; add data-quality caveat |
| F5 | P2 | H4 description says "first-bidder accuracy (auction_position=0)" but metric is pooled comparator | Rewrite H4 description to match actual metric |

### Findings NOT Addressed (Design Choices)

| ID | Finding | Rationale |
|----|---------|-----------|
| P2-bid-rate | No upper bid-rate gate | Design choice documented in decision reports — models optimize EV per hand, 98%+ bid rate is expected given the continuation policy |
| P2-objective | Comparator vs H2H divergence | Primary metric (comparator net_eppd) is explicitly declared in lineage plan §15.1; H2H is diagnostic; both champions are transparently named |

## Plan

### PR 1: Fix provenance generation + regenerate tables (F1, F2)

Code changes in `src/bid_euchre/arc_d_v2/tables.py`:

**F1 — `generate_artifact_inventory()` (line 756):**
- Bug: `model_name.split('_')[-1]` → `'av'` for every model (full_ols_av, gbt_av, etc.)
- Fix: Use `f"training_artifact_{model_name}.json"` — matches actual filenames:
  - `training_artifact_full_ols_av.json`
  - `training_artifact_gbt_av.json`
  - `training_artifact_constrained_ols_av.json`
  - `training_artifact_selected_ols_av.json`
  - `training_artifact_selected_two_stage_av.json`

**F2 — `generate_dataset_provenance()` (lines 700-723):**
- Bug 1: `n_rows: None` — never populated
- Fix 1: Read `metadata.n_deals` from training artifact (confirmed field name via live artifact inspection; `n_training_rows` does NOT exist). Fall back to None if absent.
- Bug 2: `sha256: meta.get("dataset_sha256", "")` — the field IS present in metadata but always contains the empty-string SHA256 (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), meaning the dataset was never actually hashed during the build pipeline.
- Fix 2: Detect the empty-string SHA256 VALUE (not key absence) and replace with empty string `""` to avoid presenting a fake digest as real provenance. The empty-string SHA is `hashlib.sha256(b"").hexdigest()`.
- Bug 3: Raw absolute paths from metadata (R3 points to `/Users/.../Bid-Euchre-steward-author/`)
- Fix 3: Apply `_make_repo_relative()` to the dataset path

**Regeneration:** After code fixes, regenerate `artifact_inventory.csv` and `dataset_provenance.csv` for all 4 rungs (R0-R3) by running `generate_rung_tables.py` against each rung's artifacts.

**Tests:**
- Unit test for `generate_artifact_inventory()` verifying per-model distinct paths
- Unit test for `generate_dataset_provenance()` verifying `_make_repo_relative()` is applied, n_deals populates n_rows, and empty-string SHA is neutralized
- Targeted: `uv run python -m pytest tests/unit/test_rung_tables.py -k "artifact_inventory or dataset_provenance"`

**Rollback:** Review `git diff` of regenerated CSVs before committing. If any previously-correct rung (R0/R1/R3) shows unexpected value changes beyond the path/hash/n_rows fixes, revert that rung's CSVs and investigate.

**Files changed:**
- `src/bid_euchre/arc_d_v2/tables.py` — fix 2 functions
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/full/tables/artifact_inventory.csv` — regenerated
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/full/tables/dataset_provenance.csv` — regenerated
- `tests/unit/test_rung_tables.py` — new provenance tests (existing file)

### PR 2: Regenerate R1/R2 decision reports + relabel R2 + fix H4 (F3, F4, F5)

**F3 — Decision report hand-editing:**
- `04_rung_decision.md` is a manually-written narrative document — NO script generates it. `generate_rung_report.py` only produces `01_results.md` and `02_decision.md`. F3 requires direct editing of the markdown.
- **R1 fix:** The comparator rankings table in `04_rung_decision.md` cites 6 models including `constrained_ols_av` and `selected_ols_av` with R2-era metrics. Replace this table with the correct R1 data from `tables/comparator_rankings.csv` (4 models: full_ols_av 2.275, gbt_av 2.0091, selected_two_stage_av 1.9621, modeloespecifico 1.6332). Update any surrounding narrative that references the wrong metrics.
- **R2 fix:** The comparator rankings table in `04_rung_decision.md` shows only 4 of 8 models. Replace with the full R2 roster from `tables/comparator_rankings.csv` (8 models including constrained_ols_av, selected_ols_av, stricthellraiser, rankthetank). Update metrics to match canonical CSV values.
- Also regenerate `01_results.md` via `generate_rung_report.py` for consistency (this IS script-generated).

**F4 — R2 seed relabeling:**
- Edit `docs/04_reports/arc_d_v2/r2/full/00_manifest.md`:
  - Change mode from `FULL` to `FULL (single-seed)`
  - Add caveat: "R2 was evaluated with seed 42 only. The lineage FULL-mode contract (seeds 42/123/456) was not satisfied. R2 advancement was an override decision based on QUICK evidence; FULL artifacts are seed-42 supplementary evidence."
- Edit `docs/04_reports/arc_d_v2/r2/full/04_rung_decision.md` (post-regeneration):
  - Remove the false claim "50,000 deals × 3 seeds"
  - Add seed-coverage caveat in the Data Quality section

**F5 — H4 hypothesis text:**
- Edit `plans/arc_d_v2/r1/hypotheses.json` line 43:
  - Old: `"Position features improve first-bidder accuracy (auction_position=0)"`
  - New: `"GBT pooled comparator net_eppd remains above 2.0 with position features added"`
  - Add `_note`: `"Originally described as testing position-specific accuracy, but the metric is pooled comparator. Corrected to match the actual evaluation."`

**Validation:**
- Grep cross-check: `rg "full_ols_av|gbt_av|constrained_ols_av|selected_ols_av" docs/04_reports/arc_d_v2/r{1,2}/full/04_rung_decision.md`
- Verify R1 decision cites only the 4 models in R1's comparator_rankings.csv
- Verify R2 decision cites all 8 models in R2's comparator_rankings.csv
- Verify R2 manifest no longer claims 3-seed FULL mode

**Files changed:**
- `docs/04_reports/arc_d_v2/r1/full/01_results.md` — regenerated
- `docs/04_reports/arc_d_v2/r1/full/04_rung_decision.md` — regenerated
- `docs/04_reports/arc_d_v2/r2/full/01_results.md` — regenerated
- `docs/04_reports/arc_d_v2/r2/full/04_rung_decision.md` — regenerated + R2 caveats
- `docs/04_reports/arc_d_v2/r2/full/00_manifest.md` — relabeled
- `plans/arc_d_v2/r1/hypotheses.json` — H4 text corrected

## Parallelism

PR 1 and PR 2 are **independent** — no shared file edits.

- PR 1 touches: `tables.py`, `artifact_inventory.csv` (×4 rungs), `dataset_provenance.csv` (×4 rungs), `test_rung_tables.py`
- PR 2 touches: `04_rung_decision.md` (R1, R2), `00_manifest.md` (R2), `hypotheses.json` (R1)

`01_results.md` does NOT embed provenance tables (it embeds comparator_rankings, H2H, model performance). The provenance CSVs are standalone committed artifacts, not inlined into results markdown. Therefore the PRs are truly parallel with no sequencing requirement.

## Acceptance Criteria

- [ ] `artifact_inventory.csv` has distinct per-model filenames across all 4 rungs
- [ ] `dataset_provenance.csv` has populated n_rows (where metadata supports it) and repo-relative paths
- [ ] R1 `04_rung_decision.md` cites only R1 models (4 models, not 6)
- [ ] R2 `04_rung_decision.md` cites all 8 R2 models
- [ ] R2 manifest labeled `FULL (single-seed)` with explicit caveat
- [ ] H4 description matches the actual pooled-comparator metric
- [ ] `make check` passes
- [ ] No empty-string SHA256 hashes masquerading as real digests (either real hash or explicitly empty)

## Outcome

- **PR #916** (PR1 — provenance code fix + CSV regeneration): ✅ MERGED.
- **PR #917** (PR2 — decision narratives, R2 relabel, H4 fix): ✅ MERGED.
- Follow-up noted: R2 `hypothesis_outcomes.csv` still contains R1-era values (data generation issue, not narrative). Separate task.
- Deviations: PR1 regenerated 24 CSVs (quick/canonical/full × 4 rungs) instead of only the 8 FULL CSVs — broader but harmless.
