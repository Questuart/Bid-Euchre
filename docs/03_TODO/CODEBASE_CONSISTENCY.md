# Code Changes for RULES.md Consistency

**Created:** 2026-01-04  
**Source:** RULES.md consistency review  
**Status:** Not yet implemented

This document tracks code changes needed to align the codebase with RULES.md specifications. These were identified during consistency review but deferred for future implementation.

---

## 🔴 Priority 1: CRITICAL

### 1.1 Implement Scoring System (Section 6)

**Issue:** RULES.md Section 6 describes a comprehensive per-hand points scoring system, but code only tracks tricks.

**Current state:**
- `simulation.py` only returns `(t0, t1)` trick counts
- No points calculation
- No "make-bid" determination
- No concept of "declaring team" vs "defending team" beyond partnership

**Required implementation:**
```python
# Add to simulation.py after tricks are counted
def calculate_points(
    tricks_declaring: int,
    tricks_defending: int,
    bid_tricks: int,
    declarer_team: int
) -> Tuple[int, int]:
    """Calculate points per RULES.md Section 6.3"""
    points_defending = tricks_defending
    
    if tricks_declaring >= bid_tricks:  # Make
        points_declaring = tricks_declaring
    else:  # Set
        points_declaring = -bid_tricks
    
    # Map to team0/team1
    if declarer_team == 0:
        return points_declaring, points_defending
    else:
        return points_defending, points_declaring
```

**Files to modify:**
- `src/bid_euchre/sim/simulation.py` - Add scoring logic
- `src/bid_euchre/logging/game_logger.py` - Log points fields
- Tests - Add scoring validation tests

**Effort:** 2-3 hours  
**Impact:** HIGH - Required for proper strategy evaluation

**Blockers:** None - can be implemented independently

---

### 1.2 Add Auction Transcript Logging (Section 8.2)

**Issue:** RULES.md Section 8.2 requires logging all 4 bids/passes, but current code only logs final result.

**Current state:**
- Only `winning_bid` and `bidder_position` logged
- No per-player bid actions
- No `redeal_flag` field
- Cannot replay or audit bidding decisions

**Required implementation:**

Create new log record type:
```python
@dataclass
class BidActionRecord:
    """Record for a single bid action in the auction."""
    schema_version: int
    event: str = "bid_action"
    run_id: str
    deal_id: int
    seat: int
    action: str  # "PASS" or "BID"
    tricks_bid: Optional[int]  # null if PASS
    contract_type: Optional[str]  # null if PASS
    trump: Optional[str]  # null if PASS or non-suit
    current_high_tricks: int  # After this action
    timestamp: str
```

Modify `simulation.py` to log each bid action during the auction loop.

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add `BidActionRecord`, `log_bid_action()`
- `src/bid_euchre/sim/simulation.py` - Call logger in bidding loop
- Increase `SCHEMA_VERSION` to 6

**Effort:** 1-2 hours  
**Impact:** HIGH - Essential for debugging bidding strategies

**Blockers:** None

---

## 🟡 Priority 2: HIGH

### 2.1.1 Clarify `hand_id` vs `deal_id` field requirement (METRICS.md Section 2.1)

**Issue:** METRICS.md Section 2.1 lists both `deal_id` and `hand_id` as required identity/grouping keys, but code only logs `deal_id`.

**METRICS.md requirement (Section 2.1):**
- `deal_id`
- `hand_id`

**Current state:**
- Code logs `deal_id` in `HandEndRecord`
- No `hand_id` field
- Unclear if these are intended to be different fields or if `hand_id` is an alias/documentation error

**Required clarification:**
1. Are `deal_id` and `hand_id` the same thing? (If so, METRICS.md should be updated to use one term)
2. Or are they different? (If so, what is the semantic difference? E.g., `deal_id` = deal number, `hand_id` = hand number within a deal?)

**Files to modify:**
- If different: `src/bid_euchre/logging/game_logger.py` - Add `hand_id` field
- If same: `docs/01_core/METRICS.md` - Remove duplicate or clarify they're the same

**Effort:** 
- Clarification only: 0 hours (documentation question)
- Implementation (if different): 30 minutes

**Impact:** LOW - Likely a documentation issue, but needs clarification

**Blockers:** Requires clarification on intent

