# CODEBASE_CONSISTENCY — doc/code gap tracker (RULES.md + METRICS.md)

**Created:** 2026-01-04
**Last verified on main:** 2026-01-27 (commit `279417d`)
**Status:** Active

## How to read this file

- This is a curated list of **confirmed** mismatches between documented contracts (RULES/METRICS/DATA_CONTRACT) and the current implementation.
- Keep “Now” to the **top 3** actionable gaps; everything else goes in “Later”.
- When something is implemented (or proven obsolete), move it to “Done/Archived” with a short note.

---

## Now (top 3)

### 1) Add auction transcript logging (RULES.md §8.2)

**Status:** Open
**Why it matters:** We can’t audit/replay bidding decisions without per-seat bid actions.

**Next action:**
- Add a per-action auction log record (one event per seat action; always 4 actions).
- Emit these records from the auction loop (including “all-pass redeal” hands).
- Update/extend tests to lock the log contract.

**Notes (from RULES.md):**
- Must log all 4 bids/passes (“single-round auction transcript”).
- A redeal should be explicit (see item 2).

---

### 2) Add `redeal_flag` to hand-level logs (RULES.md §8.2)

**Status:** Open
**Why it matters:** RULES.md requires an explicit redeal signal; today it’s implicit/derivable at best.

**Next action:**
- Add `redeal_flag: bool` to the hand-end record/schema and set it `True` for all-pass redeals.
- Update any record-writing paths and contract tests accordingly.

---

### 3) Add `made_bid` to hand-level logs (RULES.md §8.2 / METRICS.md required field)

**Status:** Open
**Why it matters:** `made_bid` is a required analysis field; deriving it downstream is easy but brittle and obscures intent.

**Next action:**
- Add `made_bid: bool` to the hand-end record/schema.
- Compute it in simulation once tricks are known: `decl_tricks >= contract_tricks`.
- Update tests that validate log/metrics fields.

---

## Later

### Scoring / outcome metrics

#### Dual outcome tracking (METRICS.md)

**Status:** Open
**Next action:** Add/standardize both outcome notions where we summarize results:
- `trick_win` (e.g., tricks ≥ 6)
- `points_win` (e.g., points_team0 > points_team1)

---

### Logging schema / determinism

#### Card instance IDs (RULES.md §8.3)

**Status:** Open
**Next action:** Introduce an instance identifier for cards (double-deck requires distinguishing duplicates) and plumb through logging.

---

#### Separate strategy IDs (METRICS.md)

**Status:** Open
**Next action:** Log distinct IDs for:
- `team0_play_strategy_id`, `team1_play_strategy_id`
- `team0_bid_strategy_id`, `team1_bid_strategy_id`

---

### Experiment protocols / reporting

#### TEAM_RANDOMIZED comparator protocol (METRICS.md)

**Status:** Open
**Next action:** Add a config option to randomize per-hand assignment of Strategy A to Team0 vs Team1 (seeded/replayable), with a FIXED debug mode.

---

#### Strategy-centric metrics (METRICS.md)

**Status:** Open
**Next action:** Add reporting keyed by strategy ID (not team index), especially for TEAM_RANDOMIZED runs.

---

#### Report comparability metadata surfaced in reports (METRICS.md §8)

**Status:** Open
**Current repo state:** Runs already write `meta.json` including `git_sha` and `config_sha256` (schema v2).
**Next action:** Ensure report outputs consistently surface comparability metadata (at minimum: `git_sha`, `config_sha256`, log schema version, metrics/spec version).

---

### Terminology consistency (optional / breaking)

**Status:** Open
**Next action:** If/when doing a schema migration, consider standardizing field names (e.g., “bidder” → “declarer”, `dealer_index` → `dealer_seat`) and document a backward-compat mapping.

---

### Hand strength logging (METRICS.md §2.5, §6.7)

**Status:** Open
**Next action:** Implement and log the specified v0 hand-strength definition (pre-auction, trump-agnostic), including a version tag.

---

### Nice-to-haves (recommended, not required)

- **Log derived scoring fields:** e.g., declaring/defending tricks/points (derivable but useful).
- **Recommended breakouts:** overtricks, set margin, volatility by contract (METRICS.md “strongly recommended”).
- **Minimum sample thresholds:** consistently flag low-sample groups (e.g., N < 30).
- **STYLEGUIDE.md / TESTING_STRATEGY.md:** still absent; add when there’s bandwidth (docs-only work).

---

## Done/Archived (verified in repo)

- **Arc B bidding infrastructure complete:** `datasets/`, `models/`, and `diagnostics/` modules implemented; `train_bidder.py` and `collect_bidless_dataset.py` scripts operational; ModeloEspecifico and ArtifactBidder policies working.
- **Scoring system implemented:** `src/bid_euchre/scoring.py::compute_points()` exists, simulation calls it, and unit tests cover exact scoring cases.
- **`hand_id` vs `deal_id` clarification no longer needed:** `docs/01_core/METRICS.md` no longer references `hand_id`.
- **Core docs populated:** `docs/01_core/EXPERIMENTS.md` exists and documents `meta.json` (schema v2) and reproducibility workflow.
- **Archive folder documented:** `docs/archive/README.md` exists.
- **Agent guidance already references this tracker:** `docs/02_agent/AGENTS.md` already points to `docs/03_TODO/CODEBASE_CONSISTENCY.md` and schema versioning docs.
