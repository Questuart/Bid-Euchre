# Metrics

This document defines the authoritative **metrics contract** for the Bid Euchre repo.
It specifies:
- what is computed,
- how it is computed (exact formulas),
- required denominators and exclusions,
- required breakouts and reporting conventions,
- comparability rules across experiments.

If there is any conflict between code and this document, **this document wins** unless an Architecture Decision Record explicitly states otherwise.

---

## Status

- Per-hand metrics: **Specified**
- Role-conditioned metrics (Declarer vs Defender): **Specified**
- Strategy-centric reporting under TEAM_RANDOMIZED: **Specified**
- Seat/dealer reporting: **Specified**
- Uncertainty (SE / CI / bootstrap): **Specified**
- Match-level metrics (multi-hand matches, target score): **TBD** (future)

---

## 1. Scope and Unit of Evaluation

### 1.1 Hand-level unit (current phase)

All primary metrics are computed **per hand** and then aggregated across hands.
Hands are simulated **independently** (no running match score).

### 1.2 Redeals are excluded

**All-pass redeal events are excluded** from all primary metric denominators unless stated otherwise.

- `redeal_rate` is reported separately (Section 6.9).
- Use `N_hands_nonredeal` as the default denominator for rates/means.

See `RULES.md` for redeal definition and logging requirements.

---

## 2. Required Logged Fields (Minimum Inputs)

Metrics must be computable from logged data as specified in `DATA_CONTRACT.md`.
At minimum, each attempted hand record must include:

### 2.1 Identity / grouping keys
- `seed`
- `deal_id`
- `hand_id`
- `dealer_seat` (0..3)
- `redeal_flag` (bool)

### 2.2 Auction / contract
For non-redeal hands:
- `declarer_seat` (0..3)
- `contract_tricks` (1..10)
- `contract_type` ∈ `{"suit", "high", "low"}`
- `contract_trump` ∈ `{S,H,D,C}` **iff** `contract_type == "suit"` else null

Optional (recommended for deeper breakouts):
- full 4-action auction transcript (`seat`, `action`, `tricks_bid`, `contract_type`, `trump`, `current_high_tricks` after action)

### 2.3 Outcomes
For non-redeal hands:
- `tricks_team_0` (0..10) for seats (0,2)
- `tricks_team_1` (0..10) for seats (1,3)
- `points_team_0` (int; can be negative)
- `points_team_1` (int)

Optional (derivable):
- `made_bid` (bool)

Notes:
- Tricks must satisfy `tricks_team_0 + tricks_team_1 == 10`.
- Scoring must match `RULES.md` Section 6.
- If `made_bid` is logged, it MUST equal `1{decl_tricks >= contract_tricks}` (Section 4.2).

### 2.4 Strategy identifiers (required for comparisons)

Because the default comparator protocol is TEAM_RANDOMIZED (Section 3), strategy IDs must be logged at the **team** level.

Required:
- `team0_play_strategy_id`
- `team1_play_strategy_id`
- `team0_bid_strategy_id`
- `team1_bid_strategy_id`

These IDs must be stable strings (e.g., `"random_legal_v1"`, `"greedy_trick_v2"`, `"ols_bid_v0"`).

### 2.5 Hand strength (required for breakouts)

Hand strength MUST be logged at both:
1) **individual player (seat) level**, and
2) **team level** (either logged directly or derivable from seat fields).

Hand strength is computed **pre-auction** (from each player’s private 10-card hand only) and MUST NOT depend on:
- auction outcomes (who declares),
- trick play,
- points/tricks realized,
- any opponent/partner cards.

#### 2.5.1 v0.1 strength definition: simple rank score (trump-agnostic)

For each seat, define a scalar:

`seatX_hand_strength = Σ score(rank(card)) over the 10 cards in seat X’s hand`

Rank scoring (v0.1):
- `A = 5`
- `K = 4`
- `Q = 3`
- `J = 2`
- `10 = 1`  (Ten may be represented as `T` in code)

Notes:
- Suits are ignored in v0.1 (trump-agnostic).
- Duplicate cards are scored independently (double deck).
- Expected range per seat: `10..50`.

Log a version tag so strength meaning is stable:
- `hand_strength_version = "rank_score_v0"`

#### 2.5.2 Required seat-level fields