**Note:** This may be a documentation error where `hand_id` and `deal_id` refer to the same thing. Flagged for review.

---

### 2.1 Implement Card Instance IDs (Section 8.3)

**Issue:** RULES.md requires `card_instance_id` to distinguish duplicate cards, but this isn't implemented.

**Current state:**
- `Card` is just `(suit, rank)` - no instance ID
- Duplicate cards indistinguishable in logs
- "Earlier play wins" tie-break cannot be audited

**Required implementation:**

1. Modify `Card` dataclass:
```python
@dataclass(frozen=True)
class Card:
    suit: str  # "C", "D", "H", "S"
    rank: str  # "T", "J", "Q", "K", "A"
    instance_id: int = 0  # Unique within a hand
```

2. Assign IDs when dealing:
```python
def deal_hands_with_ids(deck: List[Card], ...) -> List[List[Card]]:
    # Assign instance_id 0-39 to cards based on deal order
    for i, card in enumerate(deck):
        deck[i] = Card(card.suit, card.rank, instance_id=i)
    # ... deal as normal
```

3. Update logger to include instance_id in all card references

**Files to modify:**
- `src/bid_euchre/core/cards.py` - Add `instance_id` field
- `src/bid_euchre/core/cards.py` - Update `deal_hands()`
- `src/bid_euchre/logging/game_logger.py` - Log instance IDs
- `src/bid_euchre/sim/simulation.py` - Pass through instance IDs
- ALL test files - Update Card construction

**Effort:** 2-3 hours (plus test updates)  
**Impact:** HIGH - Required for deterministic replay

**Blockers:** This will break existing Card construction everywhere. Consider making `instance_id` optional with default=0 for backward compatibility.

---

### 2.2 Add `redeal_flag` to Logger (Section 8.2)

**Issue:** RULES.md requires explicit `redeal_flag` field in hand logs.

**Current state:**
- Misdeals logged but no explicit flag
- Implicit: `leader=-1` or `winning_bid=0` indicates misdeal
- Not clear from log schema

**Required implementation:**

Add field to `HandEndRecord`:
```python
@dataclass
class HandEndRecord:
    # ... existing fields
    redeal_flag: bool = False  # True if all-pass misdeal
```

Update `simulation.py` misdeal handling to set `redeal_flag=True`.

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add field to `HandEndRecord`
- `src/bid_euchre/sim/simulation.py` - Pass `redeal_flag=True` for misdeals
- Increase `SCHEMA_VERSION` to 6 (or 7 if 1.2 is done first)

**Effort:** 15-30 minutes  
**Impact:** MEDIUM - Improves log clarity

**Blockers:** None

---

### 2.3 Add `made_bid` Field to Logger (METRICS.md Section 2.3)

**Issue:** METRICS.md requires explicit `made_bid` (bool) field, but code doesn't log it.

**Current state:**
- Not logged in `HandEndRecord`
- Must be derived from `tricks_team_X` and `contract_tricks`
- METRICS.md Section 2.3 lists it as required

**Required implementation:**

Add field to `HandEndRecord`:
```python
@dataclass
class HandEndRecord:
    # ... existing fields
    made_bid: bool  # True if declaring team tricks >= contract_tricks
```

Compute in `simulation.py` after tricks are counted:
```python
made_bid = (tricks_declaring >= contract_tricks)
```

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add field to `HandEndRecord`
- `src/bid_euchre/sim/simulation.py` - Compute and pass `made_bid`
- Increase `SCHEMA_VERSION` if other changes require it

**Effort:** 30 minutes  
**Impact:** MEDIUM - Improves log clarity and enables explicit declarer success tracking

**Blockers:** None - Easy derivative field

---

### 2.4 Separate Strategy IDs (METRICS.md Section 2.4)

**Issue:** METRICS.md requires 4 separate strategy ID fields for team-level and play/bid separation, but logger only has 1 generic `strategy_id`.

**METRICS.md requirements:**
- `team0_play_strategy_id`, `team1_play_strategy_id`
- `team0_bid_strategy_id`, `team1_bid_strategy_id`

**Current state:**
- Logger line 49: Single `strategy_id: str` field
- No team-level tracking
- No play/bid separation
- Cannot analyze asymmetric matchups or separate bidding vs playing strategy effects

**Required implementation:**

