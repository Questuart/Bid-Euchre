<!-- review-tier: governing -->

# Arc D v2 Repair and Autonomous Regeneration Runbook

**Date:** 2026-03-16
**Status:** PROPOSED
**Scope:** Hard-archive non-canonical active Arc D v2 outputs, materially amend the
pre-`r3` continuation/dataset contract, preserve the existing smoke/quick/full roster
setup, and regenerate the lineage end to end with autonomous smoke -> quick -> full
execution.
**Governing references:** `plans/arc_d_v2/lineage_plan.md`,
`plans/arc_d_v2/amendments.md`, `plans/arc_d_v2/roster.json`,
`plans/arc_d_v2/roster_overlay_full.json`

---

## 1. Decision

Repair `arc_d_v2`; do not redefine it. The scientific intent (benchmark new model
architectures against a fixed baseline) is preserved. The execution and data contracts
are materially amended to eliminate continuation-policy drift and mode-scale
inconsistencies that compromised the original runs. Previous outputs generated under
the drifted contract are non-comparable with the repaired outputs and must be archived.

The repaired contract is:

1. Pre-`r3` (`r0`, `r1`, `r2`) always uses the frozen `r0` anchor
   `data/artifacts/arc_d/r0/hybrid_r0_full.json` as the continuation artifact.
2. Pre-`r3` datasets are shared by rung within each mode:
   one shared base dataset for `smoke`, one for `quick`, and one for `full`.
3. `r3` remains a separate dataset build because moon/loner expands the action space.
4. The roster is preserved exactly:
   `smoke` and `quick` use the base roster from `plans/arc_d_v2/roster.json`;
   `full` preserves the existing exclusions in `plans/arc_d_v2/roster_overlay_full.json`.
5. Existing active v2 outputs are hard-archived and removed from active paths before
   any repair or rerun work begins.

This runbook is intended as a one-shot handoff to another agent.
The agent should not improvise alternate contracts, paths, or seed policies.

---

## 2. Goals

1. Make the repaired v2 pipeline fully reproducible in `smoke`, `quick`, and `full`.
2. Eliminate continuation-policy drift across `r0`-`r2`.
3. Preserve the current roster and FULL roster overlay behavior.
4. Create a clean archive boundary between old non-canonical outputs and the new rerun.
5. Give the next agent an explicit execution order with stop conditions and acceptance checks.

---

## 3. Anti-Goals

1. Do not redefine v2 as a self-play or promoted-teacher lineage.
2. Do not change the roster membership or FULL exclusions.
3. Do not add moon/loner to pre-`r3` shared datasets.
4. Do not silently reuse existing active run/report/state outputs.
5. Do not use destructive repo cleanup shortcuts such as `git reset --hard` or
   `git clean -fdx`.

---

## 4. Canonical Repaired v2 Contract

### 4.1 Continuation Artifact Contract

- Pre-`r3` continuation artifact:
  `data/artifacts/arc_d/r0/hybrid_r0_full.json`
- Loader path:
  `scripts/internal/generate_action_value_dataset.py::load_continuation_policy()`
- Expected loader class:
  `HybridOLSaBidder`
- Rung-local continuation artifact probing is not allowed for `r0`, `r1`, or `r2`.

### 4.2 Mode Contract

Use the following repaired mode contract for autonomous regeneration:

| Mode | Shared Pre-`r3` Dataset | Dataset-Build Seeds | Run Seeds | Roster |
|------|--------------------------|---------------------|-----------|--------|
| `smoke` | 25 deals = 100 hands | `[1001]` | `[42]` | base roster |
| `quick` | 5,000 deals = first shard only | `[1001]` | `[42]` | base roster |
| `full` | 50,000 deals = 10 x 5,000 shards | `[1001..1010]` | `[42,123,456]` | FULL overlay preserved |

Notes:

- `smoke` size is fixed to 25 deals so the dataset is exactly 100 hands.
  **This is a contract change from the original `SMOKE = 50` in `lineage_plan.md`.**
  The reduction to 25 deals ensures exactly 100 hands (25 × 4 seats), which is a
  cleaner validation unit. Original 50-deal smoke outputs are archived as non-canonical.
- `quick` is one 5,000-deal shard only. **This is a contract change from the original
  `QUICK = 2,500` in `lineage_plan.md` and `MODE_DEALS`.** The increase to 5,000
  aligns quick with the full shard unit size, but it means repaired quick outputs are
  not directly comparable with the original 2,500-deal quick outputs. The original
  quick outputs must be archived as non-canonical.