Required fields (for seats 0–3):
- `seat0_hand_strength`, `seat1_hand_strength`, `seat2_hand_strength`, `seat3_hand_strength` (int)
- Optional but recommended:
  - `seat0_hand_strength_bucket`, `seat1_hand_strength_bucket`, `seat2_hand_strength_bucket`, `seat3_hand_strength_bucket` (string)

Bucket conventions:
- Buckets are derived from `seatX_hand_strength`.
- Bucketing scheme (quantiles vs fixed bins) must be specified in experiment config/report, but field names remain stable.

#### 2.5.3 Team-level strength (required, may be derived)

Team strength must be available for breakouts as either logged fields or derived from seat fields:

- `team0_hand_strength = seat0_hand_strength + seat2_hand_strength`
- `team1_hand_strength = seat1_hand_strength + seat3_hand_strength`

Optional but recommended:
- `team0_hand_strength_bucket`, `team1_hand_strength_bucket`

If team buckets are not logged, reports must derive them consistently from `teamX_hand_strength`.

#### 2.5.4 Role-conditioned strength (derived)

For role-conditioned reporting, derive:
- `decl_hand_strength` / `decl_hand_strength_bucket` from the declaring team’s strength
- `def_hand_strength` / `def_hand_strength_bucket` from the defending team’s strength

---

## 3. Comparator Protocol (Experiment Fairness)

### 3.1 Default comparator: TEAM_RANDOMIZED (Option B)

When comparing two policies (A vs B), **seat assignment is randomized at the team level** per hand:

- On each hand, assign Strategy A to either Team0 (seats 0,2) or Team1 (seats 1,3) with 50/50 probability.
- Partners always share the same strategies within a hand.
- This assignment must be **seeded and replayable** (see `REPRODUCIBILITY.md`).

### 3.2 Required logging for assignment

Each hand MUST be able to determine which strategy was applied to each team via:
- `team0_*_strategy_id`, `team1_*_strategy_id` (required).

### 3.3 Debug mode (optional)

Experiments MAY support a fixed assignment mode for debugging:
- `seat_assignment_mode = FIXED` (e.g., A always Team0, B always Team1)

This must not be used for headline comparisons unless explicitly stated.

---

## 4. Derived Fields and Naming Conventions

All derived metrics must use the conventions below.

### 4.1 Team net points (team-facing)

Compute net points **facing the respective team**:

- `team0_net_points = points_team_0 - points_team_1`
- `team1_net_points = points_team_1 - points_team_0`

Similarly for tricks:
- `team0_net_tricks = tricks_team_0 - tricks_team_1`
- `team1_net_tricks = tricks_team_1 - tricks_team_0`

### 4.2 Declarer/defender role fields (explicit prefixes)

Define, for non-redeal hands:

- `decl_team` = the partnership containing `declarer_seat`
- `def_team` = the other partnership

Mapping from seat index to team:
- If `declarer_seat ∈ {0,2}` then `decl_team = 0` and `def_team = 1`
- If `declarer_seat ∈ {1,3}` then `decl_team = 1` and `def_team = 0`

Role-conditioned outcomes:

If `decl_team == 0`:
- `decl_points = points_team_0`
- `def_points  = points_team_1`
- `decl_tricks = tricks_team_0`
- `def_tricks  = tricks_team_1`

If `decl_team == 1`:
- `decl_points = points_team_1`
- `def_points  = points_team_0`
- `decl_tricks = tricks_team_1`
- `def_tricks  = tricks_team_0`

Net points by role:
- `decl_net_points = decl_points - def_points`
- `def_net_points  = def_points - decl_points`

Role-conditioned success (derivable):
- `decl_success = 1{decl_tricks >= contract_tricks}`
- `decl_set     = 1 - decl_success`

Role-conditioned strategy IDs (derivable):

If `decl_team == 0`:
- `decl_play_strategy_id = team0_play_strategy_id`
- `def_play_strategy_id  = team1_play_strategy_id`
- `decl_bid_strategy_id  = team0_bid_strategy_id`
- `def_bid_strategy_id   = team1_bid_strategy_id`

If `decl_team == 1`:
- `decl_play_strategy_id = team1_play_strategy_id`
- `def_play_strategy_id  = team0_play_strategy_id`
- `decl_bid_strategy_id  = team1_bid_strategy_id`
- `def_bid_strategy_id   = team0_bid_strategy_id`

### 4.3 Win and tie definitions (authoritative)