Add fields to `HandEndRecord`:
```python
@dataclass
class HandEndRecord:
    # ... existing fields
    team0_play_strategy_id: str
    team1_play_strategy_id: str
    team0_bid_strategy_id: str
    team1_bid_strategy_id: str
```

Update `simulation.py` to extract strategy IDs from strategies per seat and map to teams.

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add 4 fields to `HandEndRecord`
- `src/bid_euchre/sim/simulation.py` - Extract strategy IDs from strategies, map to teams
- Experiment runners - Pass strategy IDs appropriately
- Increase `SCHEMA_VERSION`

**Effort:** 1-2 hours  
**Impact:** HIGH - Required for asymmetric matchup analysis and play/bid strategy separation

**Blockers:** None - Independent change

---

## 🟢 Priority 3: MEDIUM

### 3.1 Standardize Terminology: bidder → declarer

**Issue:** Mixed terminology - docs use "declarer", code uses "bidder".

**Current state:**
- `bidder_position` in code
- `declarer_seat` in RULES.md
- Inconsistent but functionally equivalent

**Recommendation:** Rename for consistency with standard trick-taking game terminology.

**Files to modify (estimate 10+ occurrences each):**
- `src/bid_euchre/sim/simulation.py` - `bidder_position` → `declarer_seat`
- `src/bid_euchre/logging/game_logger.py` - `bidder_position` → `declarer_seat`
- All experiment scripts that reference this field
- All test files

**Effort:** 30-60 minutes (careful find/replace)  
**Impact:** MEDIUM - Improves clarity and consistency

**Blockers:** Will break any analysis scripts that read logs with `bidder_position`

---

### 3.2 Standardize Terminology: dealer_index → dealer_seat

**Issue:** Mixed terminology - docs use "dealer_seat", code uses "dealer_index" and "dealer_position".

**Current state:**
- `dealer_index` in `simulation.py`
- `dealer_position` in `game_logger.py`
- `dealer_seat` in RULES.md

**Recommendation:** Unify on `dealer_seat`.

**Files to modify:**
- `src/bid_euchre/sim/simulation.py` - `dealer_index` → `dealer_seat`
- `src/bid_euchre/logging/game_logger.py` - `dealer_position` → `dealer_seat`

**Effort:** 15-30 minutes  
**Impact:** LOW-MEDIUM - Improves consistency

**Blockers:** Same as 3.1

---

### 3.3 Standardize Terminology: bid terminology and logged field names

**Issue:** Multiple terms for the same bidding concepts, and field name inconsistencies between logged fields and METRICS.md requirements.

**Current state:**
- `bid`, `bid_amount`, `tricks_bid` all used for the same thing
- `trump`, `trump_suit` used interchangeably
- Logger field `winning_bid` but METRICS.md Section 2.2 requires `contract_tricks`
- Logger fields `t0`/`t1` but METRICS.md Section 2.3 requires `tricks_team_0`/`tricks_team_1`

**METRICS.md requirements:**
- Section 2.2: `contract_tricks` (1..10) - currently logged as `winning_bid`
- Section 2.3: `tricks_team_0`, `tricks_team_1` - currently logged as `t0`, `t1`

**Recommendation:** Standardize on METRICS.md/RULES.md terms:
- Use `tricks_bid` for the number (not `bid_amount`) in code comments/docstrings
- Use `trump` consistently (not `trump_suit`) in code comments/docstrings
- Consider renaming logger fields to match METRICS.md (or document mapping):
  - `winning_bid` → `contract_tricks` (same value, different name)
  - `t0` → `tricks_team_0` (same value, different name)
  - `t1` → `tricks_team_1` (same value, different name)

**Files to modify:**
- `src/bid_euchre/strategy/base.py` - Docstring says `bid_amount`
- Various strategy files - Terminology in comments
- Logger docstrings - Field name documentation
- Consider: `src/bid_euchre/logging/game_logger.py` - Field names in `HandEndRecord` (if renaming)
- Report generators - Field name mapping/compatibility

**Effort:** 
- Terminology (comments/docstrings): 15-30 minutes
- Field renaming (if done): 1-2 hours (breaking change, requires migration)

**Impact:** 
- Terminology: LOW - Mostly comments/docstrings
- Field renaming: LOW-MEDIUM - Breaking change, but improves METRICS.md consistency