- `full` is ten 5,000-deal shards.
- Dataset-build seeds and run seeds are different controls and must remain separate.

### 4.3 Shared Dataset Scope

- Shared by rung:
  `r0`, `r1`, `r2`
- Not shared:
  `r3`

**Rationale:** Combined with the fixed R0 anchor (§4.1), shared pre-R3 datasets
ensure that rung-to-rung comparisons isolate model capacity differences (Goal 1,
lineage plan §3) — the dataset, continuation policy, and feature set are identical
across R0/R1/R2, so the only variable is the model architecture.

`r3` keeps its own mode-sized dataset builds because it adds moon/loner actions.
`r3` still uses the fixed `r0` continuation artifact and the same dataset-build seed
registry by mode; only the action space changes and the dataset is not shared with
`r0`/`r1`/`r2`.

### 4.3.1 Expected Row Counts and R3 Chunk Size

Pre-`r3` deals produce ~40 actions per seat (pass + ~13 bid levels × 3 contract
families). R3 adds +12 moon/loner counterfactuals per seat (~52 actions/seat total).

| Mode | Pre-`r3` rows (approx) | R3 rows (approx) |
|------|----------------------|-----------------|
| `smoke` (25 deals) | ~4,000 | ~5,200 |
| `quick` (5k deals) | ~800,000 | ~1,040,000 |
| `full` (50k deals) | ~8,000,000 | ~10,400,000 |

R3 deals are heavier both in row count and per-deal compute (moon exchange +
3-player loner trick play). On a 16GB machine:
- **Pre-`r3` chunk size: 5,000 deals** (~500 MB peak RSS per chunk)
- **R3 chunk size: 1,000 deals** (~200 MB peak RSS per chunk, accounting for +30%
  row count and heavier per-deal simulation)

### 4.4 Dataset Schema Contract

The repaired pre-`r3` dataset schema must add:

- `dataset_seed` (int)
- `deal_uid` (string)
- `hand_uid` (string)

Exact definitions:

- `deal_uid = f"{dataset_seed}:{deal_id}"`
- `hand_uid = f"{dataset_seed}:{hand_id}"`

Rules:

- `deal_id` remains a local-within-shard integer (0 to n_deals-1).
- `hand_id` remains `deal_id * 4 + focal_seat` within a shard — familiar for debugging
  but not globally unique across seeds.
- `deal_uid` and `hand_uid` are the canonical global grouping keys.
- Train/val/test split must use `deal_uid` when present.
- GroupKFold / forward selection grouping must use `hand_uid` when present.
- Unique deal counts in provenance and artifacts must use `deal_uid`, not `deal_id`.

### 4.5 Output Layout Contract

Use deterministic lineage-level dataset roots:

- `data/runs/arc_d_v2/base_datasets/pre_r3/smoke/seed_1001/`
- `data/runs/arc_d_v2/base_datasets/pre_r3/quick/seed_1001/`
- `data/runs/arc_d_v2/base_datasets/pre_r3/full/shards/seed_<dataset_seed>/`

The canonical shared dataset roots consumed by training should be:

- `data/runs/arc_d_v2/base_datasets/pre_r3/smoke/`
- `data/runs/arc_d_v2/base_datasets/pre_r3/quick/`
- `data/runs/arc_d_v2/base_datasets/pre_r3/full/`

The training loader must use **recursive shard discovery**: given a dataset root,
it globs `**/part_*.parquet` (or `**/datasets/action_value/*.parquet` for nested
seed directories), sorts by path, and concatenates. No assembled second copy of
the data is created. This is simpler, avoids doubling storage, and eliminates a
second provenance surface.

Do not mix multiple dataset-build seeds into one shard directory.

---

## 5. Current Repo State and Preflight Footguns

### 5.1 Dirty Worktree Snapshot (Observed 2026-03-16)

Active v2 runtime/output paths currently dirty:

- `plans/arc_d_v2/r0/advance_check.json`
- `plans/arc_d_v2/r0/execution_log.jsonl`
- `plans/arc_d_v2/r0/state.json`
- `plans/arc_d_v2/r1/execution_log.jsonl`
- `plans/arc_d_v2/r1/state.json`
- `plans/arc_d_v2/r2/state.json` (deleted)
- `plans/arc_d_v2/r1/heartbeat`
- `docs/04_reports/arc_d_v2/r0/full/` (untracked)