Two “winner” concepts are tracked (both required):

1) **Points win** (authoritative team outcome):
- `team0_points_win  = 1{points_team_0 > points_team_1}`
- `team0_points_tie  = 1{points_team_0 == points_team_1}`
- `team0_points_loss = 1{points_team_0 < points_team_1}`
- Team1 is symmetrical.

2) **Declarer success** (authoritative role outcome):
- `decl_success = 1{decl_tricks >= contract_tricks}`

Tie handling:
- Points ties are reported as ties (not as half-wins) unless a downstream report explicitly chooses otherwise.

### 4.4 Legacy / debugging metric (non-authoritative): trick majority win

This metric may exist in early code paths for convenience. It is **not** a substitute for points win.

- `team0_trick_win  = 1{tricks_team_0 >= 6}`
- `team0_trick_tie  = 1{tricks_team_0 == 5}`
- `team0_trick_loss = 1{tricks_team_0 <= 4}`
- Team1 is symmetrical.

---

## 5. Core Metrics (Authoritative Definitions)

Unless otherwise stated, all metrics below are computed over **non-redeal hands** only.

Let:
- `H` be the set of non-redeal hands in scope
- `N = |H|` (this is `N_hands_nonredeal`)

### 5.1 Deal / sample counts
- `N_attempted_hands` = number of hand records including redeals
- `N_hands_nonredeal` = number of non-redeal hands
- `N_redeals` = number of redeal events

### 5.2 Points (team-level)
For Team0:
- `team0_mean_points = mean(points_team_0 over H)`
- `team0_mean_net_points = mean(team0_net_points over H)`

For Team1:
- `team1_mean_points = mean(points_team_1 over H)`
- `team1_mean_net_points = mean(team1_net_points over H)`

### 5.3 Tricks (team-level)
For Team0:
- `team0_mean_tricks = mean(tricks_team_0 over H)`
- `team0_mean_net_tricks = mean(team0_net_tricks over H)`

For Team1 similarly.

### 5.4 Win rates by points (team-level)
For Team0:
- `team0_points_win_rate  = mean(team0_points_win over H)`
- `team0_points_tie_rate  = mean(team0_points_tie over H)`
- `team0_points_loss_rate = mean(team0_points_loss over H)`

Team1 similarly.

### 5.5 Declarer success rate (role-level)
- `decl_success_rate = mean(decl_success over H)`
- `decl_set_rate = 1 - decl_success_rate`

### 5.6 Declarer EV and defender EV (role-level)
- `decl_mean_points = mean(decl_points over H)`
- `def_mean_points  = mean(def_points over H)`

- `decl_mean_net_points = mean(decl_net_points over H)`
- `def_mean_net_points  = mean(def_net_points over H)`

### 5.7 Contract performance by bid level
For each bid level `b` in `{1..10}`:
- `decl_success_rate_by_bid[b] = mean(decl_success | contract_tricks == b)`
- `decl_mean_points_by_bid[b] = mean(decl_points | contract_tricks == b)`
- `decl_mean_net_points_by_bid[b] = mean(decl_net_points | contract_tricks == b)`
- `decl_set_rate_by_bid[b] = 1 - decl_success_rate_by_bid[b]`

### 5.8 Distribution / risk summaries
For each of the following series, report at least:
- mean, std dev, std error, median
- p10/p50/p90 (or p25/p50/p75)
- min/max
- N

Series:
- `points_team_0`, `points_team_1`
- `team0_net_points`, `team1_net_points`
- `decl_points`, `def_points`
- `decl_net_points`

---

## 5.9 Strategy-centric metrics (required under TEAM_RANDOMIZED)

Because TEAM_RANDOMIZED mixes strategies across Team0/Team1, headline comparisons must be computed **by strategy ID**, not only by team index.

### 5.9.1 Canonical transformation: team-hand rows

For each non-redeal hand, create two derived rows (one per team):

`team_hand` row schema (derived):
- `hand_id`, `deal_id`, `seed`
- `team_id` ∈ `{0,1}`
- `dealer_seat`
- Contract: `contract_type`, `contract_tricks`, `contract_trump`
- Role: `is_declaring_team` (bool), `is_defending_team` (bool)
- Outcomes: `points`, `tricks`, `net_points`, `net_tricks`
- Strategy IDs: `play_strategy_id`, `bid_strategy_id`
- Strength: `hand_strength` and/or `hand_strength_bucket`