**Blockers:** None (mostly documentation). Field renaming would be a breaking change requiring log migration.

**Note:** Field renaming (`t0`/`t1` → `tricks_team_0`/`tricks_team_1`, `winning_bid` → `contract_tricks`) is recommended for consistency with METRICS.md but is optional if reports handle the mapping. Consider documenting the mapping in a data contract if not renaming.

---

### 3.4 Implement Dual Win Tracking (METRICS.md Section 4.3)

**Issue:** METRICS.md Section 4.3 specifies both `trick_win` and `points_win` should be tracked, but code only implements trick-based wins.

**Current state:**
- `metrics.py` implements trick-based win (`tricks >= 6`)
- No points-based win tracking (requires scoring system first)
- METRICS.md now documents both, but code only has one

**Required implementation:**

After scoring system is implemented (1.1):
1. Update `metrics.py` to compute both:
   - `trick_win` (current implementation: `tricks >= 6`)
   - `points_win` (new: `points_team_0 > points_team_1`)
2. Keep both metrics for comparison/transition period
3. Update reporting to show both where relevant

**Files to modify:**
- `src/bid_euchre/reporting/metrics.py` - Add `points_win` computation
- `src/bid_euchre/analysis/stats.py` - Add points-based outcome stats if needed
- Report generators - Include both metrics

**Effort:** 1-2 hours (after scoring system)  
**Impact:** HIGH - Required for proper evaluation per METRICS.md specification

**Blockers:** Depends on scoring system implementation (1.1)

---

### 3.5 Hand Strength Logging (METRICS.md Section 2.5, 6.7)

**Issue:** METRICS.md Section 2.5 requires hand strength fields at both seat and team level with specific v0.1 definition, but this is not fully implemented.

**METRICS.md requirements (Section 2.5):**

1) **Seat-level fields (REQUIRED):**
- `seat0_hand_strength`, `seat1_hand_strength`, `seat2_hand_strength`, `seat3_hand_strength` (int)
- Optional but recommended: `seat0_hand_strength_bucket`, etc. (string)

2) **Team-level fields (REQUIRED, may be derived):**
- `team0_hand_strength = seat0_hand_strength + seat2_hand_strength` (sum, not mean)
- `team1_hand_strength = seat1_hand_strength + seat3_hand_strength` (sum)
- Optional but recommended: `team0_hand_strength_bucket`, `team1_hand_strength_bucket`

3) **v0.1 definition (REQUIRED):**
- Simple rank score (trump-agnostic)
- Rank scoring: `A = 5`, `K = 4`, `Q = 3`, `J = 2`, `10 = 1` (Ten represented as `T` in code)
- Suits are ignored
- Duplicate cards scored independently (double deck)
- Expected range per seat: `10..50`
- Formula: `seatX_hand_strength = Σ score(rank(card)) over the 10 cards in seat X's hand`

4) **Version tag (REQUIRED):**
- `hand_strength_version = "rank_score_v0"`

5) **Computation constraints (REQUIRED):**
- Hand strength MUST be computed **pre-auction** (from private 10-card hand only)
- MUST NOT depend on: auction outcomes, trick play, points/tricks realized, opponent/partner cards

6) **Role-conditioned strength (derivable):**
- `decl_hand_strength` / `decl_hand_strength_bucket` from declaring team
- `def_hand_strength` / `def_hand_strength_bucket` from defending team

7) **Breakouts (Section 6.7):**
- Report by `teamX_hand_strength_bucket`
- Report by `decl_hand_strength_bucket` and `def_hand_strength_bucket`

**Current state:**
- `hand_eval.py` has `score_hand_scalar()` function but it:
  - Uses contract-type and trump-specific weights (not the v0.1 trump-agnostic definition)
  - For suit contracts: different weights for trump vs offsuit (A=100 vs 50, etc.)
  - For high/low: uses `rank_strength` which may differ from v0.1 spec
- Individual hand scores exist but not logged at seat or team level
- No `hand_strength_version` tag
- No bucketing logic
- Computation timing: Currently computed after contract is known (may be post-auction in bidding scenarios)

**Required implementation:**

1. **Implement v0.1 rank score function (NEW function, different from `score_hand_scalar()`):**
   - Create `compute_hand_strength_v0(hand: List[Card]) -> int`
   - Rank scoring: A=5, K=4, Q=3, J=2, T=1
   - Must be trump-agnostic (ignore suits)
   - Must work for all contract types identically