Potentially unrelated dirty/untracked paths that must **not** be touched without
explicit confirmation:

- `.claude/worktrees/`
- `docs/04_reports/qa/`
- `plans/arc_d_v2/full_chart_suite_implementation.md`
- `plans/arc_d_v2/reporting_pr_scope_full_chart_suite.md`
- `plans/sessions/2026-03-16_chunked-dataset-generation.md`
- `plans/sessions/2026-03-16_plans-directory-cleanup.md`

### 5.2 Preflight Rules

Before any code changes or reruns:

1. Run `git status --short`.
2. If any dirty paths exist outside the scoped v2 runtime/output paths above,
   stop and ask for human review before touching them.
3. Create a new working branch before cleanup or source edits.
4. Do not start repair work until active v2 runtime/output paths have been archived
   and removed from active locations.

---

## 6. Hard Archive and Demotion Plan

### 6.1 Archive Classification

The following are **source-of-truth plan/config files** and stay in place:

- `plans/arc_d_v2/lineage_plan.md`
- `plans/arc_d_v2/amendments.md`
- `plans/arc_d_v2/roster.json`
- `plans/arc_d_v2/roster_overlay_full.json`
- `plans/arc_d_v2/r*/plan.md`
- `plans/arc_d_v2/r*/hypotheses.json`
- `plans/arc_d_v2/r*/checkpoints.md`

The following are **generated runtime/output artifacts** and must be hard-archived:

- `docs/04_reports/arc_d_v2/`
- `data/artifacts/arc_d_v2/`
- `data/runs/arc_d_v2/`
- `data/runs/av_*` — **Critical: the orchestrator writes Step 1/2 outputs to
  `data/runs/av_<rung>_<mode>_<seed>/` paths (not under `data/runs/arc_d_v2/`).
  These must be archived or removed.** Partial outputs from killed runs (e.g.,
  `data/runs/av_r0_full_42/`) are included. Glob `data/runs/av_*` to catch all.
- `plans/arc_d_v2/r*/advance_check.json`
- `plans/arc_d_v2/r*/execution_log.jsonl`
- `plans/arc_d_v2/r*/state.json`
- `plans/arc_d_v2/r*/heartbeat`

### 6.2 Archive Root

Use a stable archive root outside the active repo paths.

**Primary:** `../Bid-Euchre-archive/arc_d_v2_noncanonical_20260316/`

If the parent directory (`../Bid-Euchre-archive/`) is not writable or does not
exist, the agent should:
1. Attempt to create it (`mkdir -p`).
2. If creation fails (e.g., sandbox restriction), fall back to an in-workspace
   archive root: `archive/arc_d_v2_noncanonical_20260316/` (at the repo root).
   Add `archive/` to `.gitignore` if not already present.
3. If neither location is writable, stop and request human approval.

Required subdirectories:

- `reports/`
- `artifacts/`
- `runs/`
- `runtime_state/`
- `manifests/`

### 6.3 Archive Procedure

1. Create `ARCHIVE_ROOT`.
2. Write an archive manifest under
   `plans/arc_d_v2/archive_manifest_2026-03-16.md` that records:
   - archive timestamp
   - reason for demotion
   - old path -> archived path mapping
   - whether the archived item was tracked or untracked
3. Move all generated runtime/output paths from §6.1 to `ARCHIVE_ROOT`.
   - For **untracked** files/directories: `mv` to archive root.
   - For **tracked committed** files (e.g., `docs/04_reports/arc_d_v2/`,
     `plans/arc_d_v2/r*/advance_check.json`): `cp` to archive root first,
     then `git rm -r` to remove from the repo. The `git rm` deletions become
     part of the repair commit.
4. Remove the active copies from the repo working tree after the move succeeds.
5. Mark the archived material as `quarantined` / `non-canonical` in the manifest text.

### 6.4 Demotion Rationale Text

Use this exact reason in the archive manifest:

> Archived as non-canonical on 2026-03-16 due to repaired v2 rerun. Pre-`r3`
> continuation-policy execution drifted from the governing fixed-anchor contract,
> mode-scale contracts were inconsistent between plan and code, and active runtime
> state/report paths were reset to permit full autonomous regeneration.

### 6.5 Post-Archive Repo Cleanliness Gate

After archive and before implementation work:

- `git status --short` must show only:
  - intentional source file edits for the repair work, or
  - any human-approved unrelated files left untouched

If archived runtime/output files still appear as dirty, stop and resolve before coding.

---

## 7. Required Implementation Workstreams

### 7.1 Contract and Plan Alignment

Files:

- `plans/arc_d_v2/lineage_plan.md`
- `plans/arc_d_v2/amendments.md`
- `plans/arc_d_v2/v2_regeneration_repair_runbook.md`

Changes:

1. Align the lineage plan with the repaired mode contract:
   - `smoke`: 25 deals / 100 hands
   - `quick`: 5,000 deals
   - `full`: 50,000 deals via 10 shards
2. Explicitly separate dataset-build seeds from run seeds.
3. Explicitly document that pre-`r3` datasets are shared across `r0`/`r1`/`r2`.
4. Preserve the current FULL roster overlay as-is.
5. Add a new amendment (suggested `LA-5`) covering:
   - fixed-anchor enforcement for pre-`r3`
   - shared dataset reuse for `r0`-`r2`
   - repaired mode/data-build contract
   - QUICK scale change from 2,500 to 5,000 deals (with rationale: aligns with
     shard unit size; original 2,500-deal outputs archived as non-canonical)
   - separation of dataset-build seeds from run seeds

### 7.2 Dataset Build Orchestration

Files:

- `src/bid_euchre/arc_d_v2/orchestration.py`
- `src/bid_euchre/arc_d_v2/paths.py`
- new helper or script:
  `scripts/internal/build_pre_r3_base_dataset.py`

Changes:

1. Create a canonical dataset builder for pre-`r3` that:
   - accepts `--mode smoke|quick|full`
   - enforces the dataset-build seed list for that mode
   - enforces the fixed `r0` continuation artifact
   - writes the deterministic dataset roots from §4.5
   - validates each shard and the assembled root
2. Update Step 1 for `r0`/`r1`/`r2` to:
   - build the shared base dataset if missing, or
   - verify and reuse it if present
3. Update Step 1 for `r3` to:
   - retain a rung-local dataset build
   - use the same dataset-build seed registry by mode as pre-`r3`
   - use the fixed `r0` continuation artifact
   - enable `--include-moon-loner`
4. **Hard-enforce the R0 anchor for pre-`r3`.**
   In `execute_step_1()` (line 683–696) and `execute_step_2()` (line 771–784),
   replace the rung-local probe (`data/artifacts/arc_d/<rung>/hybrid_<rung>_full.json`
   with fallback to R0) with a direct hard-coded path to the R0 anchor:
   `data/artifacts/arc_d/r0/hybrid_r0_full.json`. The rung-local probe must be
   **removed entirely**, not left as a dead fallback. For `r3`, the same R0 anchor
   is used but `--include-moon-loner` is added.
5. **Migrate Step 1 output paths for pre-`r3`.**
   `execute_step_1()` currently writes to `data/runs/av_{rung}_{mode}_{seed}/`
   (line 700). For pre-`r3` rungs, Step 1 must instead point to the shared base
   dataset root from §4.5 and skip generation if the dataset already exists.
   For `r3`, the legacy per-rung output path pattern is retained.
6. **Add R3-specific chunk size.**
   In `execute_step_1()`, when rung is `r3` and mode is `full` or `quick`,
   pass `--chunk-size 1000` instead of `--chunk-size 5000`.

### 7.3 Dataset Schema and Loader Repair

Files:

- `scripts/internal/generate_action_value_dataset.py`
- `scripts/internal/train_action_value.py`

Changes:

1. Add `dataset_seed`, `deal_uid`, and `hand_uid` to generated rows.
2. Keep `deal_id` and `hand_id` for shard-local debugging.
   **Backward compatibility note:** Do NOT add `dataset_seed`, `deal_uid`, or
   `hand_uid` to `METADATA_COLS` in `train_action_value.py` (line 67). The
   `load_dataset()` validation checks `METADATA_COLS` as required columns —
   adding them would break loading of pre-repair parquet files. Instead, treat
   them as optional columns: check for their presence after load, but do not
   require them. After the archive procedure removes all pre-repair data from
   active paths, this is a safety net, not a functional requirement.
3. Update `load_dataset()` to support recursive shard discovery.
   When `parquet_path` is a directory, change from `path.glob("part_*.parquet")`
   (line 223, flat glob) to `path.rglob("part_*.parquet")` (recursive glob).
   This is required because the shared dataset layout nests parquet files under
   `shards/seed_<n>/datasets/action_value/part_*.parquet`. The flat glob would
   find zero files when pointed at the canonical root.