Derivations:
- If `team_id == 0`: `points = points_team_0`, `tricks = tricks_team_0`, `net_points = team0_net_points`, `net_tricks = team0_net_tricks`,
  `play_strategy_id = team0_play_strategy_id`, `bid_strategy_id = team0_bid_strategy_id`
- If `team_id == 1`: analogous using Team1 fields.
- `is_declaring_team = (team_id == decl_team)`
- `is_defending_team = (team_id == def_team)`

All strategy-centric metrics are computed by aggregating over these `team_hand` rows.

### 5.9.2 Strategy performance (play and bid)

For any strategy ID `S`:

Play strategy:
- `play_mean_points[S] = mean(points | play_strategy_id == S)`
- `play_mean_net_points[S] = mean(net_points | play_strategy_id == S)`
- `play_points_win_rate[S] = mean(1{net_points > 0} | play_strategy_id == S)`
- `play_points_tie_rate[S] = mean(1{net_points == 0} | play_strategy_id == S)`
- Role-conditioned:
  - `play_decl_mean_points[S] = mean(points | play_strategy_id == S and is_declaring_team)`
  - `play_def_mean_points[S]  = mean(points | play_strategy_id == S and is_defending_team)`

Bid strategy:
- analogous `bid_*` metrics using `bid_strategy_id`.

All must include uncertainty stats and N (Section 7).

### 5.9.3 Head-to-head paired delta (recommended)

For a two-strategy comparison A vs B (play or bid), define the paired per-hand delta:

Include only hands where one team uses A and the other uses B (for the relevant strategy type).

For play strategies:
- If `team0_play_strategy_id == A` and `team1_play_strategy_id == B`: `delta_A_minus_B = points_team_0 - points_team_1`
- If `team0_play_strategy_id == B` and `team1_play_strategy_id == A`: `delta_A_minus_B = points_team_1 - points_team_0`

Then report:
- `mean(delta_A_minus_B)`, SE, normal CI, bootstrap CI, N
- win/tie/loss rates: `mean(1{delta > 0})`, `mean(1{delta == 0})`, `mean(1{delta < 0})`

This paired reporting is typically lower-variance than comparing separate means.

---

## 6. Required Breakouts (Reporting Dimensions)

All core metrics (Section 5) and strategy-centric metrics (Section 5.9) must be reportable with the following breakouts.
If a breakout is not applicable, it must be omitted or labeled `N/A` consistently.

### 6.1 By contract type
Group by:
- `contract_type` ∈ `{"suit", "high", "low"}`

Required:
- `decl_success_rate` by contract type
- `decl_mean_points`, `decl_mean_net_points` by contract type

### 6.2 By trump suit (suit only)
If `contract_type == "suit"`, group by:
- `contract_trump` ∈ `{S,H,D,C}`

### 6.3 By contract tricks (bid level)
Group by:
- `contract_tricks` ∈ `{1..10}`

(See also Section 5.7; this breakout is mandatory.)

### 6.4 By dealer seat
Group by:
- `dealer_seat` ∈ `{0,1,2,3}`

### 6.5 By declarer position relative to dealer
Derive `declarer_position_relative_to_dealer` from `dealer_seat` and `declarer_seat`:
- `LHO` if `declarer_seat == (dealer_seat + 1) mod 4`
- `partner` if `declarer_seat == (dealer_seat + 2) mod 4`
- `RHO` if `declarer_seat == (dealer_seat + 3) mod 4`
- `dealer` if `declarer_seat == dealer_seat`

Group by:
- `declarer_seat` and `declarer_position_relative_to_dealer`

### 6.6 By play strategy and bidding strategy
Report strategy-centric results (Section 5.9) by:
- `play_strategy_id`
- `bid_strategy_id`

### 6.7 By hand strength buckets (required)
At minimum, report:
- team-level outcomes by `teamX_hand_strength_bucket`
- role-level outcomes by `decl_hand_strength_bucket` and `def_hand_strength_bucket` (if available)

Recommended:
- joint buckets: `(decl_strength_bucket, def_strength_bucket)` where sample size permits.

### 6.8 Recommended additional breakouts (high signal; add when data exists)

1) **Auction context**
- `current_high_tricks_when_declarer_bid`
- `did_declarer_open` (true if declarer was first non-pass bid)
- `num_bids_before_declarer`