2. **Log seat-level hand strength (REQUIRED):**
   - Compute `seatX_hand_strength` using v0.1 function for each seat
   - Add `seat0_hand_strength`, `seat1_hand_strength`, `seat2_hand_strength`, `seat3_hand_strength` to logger
   - Compute PRE-AUCTION (before bidding phase, from starting hands only)

3. **Log team-level hand strength (REQUIRED):**
   - Compute as SUM: `team0_hand_strength = seat0_hand_strength + seat2_hand_strength`
   - Add `team0_hand_strength`, `team1_hand_strength` to logger (or derive from seat fields)

4. **Add version tag:**
   - Log `hand_strength_version = "rank_score_v0"` in hand records

5. **Implement bucketing (future work):**
   - Define bucketing strategy (quantiles? fixed bins?)
   - Add `seatX_hand_strength_bucket` fields (optional but recommended)
   - Add `teamX_hand_strength_bucket` fields (optional but recommended)

**Files to modify:**
- `src/bid_euchre/features/hand_eval.py` - Add `compute_hand_strength_v0()` function (NEW, different from `score_hand_scalar()`)
- `src/bid_euchre/sim/simulation.py` - Compute hand strength PRE-AUCTION (before bidding), log seat and team fields
- `src/bid_euchre/logging/game_logger.py` - Add hand strength fields to `HandEndRecord`
- Report generators - Add role-conditioned strength derivation

**Effort:** 
- v0.1 function + seat/team logging: 2-3 hours
- Bucketing logic: 2-3 hours (future work)

**Impact:** MEDIUM-HIGH - Required for breakouts per METRICS.md Section 6.7. Seat-level fields are REQUIRED, not optional.

**Blockers:** None for logging, but requires new v0.1 function (different from existing `score_hand_scalar()`)

**Important notes:**
- The v0.1 definition is DIFFERENT from existing `score_hand_scalar()` - do not reuse it
- Hand strength must be computed PRE-AUCTION (before bidding phase starts)
- Seat-level fields are REQUIRED, not optional (Section 2.5.2)
- Team aggregation is SUM, not mean/min (Section 2.5.3)

---

### 3.6 Implement TEAM_RANDOMIZED Protocol (METRICS.md Section 3.1)

**Issue:** METRICS.md Section 3.1 requires TEAM_RANDOMIZED as the default comparator protocol, but experiments use fixed strategy-to-team assignments.

**METRICS.md requirement:**
- Section 3.1: "On each hand, assign Strategy A to either Team0 (seats 0,2) or Team1 (seats 1,3) with 50/50 probability"
- Section 3.2: Assignment must be seeded and replayable
- Section 3.3: Optional FIXED mode for debugging
- This is the **default comparator protocol** for fair comparisons

**Current state:**
- Experiments use `self_play` (same strategy all seats) or `head_to_head` (fixed Team0 vs Team1 assignments)
- No per-hand randomization of strategy-to-team assignment
- No `seat_assignment_mode` parameter
- Strategy IDs are logged at team level, but assignment is fixed per experiment

**Required implementation:**

1. Add `seat_assignment_mode` parameter to experiment config:
   - `TEAM_RANDOMIZED` (default): Randomize strategy-to-team assignment per hand
   - `FIXED` (debug mode): Fixed assignment (current behavior)

2. Implement randomization logic in experiment runner:
   ```python
   if seat_assignment_mode == "TEAM_RANDOMIZED":
       # Per hand, randomly assign Strategy A to Team0 or Team1
       # Use hand-specific seed for reproducibility: seed + deal_id
       team0_uses_A = (rng.randrange(2) == 0)
       # Then assign strategies accordingly
   ```

3. Ensure strategy IDs are logged correctly for randomized assignments

**Files to modify:**
- `experiments/run_experiment.py` - Add seat_assignment_mode logic
- `src/bid_euchre/experiments/config.py` - Add parameter to config
- Experiment configs - Add seat_assignment_mode (default to TEAM_RANDOMIZED)
- Tests - Add tests for randomized assignments

**Effort:** 2-3 hours  
**Impact:** HIGH - Required for proper strategy comparisons. Current fixed assignments may introduce bias.