4. Update `split_by_deal()` to use `deal_uid` when present.
   Exact contract: if `deal_uid` column exists, split on it. If `deal_uid` is
   absent but the dataset contains multiple distinct `dataset_seed` values, raise
   `ValueError` (multi-seed assembly without global IDs is unsafe). If `deal_uid`
   is absent and only one `dataset_seed` exists (or `dataset_seed` is absent),
   fall back to `deal_id` for backward compatibility with single-seed datasets.
5. Update forward-selection grouping to use `hand_uid` when present.
6. Update unique-deal counting and artifact metadata to use `deal_uid`.

### 7.4 Reporting and Table Pipeline Repair

Files:

- `src/bid_euchre/arc_d_v2/tables.py`
- `scripts/internal/generate_rung_tables.py`
- any chart/report helper that assumes a single `action_value.parquet`

Changes:

1. Update dataset provenance generation to record:
   - shared base dataset path
   - shared base dataset id
   - dataset-build seeds
   - continuation artifact path/hash
2. Update any code that assumes `seed_<s>/datasets/action_value.parquet`
   to also accept the shared dataset root for pre-`r3`.
3. Ensure `r3` reporting still works with its rung-local dataset path.

### 7.5 Provenance and Artifact Metadata

Files:

- `scripts/internal/train_action_value.py`
- any artifact builders / manifest writers

Changes:

Every artifact trained from the repaired pipeline must record:

- `base_dataset_id`
- `base_dataset_path`
- `base_dataset_sha256`
- `dataset_build_seeds`
- `continuation_artifact_path`
- `continuation_artifact_sha256`
- `run_seed`

---

## 8. Required Test Coverage

### 8.1 Unit Tests

Update or add coverage in:

- `tests/unit/test_action_value_dataset.py`
- `tests/unit/test_train_action_value.py`
- `tests/unit/test_rung_orchestrator.py`
- `tests/unit/test_rung_tables.py`

Required assertions:

1. Pre-`r3` Step 1 and Step 2 always use the fixed `r0` continuation artifact.
   **Specifically:** test that `r1` and `r2` Step 1 command does NOT contain
   `hybrid_r1_full.json` or `hybrid_r2_full.json` even if those paths exist at
   runtime. The rung-local probe code must be gone, not just unreachable.
2. Generated datasets include `dataset_seed`, `deal_uid`, and `hand_uid`.
3. Concatenating multiple dataset-build seeds produces no UID collisions.
4. Shared dataset roots can be loaded by the training pipeline via recursive
   `rglob("part_*.parquet")` — test with a nested `shards/seed_X/` layout.
5. `split_by_deal()` uses `deal_uid` when present. **Also test:** raises
   `ValueError` if multiple `dataset_seed` values exist but `deal_uid` is absent.
   Falls back to `deal_id` for single-seed datasets without `deal_uid`.
6. Dataset provenance reflects the shared dataset contract.
7. FULL mode still preserves the existing overlay exclusions.
8. R3 datasets contain `is_moon=1` and `is_loner=1` rows.

### 8.2 Smoke Integration Path

Required smoke integration proof before quick/full:

1. Build the `smoke` pre-`r3` shared dataset.
2. Build the `smoke` `r3` dataset.
3. Run the smoke pipeline end to end for `r0` -> `r3`.
4. Verify:
   - no stale archive/runtime contamination
   - shared dataset reused across `r0`/`r1`/`r2`
   - `r3` uses its own dataset
   - all smoke artifacts point to the correct continuation artifact

---

## 9. Autonomous Execution Order

### 9.1 Branch and Preflight

1. Create a dedicated branch.
2. Capture `git status --short` and compare against §5.1.
3. Archive active v2 outputs per §6.
4. Confirm the repo is clean enough to begin implementation.

### 9.2 Implement and Test the Repair

1. Land all source changes from §7.
2. Run the targeted unit tests from §8.
3. Do not begin smoke execution until all targeted tests pass.

### 9.3 Smoke Regeneration

1. Build `smoke` shared pre-`r3` dataset:
   - 25 deals
   - dataset-build seed `1001`
