# Artifact Governance: Behavioral Validation & Provenance

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder / R1.5 Action-Value
**Status:** PLAN
**Trigger:** GBT prototype H2H used a stale OLS artifact (R²=0.18, avg_bid=10.0) as comparator, producing an invalid baseline that contaminated the GBT-vs-OLS conclusion.

## Root Cause Analysis

The GBT H2H comparison (PR #614) included three bidders:
- hybrid_olsa_full (R0 incumbent) — **valid**
- GBT AV (new prototype) — **valid**
- OLS AV ("old artifact", R²=0.18) — **invalid**, always bids 10

The OLS AV used a stale/wrong artifact, not the counterfactual-trained Step 6
OLS AV (R²=0.557, `data/artifacts/arc_d/r1_5/action_value_full.json`). This
means the "GBT beats OLS AV" claim is unsupported.

### What failed

1. **No behavioral validation** — Gate X2 checks R² thresholds but not bidding
   behavior. An artifact with R²=0.18 passes X2 (threshold=0.05) despite being
   catastrophically broken in gameplay.
2. **No load-time sanity check** — `ActionValueBidder.__init__` validates
   feature names and schema but not whether the model produces sane predictions.
3. **Configs reference artifacts by raw path** — easy to point at the wrong file
   with no integrity check at experiment launch time.
4. **Reports don't enforce artifact provenance** — the H2H table cited "old
   artifact" without artifact SHA, path, or training metadata.

### What already works well

- `models/freeze.py`: content-based SHA-256 freeze/verify — sound
- `validation/arc_d_bundle.py`: path + hash + file existence — sound
- `train_action_value.py`: records git_sha, training_seed, target, feature_set
- `ActionValueBidder.__init__`: feature_names validation catches misalignment

## Disagreements with the Original 10-Step Outline

The original conversation proposed a full artifact lifecycle system (draft →
validated → blessed → superseded → quarantined) with a registry, publish
pipeline, and config resolution through artifact IDs. **I disagree with several
parts of that plan:**

### 1. Registry + Status Lifecycle: Over-engineered for this repo

There are ~5-10 total AV artifacts per rung. A full registry with status
transitions, SHA-based resolution, and load-time status enforcement is
enterprise infrastructure for a research pipeline. The existing `arc_d_bundle.py`
pattern already provides artifact integrity for the promotion track.

**Instead:** Extend the behavioral validation at training time and add a
lightweight manifest to canonical artifact directories. No new resolution layer.

### 2. Config resolution through artifact_id: Adds fragile indirection

The current pattern `artifact_path: data/artifacts/arc_d/r1_5/action_value_full.json`
in YAML configs is simple, grep-able, and traceable. Adding an `artifact_id`
resolution layer makes configs opaque without the registry and creates a single
point of failure.

**Instead:** Keep direct paths. Add a pre-experiment validation step that checks
the referenced artifact is frozen and behaviorally sane.

### 3. Separate publish script: Ceremony without value

"Publishing" is copying a file from `data/runs/` to `data/artifacts/`. A
dedicated `publish_action_value_artifact.py` for this one copy adds a tool
with no reuse beyond the copy.

**Instead:** Fold publication into the existing training pipeline as
`--publish-to` flag, gated on passing behavioral validation.

### 4. Quarantining/superseding: Unnecessary state management

The fix for "don't use stale artifacts" is validation at consumption time, not
tracking artifact state. A behavioral gate at load + at experiment launch catches
the actual failure mode without managing a state machine.

## Proposed Plan (3 PRs)

### PR 1: Behavioral Validation Gate (highest value)

**Goal:** Catch pathological artifacts before they enter any experiment or report.

**Files to create:**
- `scripts/internal/validate_action_value_artifact.py` — standalone CLI validator

**Files to modify:**
- `scripts/internal/train_action_value.py` — call validator after training
- `src/bid_euchre/strategy/bidding.py` — add lightweight load-time sanity check

#### Validation checks (in `validate_action_value_artifact.py`):

**Structural checks:**
- Schema version matches expected (`action_value_olsa_v1` or `action_value_gbt_v1`)
- All 4 model families present (suit, high, low, pass)
- feature_names match runtime expectations
- Required metadata present: target, training_seed, git_sha, created_at_utc

**Offline quality checks (existing Gate X2, enhanced):**
- R² thresholds per family (already in `validate_gate_x2`)
- NEW: R² minimum floor for suit (e.g., >0.20) — would have caught R²=0.18
- NEW: MAE sanity bound (e.g., MAE < 10.0 for net_points target)

**Behavioral checks (the key addition):**
- Generate deterministic synthetic observations (fixed hand, sweep of seats/contracts)
- For each, run `choose_bid()` and record the action
- Assert:
  - `avg_bid < 8.0` (catches "always bid 10")
  - `pass_rate > 0.01` (catches "never passes")
  - `bid_10_rate < 0.30` (catches over-concentration)
  - `contract_diversity >= 2` (uses multiple contract types)
  - `bid_level_std > 0.5` (bid levels not degenerate)
- These thresholds are generous — they catch catastrophic failures, not subtle
  quality issues. A valid artifact should pass easily.

**Negative control test:**
- Construct a deliberately pathological artifact (zero coefficients except
  intercept that makes bid-10 always win) and assert it FAILS the behavioral
  screen. This locks the detection capability.

**Load-time check in `ActionValueBidder.__init__` / `GBTActionValueBidder.__init__`:**
- After feature_names validation, run 3 synthetic observations
- Assert avg predicted value for bid-10 is not maximum across all hands
- Lightweight (~1ms) — just checks predictions, not full game simulation
- Controlled by `skip_behavioral_check=False` kwarg (default False for
  production, True in test fixtures using zero-coefficient mock artifacts —
  zero coefficients make all bid levels predict the same value via intercept
  only, which would false-positive on "bid-10 dominance" checks)

#### Tests:
- `tests/unit/test_validate_action_value_artifact.py`:
  - Valid artifact passes all checks
  - Wrong-schema artifact fails structural check
  - Low-R² artifact fails quality check
  - Pathological "always bid 10" artifact fails behavioral check
  - Known-good artifact (from fixtures) passes everything
- Extend `tests/unit/test_action_value_bidder.py`:
  - Test load-time behavioral check catches degenerate predictions
  - Test `skip_behavioral_check=True` bypasses the check

#### Integration with training pipeline:
- `train_action_value.py`: after `validate_gate_x2()`, call behavioral
  validation. Training fails if the artifact doesn't pass.
- Add `--skip-behavioral-validation` flag for debugging only.

---

### PR 2: Artifact Provenance & Metadata Enhancement

**Goal:** Make it impossible to use an artifact without knowing exactly what it is.

**Files to modify:**
- `scripts/internal/train_action_value.py` — enhance metadata
- `src/bid_euchre/models/freeze.py` — add `freeze_with_provenance()` helper

**Metadata additions to artifact JSON:**

```json
{
  "metadata": {
    "n_deals": 10000,
    "training_seed": 42,
    "arm": "full",
    "context_features": [],
    "git_sha": "abc123",
    "created_at_utc": "2026-03-12T00:00:00Z",
    "dataset_path": "data/runs/.../action_value.parquet",
    "dataset_sha256": "def456...",
    "continuation_artifact_path": "data/artifacts/arc_d/r0/hybrid_r0_full.json",
    "continuation_artifact_sha256": "ghi789...",
    "model_class": "ols",
    "behavioral_validation": {
      "passed": true,
      "avg_bid": 4.82,
      "pass_rate": 0.23,
      "bid_10_rate": 0.02,
      "validated_at_utc": "2026-03-12T00:00:01Z"
    }
  }
}
```

Key additions:
- `dataset_sha256` — ties artifact to exact training data
- `continuation_artifact_sha256` — ties to exact continuation policy
- `model_class` — explicit OLS vs GBT discriminator
- `behavioral_validation` — records that the artifact passed behavioral gate

**Training pipeline changes:**
- Compute SHA-256 of dataset parquet file before training
- Compute SHA-256 of continuation artifact (content hash, not file hash)
- Include both in artifact metadata
- Auto-freeze artifact after training + validation pass
- Print provenance summary at end of training

**Freeze helper:**
- `freeze_with_provenance(artifact_path, validation_report)` — combines freeze
  + validation metadata in one step

#### Tests:
- `tests/unit/test_train_action_value.py`:
  - Training produces artifact with all provenance fields
  - dataset_sha256 matches actual dataset content
  - Artifact is frozen after training
- Extend `tests/unit/test_freeze.py`:
  - `freeze_with_provenance()` produces valid frozen artifact with validation block

---

### PR 3: Experiment-Time & Report-Time Artifact Verification

**Goal:** Verify artifact integrity at experiment launch and enforce provenance
in reports.

**Files to modify:**
- `src/bid_euchre/experiments/config.py` — add artifact verification at config load
- Report templates/generators — add provenance section requirement

**Experiment-time verification:**

When `BiddingPolicyConfig.create_bidding_policy()` (config.py:108) instantiates
an `ActionValueBidder` or `GBTActionValueBidder`, add optional verification:
- Check artifact is frozen (`verify_frozen()`)
- Log artifact SHA, path, model_class, target, training_seed
- If artifact is not frozen, warn (don't block — unfrozen artifacts are valid
  during development, just not for promotion)

This is NOT a registry lookup. It's a simple `verify_frozen()` call on the
already-specified path. No new resolution layer.

**Report provenance enforcement:**

Add a report provenance template section to experiment reports:

```markdown
### Artifact Provenance

| Bidder | Artifact Path | SHA-256 (first 12) | Model Class | Target | R² (suit) | Training Seed |
|--------|--------------|--------------------| ------------|--------|-----------|---------------|
| OLS AV | data/artifacts/.../action_value_full.json | abc123def456 | ols | net_points | 0.557 | 42 |
| GBT AV | data/artifacts/.../action_value_gbt.json | xyz789abc012 | gbt | net_points | 0.594 | 42 |
```

**Concrete changes:**
- Add `extract_artifact_provenance(artifact_path) -> dict` utility function
  (in `src/bid_euchre/reporting/` or `src/bid_euchre/models/`)
- Update `scripts/internal/run_arc_d_h2h_battery.py` to log artifact provenance
  for each bidder in the H2H summary JSON
- Add a `docs/02_agent/` checklist item for artifact provenance in reports

#### Tests:
- `tests/unit/test_config.py` or new test:
  - Verify frozen artifact loads with provenance logging
  - Verify unfrozen artifact logs warning
- `tests/unit/test_extract_provenance.py`:
  - Returns correct fields from valid artifact
  - Handles missing metadata gracefully

---

## Implementation Order

1. **PR 1** (behavioral validation) — highest value, catches the exact failure
   mode that caused this issue. Can be done independently.
2. **PR 2** (provenance metadata) — enhances artifacts so PR 3 has something
   to report. Depends on PR 1 for validation integration.
3. **PR 3** (experiment-time + report-time checks) — consumption-side checks.
   Depends on PR 2 for provenance fields.

## What This Does NOT Include (and why)

| Excluded Item | Reason |
|--------------|--------|
| Artifact registry with status lifecycle | Over-engineered for ~10 artifacts/rung |
| Config resolution through artifact_id | Adds opaque indirection to simple paths |
| Dedicated publish script | Single copy operation, not worth a script |
| Quarantine/supersede state tracking | Validation at consumption time is sufficient |
| Artifact migration for all historical artifacts | Historical artifacts are in `data/runs/` (gitignored); only canonical `data/artifacts/` matter |

## Acceptance Criteria

1. A newly trained artifact that "always bids 10" is **rejected** at training time.
2. An artifact with R²=0.18 is **rejected** by the enhanced R² floor check.
3. Every artifact in `data/artifacts/arc_d/` includes dataset SHA and behavioral
   validation results in its metadata.
4. H2H battery summaries include artifact provenance per bidder.
5. A negative-control test in CI proves the behavioral gate catches pathological
   artifacts.

## Outcome

**Status:** IMPLEMENTED — 3 PRs created, review loops running.

| PR | Branch | Title | Acceptance Criteria |
|----|--------|-------|---------------------|
| #617 | `artifact-governance` | Behavioral validation gate | AC 1, 2, 5 |
| #619 | `artifact-provenance` | Provenance metadata & freeze-with-provenance | AC 3 |
| #620 | `artifact-verification` | Experiment-time & report-time verification | AC 4 |

**Merge order:** #617 → #619 → #620 (bottom-up stack).

**Test coverage:**
- `test_validate_action_value_artifact.py` — 20 tests (structural, R² floors, behavioral gates, negative controls)
- `test_freeze.py` — 34 tests (freeze, verify, content hash, provenance, sha256_file, freeze_with_provenance, extract_provenance)
- `test_train_action_value.py` — 7 new tests (provenance hashes, model_class, GBT provenance)

All three PRs pass `make check-quiet`.