**Blockers:** None - Can be implemented independently. Note: This affects all existing experiments if made default.

**Note:** This is a fundamental change to experiment design. Consider backward compatibility: should existing configs default to FIXED or TEAM_RANDOMIZED?

---

### 3.7 Implement Strategy-Centric Metrics (METRICS.md Section 5.9)

**Issue:** METRICS.md Section 5.9 requires strategy-centric metrics (reporting by strategy ID, not team index), but code only implements team-level metrics.

**METRICS.md requirements:**
- Section 5.9.1: Per-hand extraction of `points_for_play[S]` and `net_points_for_play[S]`
- Section 5.9.2: Head-to-head delta metrics (`delta_net_points_A_minus_B`) with paired comparisons
- Section 5.9.3: Required strategy-centric outputs for each strategy ID
- Section 9.2: Strategy-centric topline is **required under TEAM_RANDOMIZED**

**Current state:**
- Code computes team-level metrics only (`team0_mean_points`, `team1_mean_points`)
- No `points_for_play[S]` computation
- No `play_mean_points[S]` aggregation by strategy ID
- No `delta_net_points_A_minus_B` paired comparisons
- No role-conditioned strategy metrics (`play_decl_mean_points[S]`, `play_def_mean_points[S]`)

**Required implementation:**

1. Add strategy-centric metric computation functions:
   ```python
   def compute_points_for_strategy(hand_records, strategy_id, strategy_type="play"):
       """Extract points_for_play[S] or points_for_bid[S] per hand."""
       # For each hand, find which team uses this strategy
       # Extract points for that team
   
   def compute_strategy_centric_metrics(hand_records):
       """Compute play_mean_points[S], play_mean_net_points[S], etc."""
   
   def compute_paired_delta(hand_records, strategy_a, strategy_b):
       """Compute delta_net_points_A_minus_B per hand."""
   ```

2. Update reporting to include strategy-centric tables (Section 9.2)

3. Integrate with TEAM_RANDOMIZED protocol (3.6) - strategy IDs must be logged correctly

**Files to modify:**
- `src/bid_euchre/reporting/metrics.py` - Add strategy-centric computation functions
- `src/bid_euchre/analysis/stats.py` - Add strategy-centric aggregation
- Report generators - Include strategy-centric tables
- Dashboard generators - Add strategy-centric panels

**Effort:** 3-4 hours  
**Impact:** HIGH - Required for proper evaluation under TEAM_RANDOMIZED. Team-level metrics are insufficient.

**Blockers:** Depends on strategy ID logging (2.4) and TEAM_RANDOMIZED protocol (3.6)

**Note:** This is a major reporting change. All experiments using TEAM_RANDOMIZED will need strategy-centric metrics.

---

## 🔵 Priority 4: LOW

### 4.1 Rename `contract` → `contract_type` in Logger

**Issue:** Logger parameter is named `contract` but actually holds `contract_type` value.

**Current state:**
```python
def log_hand_end(
    self,
    # ...
    contract: str,  # Actually contract_type ("suit", "high", "low")
    trump: Optional[str],
```

**Recommendation:** Rename for clarity:
```python
def log_hand_end(
    self,
    # ...
    contract_type: str,  # "suit", "high", "low"
    trump: Optional[str],
```

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Rename parameter
- `src/bid_euchre/sim/simulation.py` - Update call sites
- All experiment scripts that use the logger

**Effort:** 10-15 minutes  
**Impact:** LOW - Improves clarity

**Blockers:** None

---

### 4.2 Log Computed Scoring Fields (Section 8.5)

**Issue:** Once scoring is implemented (1.1), should log derived fields.

**Required after 1.1:**
- `tricks_declaring`, `tricks_defending`
- `points_declaring_team`, `points_defending_team`

**Effort:** 5-10 minutes (after 1.1 is done)  
**Impact:** LOW - Nice to have, but derivable

**Blockers:** Depends on 1.1

---

### 4.3 Add Comparability Metadata to Reports (METRICS.md Section 8)

**Issue:** METRICS.md Section 8 requires reports to include specific metadata for comparability verification, but this isn't implemented.

**METRICS.md requirement (Section 8, lines 524-528):**
Reports must include:
- git SHA (commit hash)
- config hash (hash of experiment configuration)
- schema version (from logger SCHEMA_VERSION)
- metrics version (this doc version or hash)

