# CODEBASE_CONSISTENCY — doc/code gap tracker (RULES.md + METRICS.md)

**Created:** 2026-01-04
**Last verified on main:** 2026-02-18 (commit `c5a346e`)
**Status:** Active

## How to read this file

- This is a curated list of **confirmed** mismatches between documented contracts (RULES/METRICS/DATA_CONTRACT) and the current implementation.
- Keep “Now” to the **top 3** actionable gaps; everything else goes in “Later”.
- When something is implemented (or proven obsolete), move it to “Done/Archived” with a short note.

---

## Now (top 3)

_All previous top-3 items resolved (see Done/Archived). Next priorities should be drawn from the "Later" section below._

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

- **Auction transcript logging (RULES.md §8.2):** Resolved in PR #362 (schema v7). `auction_transcript` field on `hand_end` records captures per-seat bid actions as a 4-entry list.
- **`redeal_flag` on hand-level logs (RULES.md §8.2):** Resolved in PRs #361 (schema v6, field) + #362 (callsite wiring). Computed as `(winning_bid == 0 and bidder_pos is None)`.
- **`made_bid` on hand-level logs (RULES.md §8.2):** Resolved in PRs #361 (schema v6, field) + #362 (callsite wiring). Computed from team tricks vs winning bid.
- **Arc B bidding infrastructure complete:** `datasets/`, `models/`, and `diagnostics/` modules implemented; `train_bidder.py` and `collect_bidless_dataset.py` scripts operational; ModeloEspecifico and ArtifactBidder policies working.
- **Scoring system implemented:** `src/bid_euchre/scoring.py::compute_points()` exists, simulation calls it, and unit tests cover exact scoring cases.
- **`hand_id` vs `deal_id` clarification no longer needed:** `docs/01_core/METRICS.md` no longer references `hand_id`.
- **Core docs populated:** `docs/01_core/EXPERIMENTS.md` exists and documents `meta.json` (schema v2) and reproducibility workflow.
- **Archive folder documented:** `docs/archive/README.md` exists.
- **Agent guidance already references this tracker:** `docs/02_agent/AGENTS.md` already points to `docs/03_TODO/CODEBASE_CONSISTENCY.md` and schema versioning docs.
