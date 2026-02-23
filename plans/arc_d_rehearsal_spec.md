# Arc D Agentic Delivery Rehearsal Spec

**Type:** Rehearsal task card for an execution agent
**Date:** 2026-02-22
**Prerequisite:** Arc D Waves 0–3 complete (PRs #389–#400 merged, R0 PROMOTED)

---

## What This Is

An **agentic delivery rehearsal** — not a smoke test, not a production run.

You (the agent) will execute every remaining Arc D phase (R1a through F) at
small scale. The goal is to test whether the execution plan is clear enough
for autonomous execution, not to produce statistically meaningful artifacts.

**Primary output:** Per-phase scoping notes documenting where the plan was
clear, where it was ambiguous, and what you had to invent.

**Secondary output:** Working (tiny) code and artifacts that exercise the
full pipeline end-to-end.

---

## How To Use This Document

1. Read `plans/arc_d_execution_plan.md` — that is the authoritative plan.
2. Execute each phase below in order, following the execution plan's handoff
   instructions (§9, sections H-R1a through H-F).
3. Apply the **overrides** in this document (smaller data, relaxed gates).
4. After completing each phase, write a scoping note before moving on.
5. Commit after each phase boundary (enforces handoff discipline).

---

## Overrides (Rehearsal vs. Production)

| Parameter | Production | Rehearsal |
|-----------|-----------|-----------|
| Dataset size (n_per) | 50,000 | 500 |
| Lambda tuning n_per (R5b) | 10,000 | 500 |
| Evaluation seeds | 42, 43, 44 | 42 only (except R1b: run 42+43 to exercise sensitivity path once) |
| Promotion thresholds | Statistical (`max(0.01, 1.5*SE)`) | Log the result, advance regardless |
| Semantic gate failures | Block promotion | Log and continue |
| `make check` | Must pass | Must pass (no override) |
| Tests per feature extractor | 4+ | 2+ (happy path + edge case) |
| Artifact namespace | `data/artifacts/arc_d/r{N}/` | `data/artifacts/arc_d_rehearsal/r{N}/` |
| Registry file | `docs/02_agent/MODEL_ARC_RUNS.md` | `data/artifacts/arc_d_rehearsal/REGISTRY.md` |
| Branch | One per PR | Single rehearsal worktree, commit per phase |
| PRs | One per concept | None — all work in rehearsal branch |

### Script Command Templates (MUST use these — defaults write to production paths)

**Promotion gate** (exits non-zero on HALT — use `|| true` to prevent aborting):
```bash
PYTHONPATH=src uv run python scripts/internal/run_arc_d_gate.py \
  --bundle data/artifacts/arc_d_rehearsal/r{N}/rung_bundle_r{N}.json \
  || true
# The `|| true` prevents a HALT exit code from aborting the rehearsal.
# Always check promotion_decision_r{N}.json for the actual result.
```

**Registry update** (default writes to production — always pass `--registry`):
```bash
PYTHONPATH=src uv run python scripts/internal/update_arc_registry.py \
  --bundle data/artifacts/arc_d_rehearsal/r{N}/rung_bundle_r{N}.json \
  --decision data/artifacts/arc_d_rehearsal/r{N}/promotion_decision_r{N}.json \
  --registry data/artifacts/arc_d_rehearsal/REGISTRY.md
```

**Dashboard** (default writes to production — always pass `--artifacts-base` and `--output`):
```bash
PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
  --artifacts-base data/artifacts/arc_d_rehearsal \
  --output data/artifacts/arc_d_rehearsal/dashboard.md
```

**Training pipeline** (always use `--output` to rehearsal namespace):
```bash
PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
  --run-dir <dataset_path> \
  --seed 42 \
  --output data/artifacts/arc_d_rehearsal/r{N}/ \
  --rung-id r{N} \
  --arm-mode both
```

**Hard constraints that are NOT relaxed:**
- `make check` must pass after every phase
- Deterministic seeds per phase (R1b: 42+43, all others: 42 only)
- Worktree-only workflow
- Artifact freezing still required (content-hash verification)
- Split discipline (train/val/test partitions, grouped by hand_id)
- Gate/registry CLIs must be used (no manual artifact construction)
- Lambda grid search must execute all 6 values (R5b)

---

## Worktree Setup

```bash
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre
git worktree add ../Bid-Euchre-rehearsal -b rehearsal/arc-d-full
cd ../Bid-Euchre-rehearsal

# Symlink run data (read-only source datasets) from main checkout
ln -s /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/runs data/runs

# Copy R0 artifacts into rehearsal namespace (do NOT symlink production artifacts)
mkdir -p data/artifacts/arc_d_rehearsal/r0
cp /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r0/* \
   data/artifacts/arc_d_rehearsal/r0/

# NOTE: rung_bundle_r0.json contains production-relative paths internally.
# This is fine — R0 artifacts are read-only inputs. Do not use the bundle's
# internal paths to resolve file locations; use the rehearsal namespace directly.

# SAFETY: Do NOT create data/artifacts/arc_d/ in the worktree.
# All rehearsal artifacts go under data/artifacts/arc_d_rehearsal/ only.

# Environment
uv sync --all-extras && uv pip install pre-commit
```

---

## Phase Checklist

Execute these in order. Each phase maps to a section in the execution plan.

### Phase 1: R1a — Partner Context Infrastructure

**Plan reference:** `arc_d_execution_plan.md` §9 H-R1a (lines 1533–1585)

**What to build:**
1. Add `auction_history: list[dict]` field to `BiddingObservation`
2. Wire `_transcript` into `BiddingObservation` in the simulation loop
3. Extend `BiddingDatasetCollector` to capture auction history per decision row
4. Create `src/bid_euchre/features/bidding_context.py` with
   `extract_partner_context(auction_history, seat) -> dict[str, float]`
5. Generate rehearsal auction dataset (seed=42, n_per=500) using
   HybridOLSaBidder R0 artifact from `data/artifacts/arc_d_rehearsal/r0/hybrid_r0.json`
6. Tests in `tests/unit/test_bidding_context.py`

**Rehearsal overrides:**
- n_per=500 (not 50,000) for auction dataset generation
- 2+ tests (not 5+)

**Commit message pattern:** `rehearsal(r1a): partner context infrastructure`

**Scoping note:** `plans/rehearsal_notes/r1a.md`

---

### Phase 2: R1b — R1 Dual-Arm Training + Eval + Promotion

**Plan reference:** `arc_d_execution_plan.md` §4 Phase R1 (lines 403–464)
and §9 H-R{N}b template (lines 1587–1646)

**What to do:** Follow the 10-step H-R{N}b template:
1. Feature selection (OLSa_Full): forward select from 39 hand + 4 partner context
2. Feature selection (OLSa): locked 3/1/1 base + 4 partner context candidates
3. Train OLSa_Full → freeze → `data/artifacts/arc_d_rehearsal/r1/hybrid_r1_full.json`
4. Train OLSa → freeze → `data/artifacts/arc_d_rehearsal/r1/hybrid_r1.json`
   Train control → `data/artifacts/arc_d_rehearsal/r1/hybrid_r1_control.json`
5. Semantic gate on val+test (both arms)
6. Evaluation: seeds 42+43, n_per=500 (R1b exercises sensitivity path)
7. Write rung bundle → validate
8. Run promotion gate (see command templates below) → log result, advance regardless
9. Write to rehearsal registry (see command templates below)
10. Generate rung report + dashboard (see command templates below)

**Rehearsal overrides:**
- Seeds 42+43 (exercises sensitivity path once; R2b+ use seed 42 only)
- n_per=500 for evaluation
- Log promotion gate result but always advance to next rung

**Commit message pattern:** `rehearsal(r1b): R1 dual-arm training + eval`

**Scoping note:** `plans/rehearsal_notes/r1b.md`

---

### Phase 3: R2a — Opponent Context Features

**Plan reference:** `arc_d_execution_plan.md` §9 H-R{N}a template (lines 1648–1675)
and §4 Phase R2 (lines 466–492)

**What to build:**
- Add `extract_opponent_context(auction_history, seat) -> dict[str, float]`
  to `src/bid_euchre/features/bidding_context.py`
- Returns: `opponent_max_bid`, `opponent_bid_count`, `opponent_suit_signal`,
  `opponent_aggression`
- 2+ tests in `tests/unit/test_bidding_context.py`

**Commit message pattern:** `rehearsal(r2a): opponent context features`

**Scoping note:** `plans/rehearsal_notes/r2a.md`

---

### Phase 4: R2b — R2 Dual-Arm Training + Eval + Promotion

**Plan reference:** Same H-R{N}b template. Cumulative features: 39 hand + 8 context
(4 partner + 4 opponent).

**Follow the same 10-step pattern as R1b** with artifacts under
`data/artifacts/arc_d_rehearsal/r2/`.

**Commit message pattern:** `rehearsal(r2b): R2 dual-arm training + eval`

**Scoping note:** `plans/rehearsal_notes/r2b.md`

---

### Phase 5: R3a — Full Transcript Context Features

**Plan reference:** `arc_d_execution_plan.md` §9 H-R{N}a template and §4 Phase R3
(lines 494–519)

**What to build:**
- Add `extract_transcript_context(auction_history) -> dict[str, float]`
- Returns: `auction_length`, `bid_escalation_rate`, `final_bid_to_max_ratio`,
  `pass_count_total`
- 2+ tests

**Commit message pattern:** `rehearsal(r3a): transcript context features`

**Scoping note:** `plans/rehearsal_notes/r3a.md`

---

### Phase 6: R3b — R3 Dual-Arm Training + Eval + Promotion

Cumulative features: 39 hand + 12 context. Same 10-step pattern.
Artifacts under `data/artifacts/arc_d_rehearsal/r3/`.

**Commit message pattern:** `rehearsal(r3b): R3 dual-arm training + eval`

**Scoping note:** `plans/rehearsal_notes/r3b.md`

---

### Phase 7: R4a — Seat Awareness Features

**Plan reference:** `arc_d_execution_plan.md` §9 H-R{N}a template and §4 Phase R4
(lines 521–544)

**What to build:**
- Add `extract_seat_context(auction_history, seat, dealer) -> dict[str, float]`
- Returns: `seat_position`, `bids_before_me`, `is_dealer`, `partner_bid_before_me`
- 2+ tests

**Commit message pattern:** `rehearsal(r4a): seat awareness features`

**Scoping note:** `plans/rehearsal_notes/r4a.md`

---

### Phase 8: R4b — R4 Dual-Arm Training + Eval + Promotion

Cumulative features: 39 hand + 16 context. Same 10-step pattern.
Artifacts under `data/artifacts/arc_d_rehearsal/r4/`.

**Commit message pattern:** `rehearsal(r4b): R4 dual-arm training + eval`

**Scoping note:** `plans/rehearsal_notes/r4b.md`

---

### Phase 9: R5b — Lambda Tuning + Off/Def Training + Eval + Promotion

**Plan reference:** `arc_d_execution_plan.md` §4 Phase R5 (lines 547–641)
and §9 H-R{N}b R5b additions (lines 1631–1645)

**What to build (beyond the standard 10-step pattern):**
1. Create `scripts/internal/tune_lambda.py`:
   - Lambda grid: `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`
   - Val-set simulation per lambda (seed=42, n_per=500 for rehearsal)
   - Select `lambda* = argmax(net_eppd)`
   - Sensitivity check: +/-20% lambda → <5% EV change
   - Output: `lambda_tuning_report_r5.json`, `lambda_tuning_report_r5_full.json`
2. Independent lambda tuning per arm (OLSa and OLSa_Full)
3. Off/def residual_variance split (use existing R5a architecture from PR #395)
4. Strict `cvar_5` gate: `cvar_5_challenger > cvar_5_control`
5. Artifacts under `data/artifacts/arc_d_rehearsal/r5/`

**Rehearsal overrides:**
- n_per=500 for lambda tuning (not 10,000)
- Lambda grid search MUST be executed (all 6 values), even at N=500.
  The goal is to exercise tune_lambda.py end-to-end, not to find a
  statistically optimal lambda.
- Sensitivity check results will not be meaningful at N=500 — log the
  result and note this in the scoping note, but do not skip the check.

**Commit message pattern:** `rehearsal(r5b): lambda tuning + R5 training + eval`

**Scoping note:** `plans/rehearsal_notes/r5b.md`

---

### Phase 10: F — Consolidation Report

**Plan reference:** `arc_d_execution_plan.md` §5 PR-F

**What to produce:**
1. Final arc dashboard across all rehearsal rungs
2. Summary document: `data/artifacts/arc_d_rehearsal/consolidation_report.md`
   - Per-rung metrics table (all rehearsal values — not statistically meaningful)
   - Feature selection progression (which features were picked at each rung)
   - Attribution gap trend across rungs

**Commit message pattern:** `rehearsal(f): consolidation report`

**Scoping note:** `plans/rehearsal_notes/f.md`

---

## Scoping Note Format

After each phase, create `plans/rehearsal_notes/{phase}.md` with this structure:

```markdown
# Rehearsal Scoping Note: {Phase ID}

## What Was Clear
- [Bullet points: plan instructions that were unambiguous and sufficient]

## What Was Ambiguous
- [Bullet points: instructions that required interpretation or guesswork]
- [Include the exact plan text that was unclear]

## What I Had to Invent
- [Bullet points: decisions not covered by the plan that I made on my own]
- [Include what I chose and why]

## Suggested Plan Patches
- [Bullet points: specific changes to arc_d_execution_plan.md]
- [Reference section numbers and line ranges]

## Errors Encountered
- [Bullet points: runtime errors, test failures, unexpected behavior]
- [Include exact error messages]

## Time and Difficulty
- [Rough assessment: straightforward / moderate / struggled]
- [Which sub-task took the most effort and why]
```

---

## Done Criteria

The rehearsal is complete when:

1. All 10 phases attempted (R1a, R1b, R2a, R2b, R3a, R3b, R4a, R4b, R5b, F)
2. `make check` passes on the final commit
3. Scoping notes exist for all 10 phases
4. A summary document lists all suggested plan patches with priority

The rehearsal branch is disposable. Its value is the scoping notes, not the code.

---

## What To Do When Stuck

- If the plan is unclear: **make your best guess, document it in the scoping
  note, and keep going.** Do not stop to ask for clarification — the whole
  point is to discover where clarification is needed.
- If code doesn't work at N=500: note the error, try a quick fix, document
  what happened. If truly blocked (e.g., a dependency doesn't exist), skip
  that sub-step and document it as a blocker.
- If a gate fails: log the failure, note it in the scoping note, advance
  to the next phase anyway.
- If `make check` fails: fix it. This is the one hard gate that is never
  relaxed.

---

## What NOT To Do

- Do not open pull requests
- Do not write to production artifact paths (`data/artifacts/arc_d/`) — all
  artifacts go to `data/artifacts/arc_d_rehearsal/`
- Do not update the production registry (`docs/02_agent/MODEL_ARC_RUNS.md`) —
  always pass `--registry data/artifacts/arc_d_rehearsal/REGISTRY.md`
- Do not run scripts without explicit path overrides — `run_arc_d_gate.py`,
  `update_arc_registry.py`, and `generate_arc_dashboard.py` all default to
  production paths. Always use the command templates from the Overrides section.
- Do not run at production scale (n_per=50,000)
- Do not spend time on statistical interpretation of N=500 results
- Do not refactor or improve code beyond what's needed to get the phase working
- Do not add features, tests, or infrastructure not specified in the plan