**Current state:**
- Reports don't include git SHA
- No config hash computation or logging
- Schema version may be in logs but not in reports
- No metrics version tracking

**Required implementation:**

1. Add metadata extraction to report generation:
   ```python
   def get_comparability_metadata(config_path, log_dir):
       git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode()
       config_hash = hashlib.sha256(open(config_path).read().encode()).hexdigest()[:8]
       schema_version = extract_schema_version_from_logs(log_dir)
       metrics_version = "METRICS.md v1.0"  # or hash of METRICS.md
       return {
           "git_sha": git_sha,
           "config_hash": config_hash,
           "schema_version": schema_version,
           "metrics_version": metrics_version
       }
   ```

2. Include metadata in all report outputs (dashboards, tables, JSON summaries)

**Files to modify:**
- Report generators - Extract and include metadata
- Dashboard generators - Add metadata panel/section
- `experiments/run_experiment.py` - Capture metadata at experiment start
- Report template/formatter - Standardize metadata display

**Effort:** 1-2 hours  
**Impact:** MEDIUM - Enables verification of experiment comparability. Important for reproducibility audits.

**Blockers:** None - Can be implemented independently

---

### 4.4 Implement Recommended Breakouts (METRICS.md Section 6.8)

**Issue:** METRICS.md Section 6.8 lists "strongly recommended" breakouts that enhance analysis depth but may not be implemented.

**METRICS.md requirements (Section 6.8):**

1) **Auction context:**
- `current_high_tricks_when_declarer_bid` (requires auction transcript)
- `did_declarer_open` (true if declarer was first non-pass bid)
- `num_bids_before_declarer`

2) **Overtricks:**
- `overtricks = max(0, decl_tricks - contract_tricks)`
- Report EV and distribution by overtricks

3) **Set severity:**
- `set_margin = contract_tricks - decl_tricks` when set, else 0
- Breakout by set margin buckets

4) **Volatility / risk by contract:**
- std dev of `decl_points` by (`contract_type`, `contract_tricks`)

**Current state:**
- Auction context breakouts require auction transcript (not yet implemented per 1.2)
- Overtricks/set severity can be computed from existing data
- Volatility metrics may be partially computed but not explicitly broken out

**Required implementation:**

1. Compute derivable metrics (overtricks, set severity, volatility) from logged data
2. Add breakout tables/plots for these metrics
3. Auction context breakouts depend on auction transcript logging (1.2)

**Files to modify:**
- Report generators - Add breakout computations
- Dashboard generators - Add breakout panels/plots
- Analysis scripts - Add breakout analysis functions

**Effort:** 2-3 hours (excluding auction context, which depends on 1.2)  
**Impact:** LOW-MEDIUM - Enhances analysis depth. Marked as "strongly recommended" not "required".

**Blockers:** Auction context breakouts depend on auction transcript logging (1.2)

**Note:** These are recommended enhancements. Prioritize after required metrics are implemented.

---

### 4.5 Implement Minimum Sample Thresholds (METRICS.md Section 7.5)

**Issue:** METRICS.md Section 7.5 recommends flagging groups with N < 30 as "low sample", but this may not be consistently implemented.

**METRICS.md requirement (Section 7.5):**
- Always report `N_group` for any breakout group
- If `N_group < 30`, flag the group as **low sample** in reports
- Interpret CIs cautiously for low-sample groups
- Bootstrap CIs may still be computed but must be labeled low-sample

**Current state:**
- Dashboard has plotting thresholds (`MIN_SAMPLES_FOR_PLOT = 200`, `MIN_SAMPLES_FOR_PLOT_LOW = 50`)
- Not clear if reports explicitly flag low-sample groups per Section 7.5 specification
- `N` is typically reported, but low-sample flagging may be inconsistent

**Required implementation:**

1. Add low-sample detection to reporting functions:
   ```python
   def flag_low_sample(n, threshold=30):
       return n < threshold
   ```

2. Include low-sample flags in all breakout tables/reports
3. Add visual indicators (e.g., asterisk, footnote) for low-sample groups
4. Update bootstrap CI reporting to label low-sample cases

**Files to modify:**
- Report generators - Add low-sample flagging
- Dashboard generators - Add visual indicators
- Table formatters - Include low-sample annotations