2. Build `smoke` `r3` dataset:
   - 25 deals
   - dataset-build seed `1001`
   - fixed `r0` continuation
   - moon/loner enabled
   - expected: ~5,200 rows (~52 actions/seat × 4 seats × 25 deals)
3. Run the full smoke pipeline for `r0`, `r1`, `r2`, `r3`.
   **Run seed: `42` only.** Do not use dataset-build seeds as run seeds.
4. If smoke fails at any step, stop. Do not continue to quick.
   **Definition of failure:** A step fails if any of:
   - the subprocess exits with non-zero code
   - `state.json` marks the step as `"failed"`
   - Gate X1 validation assertions fail for dataset steps
   - the advance check produces a hypothesis with `pass=false` and `gating=true`

### 9.4 Quick Regeneration

1. Build `quick` shared pre-`r3` dataset:
   - 5,000 deals
   - dataset-build seed `1001`
2. Build `quick` `r3` dataset:
   - 5,000 deals
   - dataset-build seed `1001`
   - fixed `r0` continuation
   - moon/loner enabled
   - chunk size: 1,000 deals
   - expected: ~1,040,000 rows
3. Run the full quick pipeline for `r0`, `r1`, `r2`, `r3`.
   **Run seed: `42` only.** Do not use dataset-build seeds as run seeds.
4. If quick fails technical validation, stop. Do not continue to full.

### 9.5 Full Regeneration

1. Build `full` shared pre-`r3` dataset:
   - 10 shards
   - 5,000 deals each
   - dataset-build seeds `1001..1010`
2. Validate the assembled shared root:
   - `50,000` unique `deal_uid`
   - `200,000` unique `hand_uid`
3. Build `full` `r3` dataset using the repaired rung-local path:
   - `50,000` deals total
   - dataset-build seeds `1001..1010`
   - fixed `r0` continuation
   - moon/loner enabled
   - **chunk size: 1,000 deals** (not 5,000 — R3 moon/loner actions are heavier)
4. Run the full pipeline for `r0`, `r1`, `r2`, `r3`.
   **Run seeds: `42`, `123`, `456`.** Do not use dataset-build seeds as run seeds.
5. Generate final reports/tables/charts from the new canonical outputs only.

---

## 10. Same Smoke/Quick/Full Roster Setup

This must be preserved exactly:

- `smoke`: base roster from `plans/arc_d_v2/roster.json`
- `quick`: base roster from `plans/arc_d_v2/roster.json`
- `full`: base roster plus exclusions from `plans/arc_d_v2/roster_overlay_full.json`

Do not normalize `full` to the smoke/quick roster.
Do not expand smoke/quick to the FULL overlay.

---

## 11. Stop Conditions

Stop and ask for human review if any of the following occur:

1. Dirty paths outside the scoped v2 runtime/output set appear before archive.
2. Archive move fails for any active generated output path.
3. The shared pre-`r3` dataset root cannot be loaded deterministically.
4. UID collisions appear across dataset-build seeds.
5. Any pre-`r3` rung still tries to use `hybrid_r1_full.json` or another rung-local continuation.
6. The FULL overlay changes unintentionally.
7. The repaired pipeline requires a roster or hypothesis change to run.

---

## 12. Acceptance Criteria

The rerun is complete only if all of the following are true:

1. Active non-canonical v2 outputs have been hard-archived and removed from active paths.
2. The repo has a clean boundary between archived outputs and repaired source code.
3. Pre-`r3` shared datasets exist for `smoke`, `quick`, and `full`.
4. `r0`, `r1`, and `r2` reuse the same shared dataset for a given mode.
5. `r3` uses its own mode-sized dataset with the fixed `r0` continuation artifact
   and `--include-moon-loner` enabled. The R3 dataset must contain `is_moon=1` and
   `is_loner=1` rows.
6. Smoke, quick, and full all preserve the current roster setup, including FULL overlay exclusions.
7. All targeted tests pass.
8. Final artifacts/report bundles are regenerated from the repaired pipeline only.
9. Archived outputs are documented in `archive_manifest_2026-03-16.md`.

---

## 13. Recommended First Execution Commitments

The next agent should execute in this order and commit between phases:

1. Archive + repo hygiene preparation
2. Source repair + tests
3. Smoke regeneration
4. Quick regeneration
5. Full regeneration
6. Final report/provenance synthesis

Each phase should leave the repo in a reviewable state before moving to the next.

---

## 14. Outcome

<!-- Filled after implementation -->

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN
- Notes: deviations from plan