2) **Overtricks**
- `overtricks = max(0, decl_tricks - contract_tricks)`
- Report EV and distribution by overtricks

3) **Set severity**
- `set_margin = contract_tricks - decl_tricks` when set, else 0
- Breakout by set margin buckets

4) **Volatility / risk by contract**
- std dev of `decl_points` by (`contract_type`, `contract_tricks`)

### 6.9 Redeal metrics (reported separately)
Even though redeals are excluded elsewhere:
- `redeal_rate = N_redeals / N_attempted_hands`

Also report redeal rate by:
- dealer seat
- bidding strategy (team-level and seat-level if available)

---

## 7. Uncertainty and Statistical Reporting

All headline aggregates must include uncertainty statistics.

### 7.1 Standard error (SE)

For a metric that is a mean over hands (e.g., `team0_mean_net_points`):
- `SE = sd(x) / sqrt(N)` where `sd` is sample standard deviation over H.

For a proportion (e.g., `decl_success_rate`), treat it as a mean of 0/1:
- `SE = sqrt(p*(1-p)/N)` where `p` is the sample proportion.

### 7.2 Confidence intervals (normal approximation)

Default 95% CI:
- `CI_95 = mean ± 1.96 * SE`

Notes:
- This is acceptable for large N.
- For small N or heavy tails, bootstrap CIs are preferred (next section).

### 7.3 Bootstrap confidence intervals

Compute bootstrap CIs by resampling **hands**:

- Choose `B` bootstrap resamples (default: `B = 1000`).
- For each resample, sample `N` hands with replacement from H and recompute the metric.
- Report bootstrap percentile CI:
  - `CI_95_boot = [p2.5, p97.5]` of the bootstrap metric distribution.

Required reporting:
- `B` used
- sampling unit: **hand**
- whether redeals were excluded (must be yes per Section 1.2)

### 7.4 Baseline descriptive stats (required)

For any primary series reported (points/net points/tricks), include:
- mean
- std dev
- std error
- median
- quantiles (p10/p50/p90 or p25/p50/p75)
- min/max
- N

### 7.5 Minimum sample thresholds (recommended)

For any breakout group:
- Always report `N_group`
- If `N_group < 30`, flag the group as **low sample** in reports and interpret CIs cautiously.
- Bootstrap CIs may still be computed, but must be labeled low-sample.

---

## 8. Comparability Rules (Prevent Metric Drift)

Two experiment outputs are comparable **only if** all of the following match:

- Ruleset version (including `RULES.md` semantics; tracked via config hash / schema version)
- Data schema version (`SCHEMA_VERSIONING.md`)
- Metric definitions in this document (no local edits)
- Opponent mix and seat assignment mode
- Random seeds / reproducibility metadata (`REPRODUCIBILITY.md`)
- Strategy IDs refer to the same policy implementations

Reports must include:
- git SHA
- config hash
- schema version
- metrics version (this doc version or hash)

---

## 9. Minimum Reporting Tables (v0.1)

Every experiment report should include at minimum:

1) **Topline (non-redeal hands)**
- `N_hands_nonredeal`, `redeal_rate`
- Team0: mean points, mean net points, points win/tie/loss rates
- Team1: mean points, mean net points, points win/tie/loss rates
- Declarer: success rate, mean points, mean net points

2) **Strategy-centric topline (required under TEAM_RANDOMIZED)**
- For each play strategy ID: mean points, mean net points, win/tie/loss rates, role-conditioned declarer/defender EV
- For each bid strategy ID: same
- For A vs B: paired `delta_A_minus_B` mean + CI + bootstrap CI + N

3) **By contract_type**
- declarer success rate and EV by `{"suit", "high", "low"}`

4) **By contract_tricks**
- declarer success rate and EV by bid level (1..10)

5) **By dealer seat**
- key outcomes (e.g., decl_success_rate, decl_mean_net_points, strategy deltas) by `dealer_seat`

6) **By hand strength buckets**
- declarer success rate and EV by strength bucket

All topline means and rates must include:
- SE, normal 95% CI, bootstrap 95% CI, and N.

---

## Appendix A: Open Decisions (TBD)

- Match-level metrics for multi-hand matches and target-score formats
- ELO/leaderboard scoring across many strategy variants (optional)
- Advanced dependence-aware SEs (clustered by deal_id) if deal reuse creates correlation