**Effort:** 1 hour  
**Impact:** LOW - Recommended best practice. Improves interpretation clarity.

**Blockers:** None - Can be implemented independently

---

## 📋 Implementation Priority Order

### **Suggested Order:**

1. **Quick win (30 min):** 2.2 - Add `redeal_flag`
2. **Quick win (30 min):** 2.3 - Add `made_bid` field
3. **Foundation (2-3 hrs):** 1.1 - Implement scoring system ⚠️ **BLOCKS 3.4**
4. **High value (1-2 hrs):** 2.4 - Separate strategy IDs ⚠️ **REQUIRED FOR 3.7**
5. **High value (2-3 hrs):** 3.6 - TEAM_RANDOMIZED protocol ⚠️ **REQUIRED FOR 3.7**
6. **High value (3-4 hrs):** 3.7 - Strategy-centric metrics (after 2.4, 3.6)
7. **High value (1-2 hrs):** 3.4 - Dual win tracking (after 1.1)
8. **High value (2 hrs):** 1.2 - Auction transcript logging
9. **Medium value (1-2 hrs):** 4.3 - Comparability metadata
10. **Future work (3-5 hrs):** 3.5 - Hand strength bucketing (deferred)
11. **Enhancement (2-3 hrs):** 4.4 - Recommended breakouts (after 1.2 for auction context)
12. **Big effort (3 hrs):** 2.1 - Card instance IDs (when needed for replay)
13. **Cleanup (1 hr):** 3.1-3.3 - Terminology standardization (includes field name mapping documentation)
14. **Best practice (1 hr):** 4.5 - Minimum sample thresholds
15. **Clarification needed:** 2.1.1 - `hand_id` vs `deal_id` field requirement

### **Or defer all for now** if current system is working for your analysis.

---

## 🔍 Impact Summary

| Change | Files | Effort | User Impact |
|--------|-------|--------|-------------|
| 1.1 Scoring | 3-5 | 2-3 hrs | HIGH - Can properly evaluate strategies ⚠️ BLOCKS 3.4 |
| 1.2 Auction logging | 2 | 1-2 hrs | HIGH - Can debug bidding |
| 2.1 Card instance IDs | 10+ | 2-3 hrs | MEDIUM - Needed for perfect replay |
| 2.2 Redeal flag | 2 | 15-30 min | MEDIUM - Improves log clarity |
| 2.3 Made_bid field | 2 | 30 min | MEDIUM - Explicit declarer success |
| 2.4 Strategy IDs | 3-5 | 1-2 hrs | HIGH - Asymmetric matchup analysis |
| 2.1.1 hand_id vs deal_id | 1-2 | 0-30 min | LOW - Clarification needed |
| 3.1-3.3 Terminology | 10+ | 1-2 hrs | LOW-MEDIUM - Improves consistency (includes field name mapping) |
| 3.4 Dual win tracking | 2-3 | 1-2 hrs | HIGH - Required per METRICS.md (after 1.1) |
| 3.5 Hand strength | 4-5 | 2-3 hrs + 2-3 hrs (bucketing) | MEDIUM-HIGH - Required for breakouts, seat-level REQUIRED |
| 3.6 TEAM_RANDOMIZED | 3-4 | 2-3 hrs | HIGH - Required for fair comparisons |
| 3.7 Strategy-centric metrics | 4-5 | 3-4 hrs | HIGH - Required for TEAM_RANDOMIZED |
| 4.1-4.2 Minor renames | 3-5 | 30 min | LOW - Polishing |
| 4.3 Comparability metadata | 2-3 | 1-2 hrs | MEDIUM - Enables comparability verification |
| 4.4 Recommended breakouts | 3-4 | 2-3 hrs | LOW-MEDIUM - Analysis enhancements |
| 4.5 Sample thresholds | 2-3 | 1 hr | LOW - Best practice |

**Total estimated effort:** 20-28 hours for all changes (excluding deferred hand strength bucketing)

---

## ✅ Completion Checklist

When implementing any of these:

- [ ] Update RULES.md if needed
- [ ] Update this TODO file (mark as completed or move to archive)
- [ ] Write or update tests
- [ ] Update schema version if changing logs
- [ ] Update relevant documentation
- [ ] Run full test suite
- [ ] Consider backward compatibility

---

**Questions or blockers?** Add notes here and discuss before implementing.
