# Canonical Lineage Rebuild — v2

**Date:** 2026-03-13
**Status:** PROPOSED
**Scope:** Repository reorganization, multi-model comparison framework, and canonical evidence contract for Arc D v2
**Supersedes:** `2026-03-13_canonical-lineage-rebuild-proposal.md` (v1) and ad hoc rung/report structure used across `docs/04_reports/r0`, `docs/04_reports/r1`, `docs/04_reports/r1_5`

---

## 1. Decision

Create a new research lineage (`arc_d_v2`) with a multi-model comparison framework,
clean evidence contract, standardized reporting, and reproducible rung packages.

**Key shift from v1 lineage:** Instead of gating on a single model's promotion, run
all models at every rung and report findings. Replace incumbent/promotion language
with an anchor-based comparison model.

**Why this shift:** 16 R1 experiments and the full R1.5 ablation campaign proved that
model capacity dominates information effects by 35:1 (H15). The single-model
promotion approach created false bottlenecks — suit regression blocked OLS promotion
while GBT resolved it trivially. Multi-model comparison gives attribution and
faster progress simultaneously.

This proposal does **not** delete or invalidate legacy work. Existing reports remain
as historical material.

## 2. Research Intent

**Goal:** Identify optimal bidding strategies for standalone hands in Bid Euchre
(double-deck, 10-A variant with bowers).

This research focuses exclusively on the **bidding decision**: given a hand of
10 cards and available auction context, what is the best bid (contract type,
level, and bid modifiers like moon/loner)? It does not address:

- **Trick play optimization** — how to play cards after the auction. Card play
  uses a fixed strategy (GluttonStrategy) across all experiments.
- **Game-level strategy** — how to adjust bidding based on running score, game
  phase, or match state. All hands are evaluated independently.
- **Cross-hand learning** — using results from prior hands to inform future
  bidding. No history features are included.
- **Card inference during trick play** — tracking which cards opponents play
  during tricks to update beliefs about their remaining hands. Card inference
  from the *auction* (R4+) is in scope; inference during *trick play* is not
  (trick play uses a fixed strategy).

**Why standalone hands:** Isolating the bidding decision from game-level
strategy removes a major confounder. A bidding model that optimizes per-hand
expected value is a necessary foundation before adding game-state adjustments.
The rung progression (R0*→R3) incrementally adds auction context to test which
information sources improve hand-level bidding quality.

**What success looks like:** A model (or ensemble of models) that demonstrably
outperforms hand-coded heuristics on net_eppd across all contract types, with
understood tradeoffs between model families (capacity, interpretability,
tail risk).

## 3. Goals

1. **Multi-model attribution** — Same data, same context, different models → isolate capacity vs information effects
2. **Agent-executable** — Autonomous agents can run a rung end-to-end from the runbook alone
3. **Consistent evidence** — Same tables, charts, and metrics at every rung, generated from machine-readable artifacts
4. **Strong provenance** — Every claim traces to a run, table, and artifact
5. **Clear governance** — Plans, decisions, and Q&A are separated from evidence but linked

## 4. Key Definitions

### 4.1 What R0 Means in the New Lineage

**R0\* = hand-only context with the modern action-value framework.**

This is NOT a replay of the legacy R0 (bidless data, tricks_won target). It is:
- **Training data:** Action-value dataset (counterfactual {action, bid_n, outcome} tuples)
- **Target:** net_points (not tricks_won)
- **Features:** 39 hand features + action features (bid_n, bid_n_sq). No partner/opponent context.
  - Uses `--feature-set r0` in `train_action_value.py` (39 R0 hand features only)
- **Baseline anchor:** Frozen `hybrid_r0_full` artifact (legacy R0 incumbent, tricks_won target)

The anchor model is NOT retrained — it serves as a fixed cross-lineage reference point.
All 6 primary roster models ARE trained fresh on the new R0* data.

**Continuation policy:** The action-value dataset generator requires a
`--continuation-artifact` — a bidder that plays out hands after each counterfactual
action to estimate outcomes.

**The continuation policy is fixed for the entire lineage:** always use the frozen
anchor artifact (`data/artifacts/arc_d/r0/hybrid_r0_full.json`). This ensures that
rung-to-rung comparisons are clean ablations — the ONLY variable that changes between
R0* and R1 is the context bundle (new features), not the label-generation policy.

If a future experiment wants to test "what if a better continuation policy generates
better labels?", that is a separate ablation, not a rung transition. It would be
logged as an exploratory analysis (§16) and, if impactful, proposed as a lineage
amendment (§20).

**Rationale:** This isolates the "what does hand-only information give each model type?"
question using the modern objective (net_points). Comparing to the frozen hybrid_r0_full
anchor shows absolute progress.

### 4.2 Sample Size Contract

| Mode | Deals | Purpose | When |
|------|-------|---------|------|
| SMOKE | 50 | Does it run? | Script validation, CI |
| QUICK | 2,500 | Directional signal | Screening, hypothesis check |
| FULL | 50,000 | Publication-grade | Final rung evidence |

### 4.3 Seed Contract

| Mode | Seeds | Values |
|------|-------|--------|
| SMOKE | 1 | 42 |
| QUICK | 1 | 42 |
| FULL | 3 | 42, 123, 456 |

All seeds must appear in run metadata and be reproducible via `--seed <N>`.

### 4.4 Anchor Model

**Frozen baseline anchor:** `hybrid_r0_full` (legacy R0 artifact, `data/artifacts/arc_d/r0/hybrid_r0_full.json`)

Purpose:
- Stable cross-lineage comparison target
- Every model at every rung reports delta vs anchor
- Never retrained, never replaced

Additionally, track **best-in-lineage** (the model with highest pooled net_eppd across
completed rungs) for local progress comparison. Best-in-lineage updates automatically
when a new rung completes; no ceremony required.

### 4.5 Status Taxonomy

Every model artifact and run carries one of:

| Status | Meaning |
|--------|---------|
| `canonical` | Part of the official rung evidence package |
| `exploratory` | Ad hoc analysis, not yet promoted to canonical |
| `superseded` | Replaced by a newer canonical version |
| `archived` | Historical — from v1 lineage, preserved for reference |
| `quarantined` | Known-bad (wrong seed, corrupt data, training bug) |

## 5. Model Roster

The lineage uses one fixed roster. All models receive the same context bundle at
each rung.

### 5.0 Primary Roster (Trained Models + Heuristic Baseline)

| # | Name | Class | Selection | What It Tests |
|---|------|-------|-----------|---------------|
| 1 | `modeloespecifico` | ModeloEspecifico | — | Floor — hand-coded domain knowledge |
| 2 | `selected_two_stage_av` | TwoStageActionValueBidder | Forward selection | Decomposition — P(make) × E[pts\|make] with optimal features |
| 3 | `gbt_av` | GBTActionValueBidder | All features | Nonlinear capacity — tree partitions |
| 4 | `constrained_ols_av` | ActionValueBidder | Locked 3/2/2 | Attribution control — theory-driven feature set |
| 5 | `selected_ols_av` | ActionValueBidder | Forward selection | OLS best — empirically optimal feature subset |
| 6 | `full_ols_av` | ActionValueBidder | All features | Diagnostic — does feature selection help OLS? |

**Linear model design:**
- `constrained_ols_av` — minimal, theory-driven features (3/2/2 per contract)
- `selected_ols_av` — forward-selection OLS (iterative best-subset via GroupKFold).
  This is the "real" OLS entry and the primary linear comparator against GBT.
- `full_ols_av` — plain OLS on all features (no selection, no regularization).
  Diagnostic control: if it matches `selected_ols_av`, selection doesn't matter.

**Decomposition design:**
- `selected_two_stage_av` — two-stage with forward selection per sub-model
  (P(make) logistic, E[pts|make] OLS, E[pts|set] OLS). Each sub-model gets
  its own optimal feature subset. This is the primary structural-hypothesis entry.

### 5.0.1 Legacy Baselines (R0* Only, Floor Calibration)

These models are included at R0* to re-establish the floor and provide continuity
with the original R0 evidence. They are fixed heuristics — no training required.
At subsequent rungs they may be dropped if they add no diagnostic value (via
amendment).

| # | Name | Class | Purpose |
|---|------|-------|---------|
| 7 | `stricthellraiser` | StrictHellRaiser | Mid-tier heuristic baseline |
| 8 | `rankthetank` | RanktheTank | Naive heuristic floor |

### 5.0.2 R0* Floor Calibration Policy

Canonical R0* floor calibration uses the roster baselines above:
- `modeloespecifico` — heuristic mid-tier
- `stricthellraiser` — heuristic mid-tier
- `rankthetank` — naive floor

Archived or legacy phase-0-style random floors (e.g., `RandomLegalStrategy`,
`AlwaysPassBidder`) may be regenerated only as `exploratory`. They do not
enter the canonical roster, cross-rung tables, or lineage rankings unless
added via amendment (§20).

### 5.0.3 Naming Convention

- `constrained_ols_av`: OLS trained on a locked per-contract feature set (§5.1).
- `selected_ols_av`: Forward-selection OLS — iteratively adds features based on
  out-of-fold validation improvement. Uses `forward_select` from
  `src/bid_euchre/models/feature_selection.py` with GroupKFold by hand_id.
- `full_ols_av`: Plain OLS trained on ALL features available at the rung.
  No feature search, no regularization. Diagnostic control only.
- `selected_two_stage_av`: Two-stage model with forward selection applied
  per sub-model (P(make) logistic, E[pts|make] OLS, E[pts|set] OLS). Each
  sub-model gets its own optimal feature subset.
- `gbt_av`: Gradient Boosted Trees on all features. GBT handles feature
  selection internally via tree splits — no explicit selection needed.

**Roster rules:**
- Roster is fixed for the lineage lifetime.
- Models may be added at rung boundaries (never mid-rung) via a lineage amendment.
- If a model cannot consume the rung's context bundle, it is excluded from that rung
  but remains in the roster for future rungs. Exclusion is documented in the manifest.
- ModeloEspecifico does not train on data — it is a fixed heuristic that provides
  a floor for "how good is hand-coded knowledge?"
- Legacy baselines (§5.0.1) are primarily for R0* floor calibration. Their inclusion
  at subsequent rungs is optional and controlled by amendment.

### 5.1 Constrained Feature Set Definition

The constrained OLS arm uses a locked feature set per contract type:

| Contract | Features |
|----------|----------|
| suit | bowers, trump_count, offsuit_aces + action terms |
| high | offsuit_aces, quick_tricks + action terms |
| low | offsuit_tens_count, quick_tricks + action terms |

This matches the v1 OLSa constrained arm for cross-lineage comparability.
As new context features are added (partner, opponent), the constrained arm
adds them to the locked set (specified per rung in the manifest).

**Infrastructure note:** `train_action_value.py` currently supports `--feature-set`
choices: `full` (52), `r0` (39 hand), `no-partner` (52, partner zeroed),
`interaction` (52+3). The per-contract 3/2/2 locked set does NOT exist as a
`--feature-set` option. Implementation requires either:
- **(a)** Add a `constrained` feature set to `FEATURE_SETS` in
  `train_action_value.py` that maps to per-contract locked features, or
- **(b)** Use `--feature-set r0` (all 39 hand features) as a proxy for
  "constrained" at R0*, accepting that it is not identical to the legacy 3/2/2 lock.

**Recommendation:** Option (a) — add a `constrained` feature set. This is a small
code change (~10 lines) and preserves exact cross-lineage comparability.

## 6. Context Ladder

| Rung | Type | What Changes | Total State Features | Schema | Key Question |
|------|------|-------------|---------------------|--------|--------------|
| R0* | Features | Hand-only (39 hand) | 39 | v7 | What does each model extract from hand information alone? |
| R1 | Features | +6 partner (3 suit-relative, 2 contract-type, 1 pass) | 45 | v8 | Does partner signal help? Which models use it? |
| R2 | Features | +12 opponent (6 per opponent × 2, left/right split) | 57 | v9 | Does opponent signal help? Which models use it? |
| R3 | **Action Space** | +Moon & Loner bids (engine expansion) | 57 + action features | v10 | Do models learn when moon/loner is worth the risk? |
| R4+ | Features | Card inference from auction (TBD) | TBD | TBD | Can models infer opponent holdings from bids? |

### 6.1 R1 Partner Feature Contract (v2 Suit-Relative Channels)

The R1 context bundle adds **4 partner features** using suit-relative channels
that exploit Euchre's bower mechanics. This replaces the coarse v1 partner
features (`partner_bid_level`, `partner_suit_match`) with channels that
distinguish between same-suit (shared bowers), same-color (left bower overlap),
and off-color (no bower connection).

Implemented in `src/bid_euchre/features/auction_context.py` as
`extract_partner_features_v2()`.

| Feature | Type | Channel | Euchre Semantics |
|---------|------|---------|------------------|
| `partner_level_same_suit` | int (0–10) | Suit-relative | Direct support — shared trump + right bower |
| `partner_level_same_color` | int (0–10) | Suit-relative | Indirect support — left bower overlap |
| `partner_level_off_color` | int (0–10) | Suit-relative | Weak/competing — no bower connection |
| `partner_level_high` | int (0–10) | Contract-type | Distributed ace/king strength — helps suit as offsuit winners |
| `partner_level_low` | int (0–10) | Contract-type | Ten/low concentration — different hand profile |
| `partner_passed` | int (0\|1) | Auction state | Explicit pass signal |

**Color mapping** (from `src/bid_euchre/core/cards.py` `SAME_COLOR_SUIT`):
H ↔ D (red), S ↔ C (black).

**Examples** (evaluating hearts as candidate trump):
- Partner bid 7H → `same_suit=7, same_color=0, off_color=0, high=0, low=0`
- Partner bid 5D → `same_suit=0, same_color=5, off_color=0, high=0, low=0`
- Partner bid 6S → `same_suit=0, same_color=0, off_color=6, high=0, low=0`
- Partner bid high 7 → `same_suit=0, same_color=0, off_color=0, high=7, low=0`
- Partner bid low 5 → `same_suit=0, same_color=0, off_color=0, high=0, low=5`
- Partner bid 3D then 7H → `same_suit=7, same_color=3, off_color=0, high=0, low=0`

**Why high/low channels are critical:** Without them, a partner bidding high 7
(strong distributed aces) looks identical to "partner didn't bid at all" — all
suit-relative channels read 0 since no-trump bids have no suit to map. The
contract-type channels make no-trump bids visible.

At R1, all models use `--feature-set full` (39 hand + 6 partner = 45 state features
+ action terms). The constrained arm adds these 6 partner features to its locked set.

### 6.2 R2 Opponent Feature Contract (Suit-Relative, Left/Right Split)

The R2 context bundle adds **8 opponent features** using the same suit-relative
channel decomposition as partner features, split by opponent position (left/right).

Implemented in `src/bid_euchre/features/auction_context.py` as
`extract_opponent_features()`.

Each opponent gets the same 6-feature template as partner (3 suit-relative +
2 contract-type + 1 pass), split by position.

**Left opponent** (seat (observer + 1) % 4 — bids *after* you in rotation):

| Feature | Type | Channel | Semantics |
|---------|------|---------|-----------|
| `opp_left_level_same_suit` | int (0–10) | Suit-relative | Direct competition — they want your bowers |
| `opp_left_level_same_color` | int (0–10) | Suit-relative | Indirect competition — bower tension |
| `opp_left_level_off_color` | int (0–10) | Suit-relative | Orthogonal — competing suit, no bower overlap |
| `opp_left_level_high` | int (0–10) | Contract-type | Opponent has distributed ace strength |
| `opp_left_level_low` | int (0–10) | Contract-type | Opponent has ten/low concentration |
| `opp_left_passed` | int (0\|1) | Auction state | Weakness signal |

**Right opponent** (seat (observer - 1) % 4 — bids *before* you in rotation):

| Feature | Type | Channel | Semantics |
|---------|------|---------|-----------|
| `opp_right_level_same_suit` | int (0–10) | Suit-relative | Direct competition — they want your bowers |
| `opp_right_level_same_color` | int (0–10) | Suit-relative | Indirect competition — bower tension |
| `opp_right_level_off_color` | int (0–10) | Suit-relative | Orthogonal — competing suit, no bower overlap |
| `opp_right_level_high` | int (0–10) | Contract-type | Opponent has distributed ace strength |
| `opp_right_level_low` | int (0–10) | Contract-type | Opponent has ten/low concentration |
| `opp_right_passed` | int (0\|1) | Auction state | Weakness signal |

**Left vs right distinction:** Left opponent bids *after* you — their signal
represents future competitive pressure. Right opponent bids *before* you —
their signal is past information you can react to. If GBT feature importances
show left ≈ right, a future amendment could pool (reducing 12 → 6 features).

At R2, all models use `--feature-set full` (39 hand + 6 partner + 12 opponent = 57
state features + action terms). The constrained arm adds the 12 opponent features
to its locked set.

### 6.3 Feature Architecture Summary

Every auction participant gets the same 6-feature template:
3 suit-relative level channels + 2 contract-type channels + 1 pass signal.

| Player | Features | Semantics |
|--------|----------|-----------|
| Partner (1 player) | 3 suit-relative + 2 contract-type + 1 pass = 6 | Support signal |
| Left opponent (1 player) | 3 suit-relative + 2 contract-type + 1 pass = 6 | Competition signal (bids after you) |
| Right opponent (1 player) | 3 suit-relative + 2 contract-type + 1 pass = 6 | Information signal (bids before you) |

Total auction context: 18 features (6 × 3 players). Combined with 39 hand = 57 at R2.

**Channel decomposition per player:**
```
suit-relative (3):  same_suit / same_color / off_color
contract-type (2):  high / low
auction state (1):  passed
```

The suit-relative channels capture WHERE a player bid relative to your candidate
trump (bower relationships). The contract-type channels capture no-trump bids that
would otherwise be invisible (all suit channels = 0). Together they provide full
coverage of the auction signal.

**Rules:**
- Every model in the roster receives the same context bundle at the same rung.
- Context bundles are additive — R1 includes R0* features plus partner features;
  R2 includes R1 features plus opponent features.
- The exact feature list for each rung is declared in the rung manifest before
  training begins.

### 6.4 R3 Moon & Loner Specification (Action Space Expansion)

R3 is fundamentally different from R0*–R2. It does not add features — it
expands the **action space** by introducing two new bid types that require
engine changes.

#### 6.4.1 New Bid Types

**Moon (±20 points):**
- Special suit/high/low contract — always level 10 (must win all 10 tricks)
- 2-card exchange between partners before trick play:
  - Mooner selects their 2 worst cards → gives to partner (face down)
  - Partner selects their 2 best cards for the declared suit → gives to mooner (face down)
  - Neither player sees the other's full hand — only the 2 cards received
  - Opponents see nothing about the exchange
  - Partner's selection is guided only by the declared suit (no table talk)
- Scoring: make = +20 to declaring team, fail = -20 to declaring team
- Defending team always scores their tricks (same as regular bids)

**Loner (±40 points):**
- Partner sits out entirely — declarer plays 1 vs 2 opponents
- 3-card tricks, 10 tricks total (each of 3 players still has 10 cards)
- Must win all 10 tricks
- Suit/high/low contract
- Scoring: make = +40 to declaring team, fail = -40 to declaring team
- Defending team always scores their tricks

#### 6.4.2 Auction Overcall Hierarchy

Single-round auction. Each seat bids exactly once. The hierarchy:

```
Regular bid N < Regular bid N+1 < Moon < Loner
```

**Dealer special privilege:** The dealer can "take away" any Moon or Loner bid
by calling the same type. No other player has this right.

- Non-dealer calls Moon → dealer can call Moon to take it away
- Non-dealer calls Loner → dealer can call Loner to take it away
- Non-dealer calls Moon → any player can overcall with Loner
- Regular bid cannot overcall Moon (only Loner or dealer-Moon can)

**Dealer Moon takeover:** When the dealer takes a moon bid, they get the card
exchange with *their* partner. The original moon bidder becomes a normal player.
If the mooner's partner IS the dealer and overcalls, the card exchange still
happens normally (dealer is now the mooner, original mooner is the partner).

#### 6.4.3 Action-Value Framework Changes

The current action space is:
```
PASS | BID(n, contract_type, trump_suit)
```

R3 expands to:
```
PASS | BID(n, contract_type, trump_suit) | MOON(contract_type, trump_suit) | LONER(contract_type, trump_suit)
```

Moon is always level 10. Loner is always level 10. The model must learn when
the fixed ±20 or ±40 payoff is worth the risk vs a regular bid at a lower level.

**New action features** (added to `bid_n`, `bid_n_sq`):

| Feature | Type | Definition |
|---------|------|-----------|
| `is_moon` | int (0\|1) | 1 if evaluating a moon bid |
| `is_loner` | int (0\|1) | 1 if evaluating a loner bid |

For regular bids: `is_moon=0, is_loner=0`. For pass: no action features (unchanged).

#### 6.4.4 Card Exchange Policy (for Counterfactual Dataset Generation)

The counterfactual dataset generator needs to simulate moon outcomes. This
requires a card exchange policy — what cards would each player give?

**Mooner policy (select 2 worst):** Heuristic based on hand evaluation:
- For suit contracts: give the 2 cards with lowest effective value (non-trump,
  non-ace, shortest suit)
- For high contracts: give the 2 lowest-ranked cards
- For low contracts: give the 2 highest-ranked cards

**Partner policy (select 2 best for declared suit):** Heuristic:
- For suit contracts: give trump cards (bowers first), then aces
- For high contracts: give aces, then kings
- For low contracts: give tens, then jacks

These are deterministic heuristics for dataset generation. The model does NOT
learn the exchange policy — it learns the expected outcome GIVEN the exchange.
The exchange policy is fixed for the lineage (same as continuation policy).

#### 6.4.5 Engine Work Required

R3 requires a **Phase A engineering effort** before rung evaluation can begin:

| Component | Change | Scope |
|-----------|--------|-------|
| `enumerate_legal_actions()` | Add MOON and LONER action types | Medium |
| Auction resolution | New overcall hierarchy + dealer takeover | Medium |
| Card exchange phase | New game phase between auction and trick play | Large |
| 3-player trick play | Partner sits out for loner (3-card tricks) | Large |
| Scoring | Fixed ±20/±40 for declaring team; defending team gets tricks | Small |
| `hand_end` logging | Record bid type, card exchange details | Small |
| Dataset generator | Generate moon/loner counterfactuals with exchange simulation | Large |
| Action features | Add `is_moon`, `is_loner` to feature vector | Small |

**R3 is split into two phases:**
- **R3 Phase A:** Engine expansion. All game engine changes, unit tests, smoke
  validation. No model training. Multi-PR engineering effort with sub-plans.
- **R3 Phase B:** Standard rung execution (Steps 0–9). Train all models on
  expanded action space, evaluate with H2H and comparator batteries.

#### 6.4.6 R3 Research Questions

| Question | What It Tests |
|----------|--------------|
| Do models learn when to bid moon vs regular-10? | Moon gives card exchange advantage but fixed scoring |
| Do models learn when to bid loner vs moon? | Loner = ±40 but no partner support |
| Does GBT exploit the card exchange better than OLS? | Exchange creates a complex conditional outcome |
| Does two-stage P(make) generalize to level-10 bids? | P(make) at 10 is very different from P(make) at 5 |
| How do R1 partner features affect moon decisions? | `partner_level_same_suit` directly predicts exchange quality |
| Do models learn the dealer takeover risk? | Bidding moon when dealer hasn't acted is riskier |

#### 6.4.7 Rung Progression Story

The R0*–R3 progression tells a coherent story about bidding complexity:

| Rung | Decision Complexity | What the Model Learns |
|------|--------------------|-----------------------|
| R0* | "Should I bid? How high?" | Hand strength → expected tricks |
| R1 | "Does my partner's bid change my decision?" | Partner support → adjusted confidence |
| R2 | "Does opponent competition change my decision?" | Competitive pressure → risk adjustment |
| R3 | "Should I go for moon (partner exchange) or loner (solo)?" | Risk/reward tradeoff at the extremes |

Each rung builds on the prior context. R1 partner features become essential
for moon decisions (predicting exchange quality). R2 opponent features inform
whether going for 10 tricks is realistic against strong opposition.

### 6.5 R4+ Card Inference (Future, TBD)

R4 would use auction behavior to infer opponent card holdings. This is
speculative and depends on R2/R3 results. Potential features:

- Probabilistic trump count estimates from opponent bids
- Inferred hand strength distributions from bid level + suit choice
- Bayesian updating from the full auction transcript

R4 is not specified in detail. Its design should be informed by:
- Which features GBT actually uses at R2/R3 (SHAP analysis)
- Whether auction information has diminishing returns
- Whether card inference adds value beyond what bid-level features already capture

**Rules:**
- R4 feature design is deferred until R2/R3 results are reviewed
- R4 requires a rung plan but not a lineage amendment (features only, no engine changes)

## 7. Directory Layout

### 7.1 Evidence and Reports

**Lineage-level (cross-rung):**
```text
docs/04_reports/arc_d_v2/
  cross_rung_deltas.csv         # Cross-rung delta table (§12.8) — updated each rung
  rung_model_spec.csv           # Cumulative rung × model spec table (§12.7)
```

**Per-rung:**
```text
docs/04_reports/arc_d_v2/<rung>/
  00_manifest.md              # What was run, governing plan, model roster
  01_results.md               # Model card + H2H + comparator rankings + tables
  02_decision.md              # Hypotheses, bounds, observations, conclusion, retrospective
  tables/                     # CSV source files for all tables in reports
    comparator_rankings.csv
    h2h_delta_matrix.csv
    model_performance.csv
    behavior_summary.csv
    behavior_by_contract.csv
    sanity_bounds_check.csv
    data_sanity.csv
    hypothesis_outcomes.csv
    dataset_provenance.csv
    artifact_inventory.csv
  charts/                     # PNG images embedded in reports
  chart_data/                 # CSV source data for every chart
  evidence_manifest.json      # Machine-readable provenance
  design_decisions.md         # Key decisions made during this rung (inline)
  qa_log.md                   # Open questions and resolved discussions
  exploratory/
    registry.md               # Index of exploratory analyses
    <exploratory_note_*.md>
```

### 7.2 Plans

This lineage follows the repo-wide governing plan framework
(`docs/02_agent/AGENTS.md` section 12). The directory structure instantiates
the generic framework for Arc D v2:

```text
plans/arc_d_v2/
  lineage_plan.md               # Governing plan (this document, canonical copy)
  amendments.md                 # Lineage amendment log (§20)
  sub_plan_registry.md          # Index of all sub-plans across all rungs
  <rung>/
    plan.md                     # Rung-level plan (hypotheses, context bundle)
    checkpoints.md              # Step-by-step progress log (agent state file)
    sub/                        # Sub-plans for implementation-heavy steps
      <YYYY-MM-DD>_<slug>.md    # Each follows plans/_templates/sub_plan.md
```

**Governing plan:** `lineage_plan.md` is the single governing document for the
entire lineage. Rung-level `plan.md` files contain rung-specific hypotheses and
details but are subordinate to the lineage plan.

**Sub-plan contract:** Sub-plans follow the repo-wide template
(`plans/_templates/sub_plan.md`) with all required fields: ID, parent, status,
owner, inputs, assumptions, dependencies, planned changes, validation, planned
outputs, observed outputs, outcome, handoff. Sub-plans are registered in
`plans/arc_d_v2/sub_plan_registry.md`.

**Checkpoint contract:** Each rung's `checkpoints.md` follows the repo-wide
template (`plans/_templates/checkpoints.md`). Agents read it to determine
where to resume work and update it before ending their session.

**Plan immutability:** The lineage plan is immutable during execution.
The evidence manifest records the governing commit SHA (the exact commit at
which the plan was frozen for execution). Git history provides revision
tracking — no separate snapshot files. Changes require the amendment process
(§20) or the repo-wide amendment protocol (AGENTS.md section 12.6).

### 7.3 Historical Preservation

Existing reports remain in place, unchanged:
- `docs/04_reports/r0/` — status: `archived`
- `docs/04_reports/r1/` — status: `archived`
- `docs/04_reports/r1_5/` — status: `archived`
- `docs/04_reports/r1_6/` — status: `archived`

No existing report becomes a canonical source for the new lineage.

## 8. Report Architecture

Three reports per rung, with a clear automation boundary: two are fully scripted,
one requires agent judgment.

### 8.1 Report Summary

| Report | Purpose | Generated By | Review Required? |
|--------|---------|-------------|-----------------|
| `00_manifest.md` | What was run | **Fully automated** from `evidence_manifest.json` | No — metadata only |
| `01_results.md` | What happened | **Mostly automated** from CSVs + charts | Light — check rendering |
| `02_decision.md` | What it means | **Agent-synthesized** from hypotheses + results | **Yes — human review before next rung** |

### 8.2 `00_manifest.md` — What Was Run

**Generation:** Fully automated by `generate_evidence_manifest.py` → render to
markdown. Zero prose. Structured metadata dump.

| Section | Content | Source |
|---------|---------|--------|
| Header | Lineage ID, rung ID, date, provenance SHA | `evidence_manifest.json` |
| Governing Plan | Link to `plan.md` + governing commit SHA | `evidence_manifest.json` |
| Model Roster | All models: class, selection, feature set, status | `evidence_manifest.json` → `roster[]` |
| Context Bundle | Feature list, count, schema version | `evidence_manifest.json` → `context_bundle` |
| Dataset Provenance | Deals, mode, seeds, continuation policy, run IDs | `tables/dataset_provenance.csv` |
| Artifact Inventory | Per-model artifact paths, schema versions, git SHAs | `tables/artifact_inventory.csv` |
| Configuration | Links to roster JSON, comparator config, H2H config | File paths |

### 8.3 `01_results.md` — What Happened

**Generation:** Mostly automated by `generate_rung_report.py` which reads CSVs
from `tables/` and embeds PNGs from `charts/`. Section headers and table
rendering are scripted. Brief auto-generated commentary accompanies each section
(e.g., "GBT leads comparator rankings at +X.XX pooled net_eppd").

This report contains all the numbers and charts but minimal interpretation.

| Section | Tables Embedded | Charts Embedded |
|---------|----------------|-----------------|
| §1 Data Sanity | `data_sanity.csv` | `outcome_distributions.png`, `seat_balance.png` |
| §2 Offline Model Performance | `model_performance.csv` | `r2_by_contract.png`, `mae_by_contract.png` |
| §3 Offline Diagnostics | — | `pred_vs_actual.png`, `residual_distribution.png`, `calibration_curve.png` |
| §4 Model Interpretability | `selected_features.csv` | `shap_summary.png`, `shap_dependence_top5.png`, `shap_interactions.png`, `selection_path.png` |
| §5 Cross-Model Decision Analysis | — | `decision_agreement.png`, `disagreement_outcomes.png` |
| §6 Comparator Rankings | `comparator_rankings.csv` | `comparator_ranking_bars.png`, `tail_risk_panel.png` |
| §7 H2H Battery | `h2h_delta_matrix.csv` | `delta_bars_by_contract.png`, `h2h_heatmap.png` |
| §8 Behavioral Analysis | `behavior_summary.csv`, `behavior_by_contract.csv` | `bid_behavior_panel.png`, `contract_mix_bars.png`, `bid_level_distribution.png` |
| §9 Sanity Bounds | `sanity_bounds_check.csv` | — |

**Rule:** This report never contains hand-typed metrics. Every number renders
from a CSV. If a value looks wrong, fix the generating script and regenerate —
do not edit the markdown.

### 8.4 `02_decision.md` — What It Means

**Generation:** Agent-synthesized. This is the only report that requires judgment.
The agent reads tables and charts from `01_results.md`, compares observed results
to preregistered hypotheses from `plan.md`, and writes the narrative.

| Section | Content | Source |
|---------|---------|--------|
| §1 Hypothesis Outcomes | Each hypothesis → expected, observed, status | Agent fills `tables/hypothesis_outcomes.csv` |
| §2 Key Findings | 3–5 bullet findings, each linked to supporting table/chart | Agent synthesis |
| §3 Surprises | Results outside expected bounds, investigation notes | Agent analysis |
| §4 Model Rankings | Which model won, by how much, on which contracts | `comparator_rankings.csv` + `h2h_delta_matrix.csv` |
| §5 Cross-Rung Progress | Comparison to prior rungs (if not R0*) | `cross_rung_deltas.csv` + cross-rung charts |
| §6 Interpretability Insights | Key SHAP findings, selection path results, decision comparison | SHAP charts + `selected_features.csv` |
| §7 Risks Carried Forward | Known issues, open questions, caveats | Agent judgment |
| §8 Retrospective | What worked, what didn't, what to change | Agent reflection |
| §9 Next Rung Recommendation | Proceed / investigate / pause / redirect | Agent recommendation |

**Rule:** This report references tables and charts but never redefines metrics.
Every cited number must trace to a CSV via the evidence manifest.

### 8.5 Report Generation Pipeline

```text
Runbook Steps 3-6 produce:
  tables/*.csv          (11 CSV files)
  charts/*.png          (18 PNG files)
  chart_data/*.csv      (source data for each chart)

Step 7 generates reports:
  ┌─ generate_evidence_manifest.py
  │    → evidence_manifest.json
  │    → 00_manifest.md                              [AUTOMATED]
  │
  ├─ generate_rung_report.py
  │    reads: tables/*.csv + charts/*.png
  │    → 01_results.md                               [AUTOMATED]
  │
  └─ Agent synthesis
       reads: 01_results.md + plan.md hypotheses
       → 02_decision.md                              [SYNTHESIZED]
       → tables/hypothesis_outcomes.csv               [AGENT-FILLED]

Step 8 updates lineage-level artifacts:
  → cross_rung_deltas.csv                            [AUTOMATED]
  → cross_rung_progression.png                       [AUTOMATED]
  → cross_rung_by_contract.png                       [AUTOMATED]
```

### 8.6 Scripts That Generate Reports

| Script | Input | Output | Exists? |
|--------|-------|--------|---------|
| `generate_evidence_manifest.py` | Run metadata, artifacts, CSVs | `evidence_manifest.json`, `00_manifest.md` | **NEW** |
| `generate_rung_report.py` | `tables/*.csv`, `charts/*.png` | `01_results.md` | **NEW** (replaces `arc_d_report.py`) |
| `generate_rung_tables.py` | Run artifacts, JSONL logs | All CSVs in `tables/` | **NEW** |
| `generate_rung_charts.py` | `tables/*.csv`, model artifacts | PNGs in `charts/`, CSVs in `chart_data/` | **EXISTS** (needs adaptation) |
| Agent | `01_results.md`, `plan.md` | `02_decision.md`, `hypothesis_outcomes.csv` | N/A |

### 8.7 Regeneration Contract

If any upstream data changes (e.g., a data issue is discovered):

1. Regenerate affected CSVs via `generate_rung_tables.py`
2. Regenerate charts via `generate_rung_charts.py`
3. Re-run `generate_rung_report.py` → new `01_results.md`
4. Re-run `generate_evidence_manifest.py` → new `00_manifest.md`
5. Agent rewrites `02_decision.md` (the only manual step)

Because `00_manifest` and `01_results` are deterministic, regeneration is
fully automated for 2 of 3 reports. Only the interpretation layer needs
human/agent re-synthesis.

## 9. Rung Execution Runbook

This is the step-by-step procedure for executing a rung. Autonomous agents should
follow this sequence exactly.

### Step 0: Plan & Hypothesize

**Actions:**
1. Create `plans/arc_d_v2/<rung>/plan.md` from the hypothesis framework (§10)
2. Define hypotheses with expected bounds based on previous rung results
3. Declare the context bundle (exact feature list)
4. Confirm roster applicability (which models can consume this context?)
5. Create directory scaffolding for the rung

**Validates:** Plan file exists, hypothesis table complete, directory structure created

**Gate:** Plan review (human or `/reviewing-plans`)

### Step 1: Generate Training Data

**Commands:**
```bash
# Generate action-value dataset
# --continuation-artifact: the policy that plays out hands for outcome estimation
#   FIXED for all rungs: frozen anchor (hybrid_r0_full.json)
#   See §4.1 — continuation policy never changes within the lineage
# --mode: SMOKE (50 deals), QUICK (2,500), FULL (50,000)
# --n-deals: optional override for mode default
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 \
  --mode <SMOKE|QUICK|FULL> \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/arc_d_v2/<rung>/datasets/
```

**Validates:**
- `action_value.parquet` exists in `--output-dir`
- Row count >= expected (deals × actions_per_deal)
- Feature columns match declared context bundle
- No NaN in feature columns

**Error recovery:** If generation fails, check seed, continuation artifact path,
and output directory. Do not proceed until dataset validates.

**Context-level note:** The current script does not have a `--context-level` flag.
At R0*, the dataset naturally contains only hand features (no partner/opponent
context in the auction). At R1+, partner features are extracted from the auction
transcript automatically. If rung-specific context filtering is needed, a small
script adaptation may be required (see §23 Phase 0).

### Step 2: Train All Roster Models

**Phase 0 prerequisite:** Step 2 may not be executed until Phase 0 items 3 and 4
are complete:
- `--feature-set constrained` implemented and tested (Phase 0 item 3)
- `--selection forward` implemented and tested (Phase 0 item 4)

If either prerequisite is missing, mark Step 2 `BLOCKED` in `checkpoints.md`.
Do not partially execute the rung with a reduced primary roster — return to
§23 Phase 0.

**Commands:**
```bash
# Common args
DATASET="data/runs/arc_d_v2/<rung>/datasets/action_value.parquet"
CONT_ART="data/artifacts/arc_d/r0/hybrid_r0_full.json"  # Fixed for all rungs (§4.1)
OUT_DIR="data/runs/arc_d_v2/<rung>/artifacts"

# Selected OLS — forward-selection OLS (primary linear comparator)
# At R0*: --feature-set r0 (39 hand features, no partner context)
# At R1+: --feature-set full (includes partner features)
# Uses forward_select from feature_selection.py
# Requires --selection forward (must be added to script, see §23 Phase 0)
uv run python scripts/internal/train_action_value.py \
  --seed 42 \
  --dataset "$DATASET" \
  --model-class ols \
  --feature-set r0 \
  --selection forward \
  --continuation-artifact "$CONT_ART" \
  --output-dir "$OUT_DIR/selected_ols"

# Full OLS — plain OLS on ALL features (diagnostic control)
uv run python scripts/internal/train_action_value.py \
  --seed 42 \
  --dataset "$DATASET" \
  --model-class ols \
  --feature-set r0 \
  --continuation-artifact "$CONT_ART" \
  --output-dir "$OUT_DIR/full_ols"

# GBT (same candidate feature set as full OLS)
uv run python scripts/internal/train_action_value.py \
  --seed 42 \
  --dataset "$DATASET" \
  --model-class gbt \
  --feature-set r0 \
  --continuation-artifact "$CONT_ART" \
  --output-dir "$OUT_DIR/gbt"

# Selected Two-Stage (logistic P(make) + conditional OLS, forward selection per sub-model)
# Requires --selection forward wired for two-stage path (see §23 Phase 0)
uv run python scripts/internal/train_action_value.py \
  --seed 42 \
  --dataset "$DATASET" \
  --model-class two-stage \
  --feature-set r0 \
  --selection forward \
  --continuation-artifact "$CONT_ART" \
  --output-dir "$OUT_DIR/selected_two_stage"

# Constrained OLS (locked per-contract features — see §5.1)
# Requires --feature-set constrained (must be added to script, see §5.1 note)
uv run python scripts/internal/train_action_value.py \
  --seed 42 \
  --dataset "$DATASET" \
  --model-class ols \
  --feature-set constrained \
  --continuation-artifact "$CONT_ART" \
  --output-dir "$OUT_DIR/constrained_ols"
```

**Note:** The baseline (ModeloEspecifico) and legacy baselines (StrictHellRaiser,
RanktheTank) do not train — they are fixed heuristics. They are
included in the H2H and comparator batteries but skip this step.

**Validates:**
- All artifact JSONs exist and pass schema validation
- Each artifact records: schema_version, feature_names, git_sha, seed
- Per-contract R² and MAE are finite and within plausible range

**Error recovery:** If training fails for model X:
- Log the failure in `checkpoints.md`
- Proceed with remaining models
- Record excluded model in rung manifest with reason

### Step 3: Offline Evaluation + Data Sanity (Phase 0-lite)

**Actions:**
1. Compute per-model offline metrics (R², MAE, n) by contract type
2. Generate model performance table CSV
3. Run optional diagnostics (calibration, residuals)
4. **Data sanity checks (Phase 0-lite):**
   - Dataset row count and completeness
   - Feature coverage (no NaN columns, expected feature count)
   - Action distribution (bid levels, pass fraction)
   - Contract-type balance (suit/high/low counts)
   - Outcome distributions (tricks_won, net_points histograms)
   - Seat balance (uniform across 4 seats)

These sanity checks replace the legacy Phase 0 workstream. They are lightweight
validation built into the rung, not a separate phase. Results are recorded in
`tables/data_sanity.csv` and summarized in `01_results.md`.

**Outputs:**
- `tables/model_performance.csv`
- `tables/data_sanity.csv`
- `charts/r2_by_contract.png`, `charts/mae_by_contract.png`
- `chart_data/r2_by_contract.csv`, `chart_data/mae_by_contract.csv`

### Step 3b: Model Interpretability Analysis

Run after offline evaluation, before H2H. Uses training-layer predictions
to understand *how* each model makes decisions, not just *how well*.

**Actions:**

1. **SHAP analysis (GBT):**
   - Compute SHAP values via `shap.TreeExplainer` on validation set
   - Generate per-contract SHAP summary (beeswarm), top-5 dependence plots,
     top-3 interaction plots
   - At R1+: specifically check whether new context features (partner/opponent
     channels) appear in SHAP top-10

2. **Forward selection diagnostics (selected_ols_av, selected_two_stage_av):**
   - Log the selection path: features added in order, OOF R² at each step
   - Generate selection path chart showing diminishing returns
   - Record final selected feature set per contract in manifest

3. **Prediction diagnostics (all trained models):**
   - Generate pred_vs_actual scatter per model × contract
   - Generate residual distributions per model × contract
   - Generate calibration curves per model (+ P(make) calibration for two-stage)

4. **Cross-model decision comparison:**
   - For each hand in eval set, compute each model's best action (bid level + contract)
   - Compute pairwise agreement rates (especially GBT vs OLS, GBT vs two-stage)
   - On disagreements: which model's choice had better actual net_points?
   - Profile disagreement hands: what features distinguish GBT-bids-OLS-passes?

**Outputs:**
- `chart_data/shap_values.csv` — per-prediction SHAP values for GBT
- `chart_data/shap_dependence.csv` — binned dependence data for top features
- `chart_data/shap_interactions.csv` — top interaction pairs
- `chart_data/selection_paths.csv` — forward selection R² path per model
- `chart_data/predictions.csv` — predicted vs actual per model × contract
- `chart_data/residuals.csv` — residuals per model × contract
- `chart_data/calibration_bins.csv` — binned calibration data
- `chart_data/decision_comparison.csv` — agreement/disagreement rates
- `chart_data/disagreement_outcomes.csv` — outcome analysis for disagreements
- `tables/selected_features.csv` — final feature sets from forward selection
- `charts/shap_summary.png` — SHAP beeswarm per contract
- `charts/shap_dependence_top5.png` — top-5 feature dependence curves
- `charts/shap_interactions.png` — top-3 interaction effects
- `charts/selection_path.png` — forward selection R² curves
- `charts/pred_vs_actual.png` — scatter per model × contract
- `charts/residual_distribution.png` — residual histograms
- `charts/calibration_curve.png` — calibration per model
- `charts/decision_agreement.png` — GBT vs OLS agreement rates by contract
- `charts/disagreement_outcomes.png` — who wins when models disagree?

**Key interpretability questions per rung:**

| Rung | Question | How to Answer |
|------|----------|--------------|
| R0* | What nonlinear patterns does GBT find in hand-only data? | SHAP dependence curves — look for non-monotonic or threshold effects |
| R0* | Why does GBT resolve suit regression? | Decision comparison — find hands where GBT predicts "set" that OLS misses |
| R0* | Does forward selection help OLS? Which features survive? | `selected_features.csv` + selection path plateau point |
| R1 | Does GBT use partner features? Which channels? | SHAP importance ranking — do partner features enter top-10? |
| R1 | Does GBT learn partner × hand interactions? | SHAP interaction plots for partner_level_same_suit × trump_count |
| R2 | Does GBT use opponent features? Left vs right? | SHAP importance of opp_left vs opp_right channels |
| R2 | Does GBT learn positional asymmetry? | Compare SHAP values for symmetric opponent features |

**Validates:**
- SHAP values sum to model prediction (consistency check)
- All `chart_data/*.csv` files produced before chart generation
- Selected feature sets are subsets of the rung's feature set

**Error recovery:** SHAP computation is independent of other steps. If it fails
(e.g., memory on large eval sets), subsample to 5,000 predictions and retry.
SHAP failure is a WARNING, not a BLOCKER — it doesn't affect H2H or comparator
evaluation.

### Step 4: H2H Battery

**Commands:**
```bash
uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --roster data/runs/arc_d_v2/<rung>/roster.json \
  --mode <QUICK|FULL> \
  --seed 42 \
  --n-per <MODE_DEALS> \
  --output data/runs/arc_d_v2/<rung>/h2h/
```

The roster JSON includes all roster models + the frozen anchor model.
At R0*: 6 primary + 2 legacy baselines + 1 anchor = 9 models (81 matchups).
At R1+: 6 primary + 1 anchor = 7 models (49 matchups), unless legacy baselines retained.

**Validates:**
- All matchups complete (N² matchups for N models in roster)
- No NaN in metrics
- Self-play win rates within [45%, 55%]

**Outputs:**
- `tables/h2h_delta_matrix.csv`
- `charts/h2h_heatmap.png`, `charts/delta_bars.png`
- `chart_data/h2h_delta_matrix.csv`

### Step 5: Comparator Battery

The comparator runner (`run_auction_comparator.py`) is **config-driven**, not
roster-driven. It takes a YAML config with `bidding_policies` and evaluates each
policy against `AlwaysPassBidder` sentinels in single-seat mode.

**Commands:**
```bash
# Step 5a: Generate comparator YAML config from roster
# This config lists all 6 primary roster models as bidding_policies.
# The anchor (hybrid_r0_full) is included via --olsa-artifact.
# Each bidder is evaluated independently against AlwaysPass sentinels.

# Run comparator for each roster model (single-seat mode)
uv run python scripts/internal/run_auction_comparator.py \
  --config data/runs/arc_d_v2/<rung>/comparator_config.yaml \
  --seed 42 \
  --single-seat \
  --n-per <MODE_DEALS> \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --bidder-class HybridOLSaBidder \
  --bidder-name anchor_hybrid_r0_full \
  --output data/runs/arc_d_v2/<rung>/comparator/comparator_report.json

# Step 5b: Extract bootstrap CIs from JSONL game logs
uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/runs/arc_d_v2/<rung>/comparator/ \
  --runs-dir data/runs/ \
  --battery-file comparator_battery.json \
  --single-seat \
  --seed 42 \
  --n-bootstrap 10000 \
  --output data/runs/arc_d_v2/<rung>/comparator/comparator_cis.json
```

**Infrastructure note:** The comparator config YAML must list all 6 primary
roster models as `bidding_policies` entries. A template YAML is created in
Phase 0 (§23, item 6). The `--olsa-artifact` flag adds the anchor to the roster.

**Comparator aggregation contract:** Comparator rankings are canonical only
when emitted at both pooled AND contract-type levels. `generate_rung_tables.py`
is the canonical aggregator that converts comparator JSONL outputs into:
- `tables/comparator_rankings.csv` — one row per `(model, facet)` where
  `facet ∈ {suit, high, low, pooled}`
- Required columns: `model`, `facet`, `net_eppd`, `ci_low`, `ci_high`,
  `bid_rate`, `make_rate`, `net_cvar_5`, `rank`

Step 5 is incomplete until both pooled and by-contract comparator outputs exist.

**Validates:**
- Per-bidder metrics exist for all roster models
- Bootstrap CIs computed for net_eppd, net_cvar_5
- Rankings are consistent (no NaN-induced inversions)
- Contract-faceted breakdown (suit/high/low/pooled) is present

**Outputs:**
- `tables/comparator_rankings.csv` (faceted: one row per model × facet)
- `charts/ranking_bars.png`, `charts/tail_risk.png`
- `chart_data/comparator_rankings.csv`

### Step 6: Sanity Bounds Check

Apply progression bounds to all models (see §11.1). Log results.

**Outputs:**
- `tables/sanity_bounds_check.csv`

**Gate:** If ANY model fails sanity bounds, flag in `checkpoints.md`.
Failing models are still reported but marked with a warning.
The rung proceeds as long as at least one model passes.

### Step 7: Generate Reports

**Canonical reporting stack** (in order):
1. `generate_rung_tables.py` — CSVs from run artifacts
2. `generate_rung_charts.py` — PNGs + chart_data CSVs from tables
3. `generate_interpretability.py` — SHAP, selection path, decision CSVs
4. `generate_evidence_manifest.py` — manifest JSON + `00_manifest.md`
5. `generate_rung_report.py` — `01_results.md` from CSVs + PNGs
6. Agent writes `02_decision.md`

`arc_d_report.py` is legacy and is NOT part of the `arc_d_v2` canonical pipeline.

**Commands:**
```bash
RUNG_DIR="data/runs/arc_d_v2/<rung>"
REPORT_DIR="docs/04_reports/arc_d_v2/<rung>"

# 1. Generate standardized tables
uv run python scripts/internal/generate_rung_tables.py \
  --rung-dir "$RUNG_DIR" \
  --output "$REPORT_DIR"

# 2. Generate charts from tables
uv run python scripts/internal/generate_rung_charts.py \
  --rung-dir "$RUNG_DIR" \
  --report-dir "$REPORT_DIR"

# 3. Generate interpretability artifacts
uv run python scripts/internal/generate_interpretability.py \
  --rung-dir "$RUNG_DIR" \
  --report-dir "$REPORT_DIR"

# 4. Generate evidence manifest + 00_manifest.md
uv run python scripts/internal/generate_evidence_manifest.py \
  --rung-dir "$RUNG_DIR" \
  --report-dir "$REPORT_DIR"

# 5. Generate 01_results.md from CSVs + charts
uv run python scripts/internal/generate_rung_report.py \
  --report-dir "$REPORT_DIR" \
  --output "$REPORT_DIR/01_results.md"
```

Then: agent synthesizes `02_decision.md` from hypotheses + results.

**Validates:**
- All tables referenced in reports exist as CSVs
- All charts referenced in reports exist as PNGs with source CSVs
- Evidence manifest is valid JSON with all required fields
- `01_results.md` contains no hand-typed metrics

### Step 8: Decision & Retrospective

**Actions:**
1. Compare observed results to preregistered hypotheses
2. Check sanity bounds (progression gate)
3. Update best-in-lineage if a model surpasses current best
4. Write `02_decision.md` with:
   - Hypothesis outcomes (confirmed/rejected/inconclusive)
   - Surprises (results outside expected bounds)
   - Risks carried forward
   - Recommendation for next rung
5. Update `checkpoints.md` with final status

**Gate:** Human review of `02_decision.md` before proceeding to next rung.

### Step 9: Archive & Advance

**Actions:**
1. Commit all evidence artifacts
2. Tag the rung: `arc_d_v2_<rung>_complete`
3. Update MEMORY.md with rung summary
4. Begin Step 0 for next rung

## 10. Hypothesis Framework

Every rung must preregister hypotheses before execution.

### 10.1 Hypothesis Template

```markdown
## Rung <ID> Hypotheses

| ID | Hypothesis | Metric | Expected Bound | Surprise If | Source |
|----|-----------|--------|----------------|-------------|--------|
| H1 | GBT resolves suit regression at this context level | suit_delta vs anchor | > 0.0 | < -0.5 | R1.5.3 QUICK: +1.110 |
| H2 | Partner context improves GBT | gbt_pooled_delta R1 vs R0* | > 0.0 | < -0.2 | H15: capacity >> info |
| H3 | OLS still shows suit regression | ols_suit_delta vs anchor | < 0.0 | > +0.5 | Structural OLS limitation |
| H4 | Two-stage closes gap vs GBT | two_stage_pooled - gbt_pooled | > -1.0 | < -1.5 | R1.5.3: gap = 0.750 |
```

### 10.2 Rules

- Hypotheses are written BEFORE training begins (preregistration).
- "Expected Bound" is the range we consider normal given prior evidence.
- "Surprise If" is the threshold that would change our research direction.
- After execution, each hypothesis gets a status: `confirmed`, `rejected`, `inconclusive`.
- Surprises trigger an exploratory investigation note before proceeding.

### 10.3 R0* Hypotheses (First Rung)

| ID | Hypothesis | Metric | Expected Bound | Surprise If | Source |
|----|-----------|--------|----------------|-------------|--------|
| H1 | GBT outperforms all OLS variants on suit | gbt_suit_delta vs anchor | > +0.5 | < 0.0 | R1.5.3 QUICK: +1.110 |
| H2 | GBT outperforms anchor on pooled | gbt_pooled_delta vs anchor | > +0.3 | < 0.0 | R1.5.3 QUICK: +1.067 |
| H3 | OLS AV outperforms anchor on high/low but not suit | ols_suit_delta vs anchor | < 0.0 | > +0.3 | R1.5 FULL: -0.142 |
| H4 | Two-stage reduces suit deficit vs flat OLS | two_stage_suit - ols_suit | > 0.0 | < -0.2 | R1.5.3: -0.066 vs -0.168 |
| H5 | ModeloEspecifico is competitive on high | especifico_high_delta vs anchor | > -0.5 | < -2.0 | Heuristic + hand-coded |
| H6 | GBT FULL shrinkage from QUICK is 30-50% | gbt_full_pooled / gbt_quick_pooled | 0.50–0.70 | < 0.40 or > 0.80 | Seed 42 FULL: 44% shrinkage (ratio 0.56) |
| H7 | All trained models beat RanktheTank (floor) | all_trained_pooled - rankthetank | > +5.0 | < +3.0 | R0 comparator: rankthetank at -9.665 |
| H8 | StrictHellRaiser beats RanktheTank | hellraiser_pooled - rankthetank | > +5.0 | < +3.0 | R0 comparator: legacy ordering stable |
| H9 | Full OLS ≈ constrained OLS (features don't matter for OLS) | full_ols_pooled - constrained_ols_pooled | [-0.2, +0.2] | abs > 0.5 | R1 finding: constrained ≈ full |

## 11. Progression & Decision Framework

### 11.1 Sanity Bounds (Progression Gate)

These determine whether a model's results are plausible enough to report.
Failing sanity bounds does NOT remove a model from the rung — it flags the
result for investigation.

| Metric | Lower Bound | Upper Bound | Rationale |
|--------|-------------|-------------|-----------|
| win_rate (self-play) | 0.45 | 0.55 | Self-play should be ~50% |
| bid_rate | 0.05 | 0.95 | Neither always-pass nor always-bid |
| make_rate | 0.40 | 1.00 | Must make a reasonable fraction |
| avg_bid_level | 3.5 | 7.0 | Not degenerate bidding |
| pass_rate | 0.00 | 0.60 | Selective is fine; majority-pass is suspect |
| contract_regression (any) | -2.0 | — | No catastrophic single-contract failure |

### 11.2 Anchor Comparison

Every model reports delta vs the frozen anchor at every rung:

```
delta_vs_anchor = model_net_eppd - anchor_net_eppd
```

Faceted by: suit, high, low, pooled. With bootstrap CIs.

This provides **absolute continuity** across the entire lineage.

### 11.3 Best-in-Lineage Tracking

After each rung, identify the model with the highest pooled net_eppd
(CI-adjusted: use CI_low to break ties). This becomes the **best-in-lineage**
reference for local progress comparison.

Best-in-lineage is informational, not ceremonial. No "promotion" event.
It updates automatically in the lineage registry.

### 11.4 Rung Decision Outcomes

Each rung concludes with one of:

| Outcome | Meaning | Action |
|---------|---------|--------|
| `PROCEED` | Results within expected bounds, no surprises | Advance to next rung |
| `INVESTIGATE` | Surprise result detected (outside expected bounds) | Exploratory analysis required before proceeding |
| `PAUSE` | Multiple models fail sanity bounds or data quality issue | Fix before re-running rung |
| `REDIRECT` | Results suggest the context ladder needs revision | Amend lineage plan |

Note: There is no `HALT` or `PROMOTE`. All models advance. The decision is about
the lineage direction, not individual model status.

### 11.5 Model Status Labels

After each rung, every model carries a status:

| Status | Meaning |
|--------|---------|
| `retained` | Passed sanity bounds, results reported normally |
| `flagged` | Failed one or more sanity bounds, results reported with warning |
| `excluded` | Could not run at this rung (e.g., cannot consume context bundle) |
| `experimental` | Added mid-lineage via amendment, not part of original roster |

## 12. Canonical Table Templates

### 12.1 Comparator Rankings Table (Tier 1 + Key Tier 2)

Required at every rung. Facet order: Suit, High, Low, Pooled.
This table contains **Tier 1 decision metrics + key Tier 2 behavioral context**.
No offline fit metrics (R², MAE).

```
| Rank | Model | Suit net_eppd [CI] | High net_eppd [CI] | Low net_eppd [CI] | Pooled net_eppd [CI] | bid_rate | make_rate | net_CVaR₅ |
|------|-------|-------------------|-------------------|------------------|---------------------|----------|-----------|-----------|
```

### 12.2 H2H Delta Table (vs Anchor)

Required at every rung.

```
| Model | Suit Δ [CI] | High Δ [CI] | Low Δ [CI] | Pooled Δ [CI] | Status |
|-------|-------------|-------------|------------|---------------|--------|
```

### 12.3 Model Performance Table (Offline)

Required at every rung.

```
| Model | R² suit | R² high | R² low | R² pooled | MAE suit | MAE high | MAE low | MAE pooled | n |
|-------|---------|---------|--------|-----------|----------|----------|---------|------------|---|
```

### 12.4 Behavior Summary Table

Required at every rung.

```
| Model | bid_rate | pass_rate | make_rate | avg_bid | bid_std | bid_min | bid_max | mix_suit | mix_high | mix_low | score_std | redeal_rate |
|-------|----------|-----------|-----------|---------|---------|---------|---------|----------|----------|---------|-----------|-------------|
```

### 12.4b Behavior by Contract Table

Required at every rung. One row per (model, contract_type). Facets key Tier 2
metrics that vary by contract.

```
| Model | Contract | bid_rate | make_rate | avg_bid | bid_std | bid_min | bid_max |
|-------|----------|----------|-----------|---------|---------|---------|---------|
```

### 12.5 Sanity Bounds Check Table

Required at every rung.

```
| Model | win_rate | bid_rate | make_rate | avg_bid | pass_rate | worst_contract_Δ | all_pass? |
|-------|----------|----------|-----------|---------|-----------|-------------------|-----------|
```

### 12.6 Hypothesis Outcome Table

Required at every rung.

```
| ID | Hypothesis | Expected | Observed | Status | Notes |
|----|-----------|----------|----------|--------|-------|
```

### 12.7 Rung × Model Spec Table (Source-of-Truth Inventory)

Required at every rung. This is the single most important table — it records
exactly what was evaluated. This table is a CSV schema first, rendered in
markdown second.

**CSV schema** (`tables/rung_model_spec.csv`):

| Column | Type | Description |
|--------|------|-------------|
| `rung` | string | Rung ID (e.g., "r0", "r1") |
| `model` | string | Model name from roster (e.g., "gbt_av") |
| `family` | string | Model family: "heuristic", "OLS", "GBT", "two-stage" |
| `target` | string | Training target: "net_points" or "—" for heuristics |
| `selection` | string | Feature selection: "all", "forward", "locked", "—" |
| `dataset_id` | string | Training dataset run ID, or "—" for heuristics |
| `feature_set` | string | Feature set used (e.g., "r0 (all 39)", "constrained (3/2/2)") |
| `context_bundle` | string | Context level (e.g., "hand-only (39)", "hand+partner (45)") |
| `continuation` | string | Continuation policy artifact name |
| `seeds` | string | Comma-separated seed list |
| `status` | string | "canonical", "excluded", "experimental" |
| `notes` | string | Free text |

**Example rows for R0*:**

| rung | model | family | target | selection | dataset_id | feature_set | context_bundle | continuation | seeds | status | notes |
|------|-------|--------|--------|-----------|------------|-------------|----------------|-------------|-------|--------|-------|
| r0 | modeloespecifico | heuristic | — | — | — | hand-coded | hand-only | — | — | canonical | no training |
| r0 | selected_two_stage_av | two-stage | net_points | forward | action_value_r0_42 | per sub-model | hand-only (39) | hybrid_r0_full | 42,123,456 | canonical | decomposition + selection |
| r0 | gbt_av | GBT | net_points | all | action_value_r0_42 | r0 (all 39) | hand-only (39) | hybrid_r0_full | 42,123,456 | canonical | tree-based |
| r0 | constrained_ols_av | OLS | net_points | locked | action_value_r0_42 | constrained (3/2/2) | hand-only (39) | hybrid_r0_full | 42,123,456 | canonical | theory-driven |
| r0 | selected_ols_av | OLS | net_points | forward | action_value_r0_42 | selected from r0 | hand-only (39) | hybrid_r0_full | 42,123,456 | canonical | primary OLS entry |
| r0 | full_ols_av | OLS | net_points | all | action_value_r0_42 | r0 (all 39) | hand-only (39) | hybrid_r0_full | 42,123,456 | canonical | diagnostic control |
| r0 | stricthellraiser | heuristic | — | — | — | hand-coded | hand-only | — | — | canonical | legacy baseline |
| r0 | rankthetank | heuristic | — | — | — | hand-coded | hand-only | — | — | canonical | legacy floor |

### 12.8 Cross-Rung Delta Table

One row per (model, rung). Enables longitudinal comparison across the lineage.
Populated incrementally as rungs complete. Includes Tier 1 deltas + key Tier 2
behavioral metrics for tracking changes.

```
| Model | Rung | Suit Δ [CI] | High Δ [CI] | Low Δ [CI] | Pooled Δ [CI] | bid_rate | make_rate | net_CVaR₅ | Status | Surprise? | Notes |
|-------|------|-------------|-------------|------------|---------------|----------|-----------|-----------|--------|-----------|-------|
```

This table lives at the lineage level (`docs/04_reports/arc_d_v2/cross_rung_deltas.csv`),
not inside a single rung directory. It is the primary tool for answering "how did
model X respond to new context across rungs?"

### 12.9 Dataset / Evidence Provenance Table

Required at every rung.

```
| Rung | Dataset ID | Deals | Mode | Seeds | Continuation Policy | Context Bundle | Feature Count | Generated By | Run ID | Notes |
|------|------------|-------|------|-------|---------------------|----------------|---------------|--------------|--------|-------|
```

### 12.10 Artifact Inventory Table

Required at every rung.

```
| Rung | Model | Artifact Path | Schema Version | Git SHA | Training Seeds | Status | Notes |
|------|-------|---------------|----------------|---------|----------------|--------|-------|
```

### 12.11 Data Sanity Table (Phase 0-lite)

Required at every rung.

```
| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| total_rows | >= N * actions_per_deal | ... | PASS/FAIL |
| feature_count | 39 (R0*) or 45 (R1) or 57 (R2) | ... | PASS/FAIL |
| nan_features | 0 | ... | PASS/FAIL |
| suit_fraction | ~0.4 | ... | PASS/FAIL |
| high_fraction | ~0.3 | ... | PASS/FAIL |
| low_fraction | ~0.3 | ... | PASS/FAIL |
| seat_balance_p | > 0.05 (ANOVA) | ... | PASS/FAIL |
| tricks_range | [0, 10] | ... | PASS/FAIL |
| net_points_mean | [-2, 6] | ... | PASS/FAIL |
```

### 12.12 Canonical Chart Specification

Every chart renders from a CSV in `tables/` or `chart_data/`. No chart reads
raw data (JSONL logs, model artifacts, parquet files) directly. Raw data must
first be processed into a `chart_data/*.csv` intermediate by the chart generation
script. This ensures every chart is auditable from its source CSV.

**Two classes of chart data sources:**
- **`tables/*.csv`** — charts that visualize the same data as report tables
  (e.g., ranking bars from `comparator_rankings.csv`)
- **`chart_data/*.csv`** — charts that need data not in any report table
  (e.g., per-deal bid level distributions, per-prediction scatter data).
  These CSVs are generated by `generate_rung_charts.py` as a preprocessing
  step before rendering the chart image.

#### Tier 1 Charts: Decision

| Chart | CSV Source | What It Shows |
|-------|-----------|---------------|
| `delta_bars_by_contract.png` | `tables/h2h_delta_matrix.csv` | H2H delta vs anchor, faceted suit/high/low/pooled, with CIs. One group per model. |
| `comparator_ranking_bars.png` | `tables/comparator_rankings.csv` | Comparator net_eppd by model, faceted by contract. Sorted by pooled descending. |
| `h2h_heatmap.png` | `tables/h2h_delta_matrix.csv` | Full N×N matrix — color-coded delta, one cell per matchup. |
| `tail_risk_panel.png` | `tables/comparator_rankings.csv` | net_CVaR₅ by model, faceted by contract. Shows downside exposure. |

#### Tier 2 Charts: Behavioral

| Chart | CSV Source | What It Shows |
|-------|-----------|---------------|
| `bid_behavior_panel.png` | `tables/behavior_by_contract.csv` | Multi-panel: bid_rate, make_rate, avg_bid, bid_std by model × contract. |
| `contract_mix_bars.png` | `tables/behavior_summary.csv` | Stacked bars showing each model's contract preference. |
| `bid_level_distribution.png` | `chart_data/bid_levels.csv` | Histogram/violin of bid levels per model. Extracted from JSONL → CSV by chart script. |

#### Tier 3 Charts: Offline Fit

| Chart | CSV Source | What It Shows |
|-------|-----------|---------------|
| `r2_by_contract.png` | `tables/model_performance.csv` | R² by model × contract. Grouped bar chart. |
| `mae_by_contract.png` | `tables/model_performance.csv` | MAE by model × contract. Same layout. |
| `pred_vs_actual.png` | `chart_data/predictions.csv` | Scatter of predicted vs actual net_points, faceted by contract. Extracted from model eval → CSV by chart script. |
| `residual_distribution.png` | `chart_data/residuals.csv` | Histogram of residuals by contract. Derived from `predictions.csv`. |
| `calibration_curve.png` | `chart_data/calibration_bins.csv` | Predicted vs actual binned means. Binned from `predictions.csv` by chart script. |

#### Model-Specific Charts

| Chart | CSV Source | What It Shows | Applicable Models |
|-------|-----------|---------------|-------------------|
| `feature_importance.png` | `chart_data/feature_importances.csv` | Top-N feature importances by contract. Extracted from GBT artifact → CSV by chart script. | `gbt_av` only |
| `selection_path.png` | `chart_data/selection_paths.csv` | OOF R² vs features added. Extracted from forward selection log → CSV by chart script. | `selected_ols_av`, `selected_two_stage_av` |

#### Data Sanity Charts (Phase 0-lite)

| Chart | CSV Source | What It Shows |
|-------|-----------|---------------|
| `outcome_distributions.png` | `chart_data/outcome_distributions.csv` | Histograms of net_points by contract type. Extracted from dataset → CSV by chart script. |
| `seat_balance.png` | `chart_data/seat_balance.csv` | Boxplot of outcomes by seat. Extracted from dataset → CSV by chart script. |

#### Cross-Rung Charts (Lineage-Level)

| Chart | CSV Source | What It Shows |
|-------|-----------|---------------|
| `cross_rung_progression.png` | `cross_rung_deltas.csv` | Line chart: pooled delta vs anchor by rung, one line per model. |
| `cross_rung_by_contract.png` | `cross_rung_deltas.csv` | Same as above, faceted suit/high/low. |

#### Interpretability Charts

| Chart | CSV Source | What It Shows | Applicable Models |
|-------|-----------|---------------|-------------------|
| `shap_summary.png` | `chart_data/shap_values.csv` | Beeswarm: feature importance with direction, per contract | `gbt_av` |
| `shap_dependence_top5.png` | `chart_data/shap_dependence.csv` | How top-5 features affect predictions across their range | `gbt_av` |
| `shap_interactions.png` | `chart_data/shap_interactions.csv` | Top-3 feature pair interactions | `gbt_av` |
| `selection_path.png` | `chart_data/selection_paths.csv` | OOF R² vs features added — diminishing returns curve | `selected_ols_av`, `selected_two_stage_av` |
| `decision_agreement.png` | `chart_data/decision_comparison.csv` | Agreement rate between model pairs by contract | All trained models |
| `disagreement_outcomes.png` | `chart_data/disagreement_outcomes.csv` | When models disagree, who has better actual outcomes? | All trained models |

#### Chart Count Summary

| Category | Count | Required At |
|----------|-------|-------------|
| Tier 1 (Decision) | 4 | Every rung |
| Tier 2 (Behavioral) | 3 | Every rung |
| Tier 3 (Offline Fit) | 5 | Every rung |
| Interpretability | 6 | Every rung (model-specific where noted) |
| Data sanity | 2 | Every rung |
| Cross-rung | 2 | Lineage-level (updated each rung) |
| **Total** | **22** | |

## 13. Evidence Contract

### 13.1 Source-of-Truth Rule

All canonical reports must be generated from machine-readable artifacts.

**Allowed evidence sources:**
- JSON manifests and artifacts
- CSV tables (in `tables/`)
- CSV chart-data files (in `chart_data/`)
- Committed report markdown generated from those artifacts

**Disallowed as canonical sources:**
- Notebook cell outputs
- Ad hoc shell output pasted into reports
- Manually typed metrics

### 13.2 CSV-First Principle

Every canonical table (§12) must be defined as a **CSV schema first**, then
rendered into markdown for reports. This prevents hand-maintained tables from
drifting out of sync with the underlying data.

**Workflow:**
1. Script generates CSV to `tables/<table_name>.csv`
2. Report generator reads CSV and renders markdown table
3. Human or agent reviews the rendered report

**Never edit a table directly in markdown.** If a value is wrong, fix the
generating script or the underlying data, then regenerate. This keeps the
CSV as the single source of truth and the markdown as a derived view.

### 13.3 Co-Located Evidence Rule

Every figure or table in a canonical report must have nearby source files.

- Each chart: image in `charts/`, source data in `chart_data/`
- Each table: rendered markdown in report, exact CSV in `tables/`

### 13.4 Claim Traceability Rule

Every major claim traces through:

```
claim → report section → table/chart ID → source CSV/JSON → run_id → seed
```

This mapping is encoded in `evidence_manifest.json`.

## 14. Evidence Manifest Schema

Each rung emits one manifest:

```json
{
  "schema_version": "arc_d_evidence_manifest_v1",
  "lineage_id": "arc_d_v2",
  "rung_id": "r0",
  "provenance_sha": "<git SHA at execution>",
  "lineage_plan": "plans/arc_d_v2/lineage_plan.md",
  "lineage_plan_sha": "<commit SHA of lineage plan>",
  "rung_plan": "plans/arc_d_v2/r0/plan.md",
  "rung_plan_sha": "<commit SHA of rung plan at execution start>",
  "anchor_model": "hybrid_r0_full",
  "anchor_artifact": "data/artifacts/arc_d/r0/hybrid_r0_full.json",
  "best_in_lineage": null,
  "roster": [
    {
      "name": "gbt_av",
      "class": "GBTActionValueBidder",
      "artifact_path": "data/runs/arc_d_v2/r0/artifacts/gbt_v1.json",
      "status": "retained",
      "excluded_reason": null
    }
  ],
  "context_bundle": {
    "rung": "r0",
    "features": ["bowers", "trump_count", "..."],
    "feature_count": 39
  },
  "seeds": [42, 123, 456],
  "mode": "FULL",
  "run_ids": ["arc_d_v2_r0_seed42_20260314T120000Z"],
  "artifacts": [
    {
      "name": "gbt_av",
      "path": "data/runs/arc_d_v2/r0/artifacts/gbt_v1.json",
      "schema_version": "action_value_gbt_v1",
      "generating_run_id": "..."
    }
  ],
  "tables": [
    {
      "id": "comparator_rankings",
      "csv_path": "tables/comparator_rankings.csv",
      "referenced_in": ["01_results.md"]
    }
  ],
  "charts": [
    {
      "id": "h2h_heatmap",
      "image_path": "charts/h2h_heatmap.png",
      "data_csv_path": "chart_data/h2h_delta_matrix.csv",
      "referenced_in": ["01_results.md"]
    }
  ]
}
```

The evidence manifest is **structural provenance only**. It records what was run,
what was produced, and where it lives. Interpretive findings (hypothesis outcomes,
key results, surprises) live in:
- `02_decision.md` (narrative)
- `tables/hypothesis_outcomes.csv` (structured)
- `design_decisions.md` (if a finding drives a decision)

This separation prevents the manifest from becoming a second sync surface with
the decision report.

## 15. Canonical Metrics Contract

Metrics are organized into tiers by purpose. Each tier feeds a specific table
and answers a specific question. Tiers must not be mixed in the same table.

### 15.1 Tier 1: Primary Decision Metrics (Ranking + Comparison)

Used to rank models and measure progress. These appear in the comparator
rankings table (§12.1) and H2H delta table (§12.2).

| Metric | Description | Faceting |
|--------|-------------|----------|
| `net_eppd` | Net expected points per deal (primary ranking metric) | Suit, High, Low, Pooled |
| `h2h_delta_vs_anchor` | net_eppd difference from anchor in direct H2H matchup | Suit, High, Low, Pooled |
| `comparator_net_eppd` | net_eppd in comparator mode (vs AlwaysPass sentinels) | Suit, High, Low, Pooled |
| `ci_low`, `ci_high` | Bootstrap 95% CI on delta | Per facet |
| `net_cvar_5` | CVaR₅ of net points (tail risk) | Suit, High, Low, Pooled |

`net_eppd` is the single primary metric. It captures bidding quality (right hands)
and bid calibration (right level) in one number, accounting for opponent scoring.

**Two delta sources, different questions:**
- **`h2h_delta_vs_anchor`**: Model and anchor play *against each other* on paired
  deals. Measures competitive performance. This is the primary delta for the
  cross-rung tracking table (§12.8) and H2H delta table (§12.2).
- **`comparator_net_eppd`**: Model plays against AlwaysPass sentinels independently.
  Measures absolute decision quality in isolation. This is the primary metric for
  the comparator rankings table (§12.1).

Both are reported at every rung. If they diverge (model is strong in comparator
but weak in H2H, or vice versa), that is a diagnostic finding worth investigating
in the rung decision report.

**Dropped:** `eppd` (non-net). The information `eppd` adds beyond `net_eppd` is
fully captured by `make_rate`. A model with high `eppd` but low `net_eppd` is
failing bids and giving the opponent set bonuses — `make_rate` shows this directly.
Keeping both creates confusion about which is primary.

### 15.2 Tier 2: Behavioral Metrics (Sanity + Diagnostic)

Used for sanity bounds (§11.1) and explaining *why* a model performs the way it
does. These appear in the behavior summary table (§12.4).

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| `bid_rate` | Fraction of hands where model bids | Too low → passive; too high → overbidding |
| `pass_rate` | Fraction of hands passed | Complement of bid_rate |
| `make_rate` | P(make \| bid) | Too low → bad hands; 100% → only certainties |
| `avg_bid_level` | Mean bid level when bidding | Calibration — central tendency |
| `bid_level_std` | Std dev of bid levels when bidding | Discrimination — near 0 means fixed-level bidding (bug) |
| `bid_level_min` | Lowest bid level made | Floor — does the model ever bid conservatively? |
| `bid_level_max` | Highest bid level made | Ceiling — does the model ever bid aggressively? |
| `contract_mix_suit` | Fraction of bids that are suit | Contract preference |
| `contract_mix_high` | Fraction of bids that are high | Contract preference |
| `contract_mix_low` | Fraction of bids that are low | Contract preference |
| `score_std` | Std dev of per-deal scores | Volatility |
| `redeal_rate` | Fraction of redeals | Framework health |

These metrics do not rank models. A model with 30% pass rate is not inherently
better or worse than one with 5% — the ranking comes from `net_eppd`.

The `bid_level_std` metric is particularly diagnostic. R1.5 OLS AV had
bid_level_std ≈ 0 (every bid at level 4) while GBT had bid_level_std ≈ 1.2
(bids ranging 3–8). Near-zero std indicates the model is not using hand
information to modulate bid level — a capacity failure, not a strategy choice.

### 15.3 Tier 3: Offline Fit Metrics (Training Layer)

Used to evaluate model fit to training data. These appear in the model
performance table (§12.3). **Never use offline metrics to rank gameplay quality.**

| Metric | Description | Faceting |
|--------|-------------|----------|
| `R²` | Coefficient of determination | Per contract (suit, high, low) |
| `MAE` | Mean absolute error | Per contract |
| `n` | Training sample count | Per contract |

R1.5 proved these can diverge dramatically from gameplay — OLS R² improved +0.14
with multi-rollout labels but H2H gameplay got *worse*. Offline metrics are
informational context, never decisive.

### 15.4 Mandatory Faceting

All three tiers must be faceted by contract type: `suit`, `high`, `low`, `pooled`.

This is non-negotiable. The v1 lineage's most important finding (suit regression)
was invisible in pooled metrics. Contract-type faceting is where the signal lives.

**Tier 1:** All metrics faceted (net_eppd, delta, CIs, net_cvar_5).

**Tier 2:** Key behavioral metrics faceted; remaining reported pooled only.

| Metric | Faceted? | Rationale |
|--------|----------|-----------|
| `bid_rate` | **Yes** | Model may bid suit but pass high — critical |
| `make_rate` | **Yes** | Suit make_rate drove the R1.5 regression finding |
| `avg_bid_level` | **Yes** | Bid calibration varies by contract |
| `bid_level_std` | **Yes** | Fixed-bid pathology may be contract-specific |
| `bid_level_min/max` | **Yes** | Range may differ by contract |
| `pass_rate` | Pooled | Complement of bid_rate, faceting is redundant |
| `contract_mix_*` | Pooled | These ARE the faceting (suit/high/low fractions) |
| `score_std` | Pooled | Outcome volatility is a game-level property |
| `redeal_rate` | Pooled | Framework health, not contract-specific |

**Tier 3:** Per-contract by definition (R², MAE, n are always per contract).

**Table layout:** The behavior summary table (§12.4) reports pooled values.
A companion `behavior_by_contract.csv` reports the faceted Tier 2 metrics.
Both are required at every rung.

### 15.5 Cross-Rung Tracking

The cross-rung delta table (§12.8) tracks Tier 1 + key Tier 2 metrics
longitudinally. One row per (model, rung), accumulated as rungs complete:

| Tracked Cross-Rung | Tier | Purpose |
|--------------------|------|---------|
| `delta_vs_anchor` (all facets) | 1 | Did this model improve with new context? |
| `bid_rate` | 2 | Did bidding behavior change? |
| `make_rate` | 2 | Did accuracy change? |
| `net_cvar_5` | 1 | Did tail risk change? |

This table is the primary tool for answering "how did model X respond to
new context across rungs?"

## 16. Exploratory Work Contract

### 16.1 Location

```text
docs/04_reports/arc_d_v2/<rung>/exploratory/
```

### 16.2 Registry

Each rung maintains `exploratory/registry.md`:

| ID | Hypothesis | Why Exploratory | Run/Command | Result | Changed Canonical? |
|----|-----------|----------------|-------------|--------|-------------------|

### 16.3 Contamination Rule

Exploratory work becomes canonical evidence only when:
1. The output is regenerated through canonical scripts
2. Tables/charts are emitted into canonical locations
3. The evidence manifest is updated

## 17. Governance

### 17.1 Plan Governance

Two levels of governing plans:
- `plans/arc_d_v2/lineage_plan.md` — the stable lineage contract (roster,
  metrics, evidence architecture). Changes via amendment only (§20).
- `plans/arc_d_v2/<rung>/plan.md` — rung-specific hypotheses and execution
  details. Created at Step 0, frozen at Step 1.

Git tracks revision history. No separate snapshot files.
The evidence manifest records BOTH SHAs:
- `lineage_plan_sha` — the lineage contract version in effect
- `rung_plan_sha` — the rung plan version that governed execution

Both are set when Step 1 begins and never changed for that rung.

### 17.2 Design Decisions

Key decisions are recorded in `design_decisions.md` within the rung directory.
Each entry:

```markdown
### DD-<N>: <Title>
**Date:** YYYY-MM-DD
**Decision:** <one-line summary>
**Rationale:** <why, citing evidence or constraints>
**Alternatives considered:** <brief>
```

### 17.3 Q&A Log

Each rung maintains a `qa_log.md` for open questions and resolved discussions.

Each entry:

```markdown
### Q-<N>: <Question>
**Date:** YYYY-MM-DD
**Status:** open | resolved | deferred
**Answer:** <if resolved>
**Linked decision:** DD-<N> (if applicable)
**Linked finding:** F-<N> (if applicable)
```

**Why separate from design decisions:** Design decisions record conclusions.
Q&A logs preserve the reasoning thread — why a decision changed, what
alternatives were debated, what evidence shifted thinking. Without this,
the "why" behind a design decision is lost to conversation history.

### 17.4 Notebook Governance

Notebooks remain allowed for exploration only.

- Notebooks may NOT be canonical sources for report metrics
- Notebooks may reference canonical CSV/JSON artifacts
- If notebook findings matter, they must be promoted into canonical scripts
  and regenerated through the runbook

### 17.5 Agent Operating Protocol

This lineage follows the **repo-wide governing plan framework** defined in
`docs/02_agent/AGENTS.md` section 12 and the **Agent Execution Protocol**
in `CLAUDE.md`. This section documents lineage-specific specializations only.

For the general framework (plan hierarchy, sub-plan contract, checkpoint
format, session handoff rules, amendment process), see those documents.

#### 17.5.1 Discovery (Lineage-Specific)

The repo-wide discovery order (CLAUDE.md "Agent Execution Protocol") applies.
For this lineage specifically:

1. `CLAUDE.md` "Active Governing Plans" table points to `plans/arc_d_v2/lineage_plan.md`
2. The lineage plan's §9 (Runbook) defines the step sequence
3. Each rung's `plans/arc_d_v2/<rung>/checkpoints.md` tracks step progress
4. Each rung's `plans/arc_d_v2/<rung>/plan.md` has hypotheses and rung-specific details
5. `plans/arc_d_v2/sub_plan_registry.md` indexes all sub-plans across rungs

#### 17.5.2 Execution Boundaries (Lineage-Specific)

Each runbook step (§9) has three components that define execution boundaries:

- **Commands:** Exact CLI commands to run. Execute these, not variations.
- **Validates:** Conditions that must be true before proceeding. If validation
  fails, do NOT proceed — log the failure and mark the step `BLOCKED`.
- **Error recovery:** What to do when something goes wrong. Follow this guidance
  before improvising.

**Scope rules:**
- Agents execute the runbook. They do NOT modify the lineage plan.
- If an agent believes the lineage plan is wrong, they log the concern in
  `qa_log.md` as an `open` question and continue with the plan as written.
  The human reviews `qa_log.md` during the Step 8 decision review.
- Agents may make small tactical decisions (e.g., "retry with a different
  random state after OOM") without a sub-plan. Log these in `checkpoints.md`.

#### 17.5.3 Sub-Plans (Lineage-Specific)

Sub-plans follow the repo-wide contract (`docs/02_agent/AGENTS.md` section 12.3).
Use the template at `plans/_templates/sub_plan.md`.

**Where sub-plans live for this lineage:**
```text
plans/arc_d_v2/<rung>/sub/
  <YYYY-MM-DD>_<slug>.md
```

**Sub-plan registry:** `plans/arc_d_v2/sub_plan_registry.md`

**Examples of sub-plan-worthy work:**
- Phase 0 infrastructure: "Add `--selection forward` to `train_action_value.py`"
- Phase 0 infrastructure: "Create `generate_rung_tables.py`"
- Rung execution: "Investigate surprise H3 — OLS suit delta unexpectedly positive"

**Examples that do NOT need a sub-plan:**
- Running a training command from the runbook
- Generating charts from existing CSVs
- Filling in `checkpoints.md` or `hypothesis_outcomes.csv`

#### 17.5.4 Issue Flagging

Agents must flag issues rather than silently working around them.

**Issue severity:**

| Severity | Action | Where to Log |
|----------|--------|-------------|
| **BLOCKER** | Stop current step. Mark step `BLOCKED` in checkpoints. | `checkpoints.md` + `qa_log.md` |
| **WARNING** | Continue but record. May affect interpretation. | `qa_log.md` |
| **INFO** | Note for future reference. | `checkpoints.md` Notes column |

**Common issue patterns:**

| Situation | Severity | What to Do |
|-----------|----------|-----------|
| Validation fails after a runbook step | BLOCKER | Do not proceed. Log exact error. Check error recovery guidance. |
| Training fails for one model | WARNING | Log failure, proceed with remaining models, record exclusion in manifest. |
| Metrics outside expected hypothesis bounds | WARNING | Log as potential surprise, proceed to Step 8 for analysis. |
| Script produces unexpected output format | BLOCKER | Do not hand-edit output. Log the issue, check if script needs fixing. |
| Plan seems wrong or outdated | WARNING | Log in `qa_log.md` as `open`. Execute plan as written. Human reviews. |
| Unclear which step to execute next | BLOCKER | Read `checkpoints.md`. If still unclear, log question and wait. |

**Anti-patterns to avoid:**
- Silently skipping a failed validation and proceeding to the next step
- Hand-editing a CSV or report to "fix" a value instead of fixing the source
- Modifying the lineage plan to match what actually happened
- Creating ad hoc scripts outside the script ownership map (§19)
- Running exploratory analysis in the canonical pipeline without logging it

#### 17.5.5 Lineage Plan Immutability

**The lineage plan (`plans/arc_d_v2/lineage_plan.md`) is immutable during execution.**

This is an instance of the repo-wide amendment policy (AGENTS.md section 12.6).
For this lineage specifically:

- **Rung-level adjustments** (e.g., "drop legacy baselines at R1"): Use the lineage
  amendment process (§20). Log in `plans/arc_d_v2/amendments.md`.
- **Step-level clarifications** (e.g., "the --output-dir flag should be X not Y"):
  Log in `qa_log.md`. If confirmed, a human or designated agent applies a
  targeted fix to the lineage plan with a commit message referencing the Q&A entry.
- **Fundamental design changes** (e.g., "add a new model family"): Requires
  human approval. Proposed via `qa_log.md` -> `design_decisions.md` -> amendment.

## 18. Run Naming Contract

All run IDs follow this pattern:

```
arc_d_v2_<rung>_<mode>_seed<N>_<ISO8601_timestamp>
```

Examples:
- `arc_d_v2_r0_quick_seed42_20260314T120000Z`
- `arc_d_v2_r1_full_seed123_20260320T090000Z`

Rules:
- Timestamps are UTC ISO 8601 (no colons in filename: use `T` and `Z`)
- Mode is lowercase: `smoke`, `quick`, `full`
- Run IDs appear in metadata, manifest, and directory names
- Never reuse a run ID — if re-running, generate a new timestamp

## 19. Script Ownership Map

Which script produces which artifact:

| Script | Inputs | Outputs | Report Section |
|--------|--------|---------|----------------|
| `generate_action_value_dataset.py` | Seed, config, context level | `action_value.parquet` | — |
| `train_action_value.py` | Dataset, model class, seed | Model artifact JSON | 01_results §Offline |
| `run_arc_d_h2h_battery.py` | Roster JSON, seed, mode | H2H battery JSON, per-matchup runs | 01_results §H2H |
| `extract_comparator_cis.py` | Battery JSON, JSONL logs | Comparator CIs JSON | 01_results §Rankings |
| `run_auction_comparator.py` | Roster, seed, mode | Per-bidder comparator runs | 01_results §Rankings |
| `generate_rung_tables.py` | Run artifacts, manifests | CSVs in `tables/` | All sections |
| `generate_rung_charts.py` | CSVs from `tables/` + `chart_data/` | PNGs in `charts/` | All sections |
| `generate_interpretability.py` | Model artifacts, eval predictions | CSVs in `chart_data/` (SHAP, selection paths, decisions) | 01_results §4–§5 |
| `generate_rung_report.py` | `tables/*.csv`, `charts/*.png` | `01_results.md` | — |
| `generate_evidence_manifest.py` | All of the above | `evidence_manifest.json`, `00_manifest.md` | — |

**Note:** `generate_rung_tables.py`, `generate_interpretability.py`,
`generate_rung_report.py`, and `generate_evidence_manifest.py` do not currently
exist and must be created as part of the infrastructure work (§23 Phase 0).

## 20. Lineage Amendment Process

Amendments to the lineage contract (roster, metrics, rung definitions) may
only occur at rung boundaries.

### 20.1 Amendment Template

```markdown
## Lineage Amendment LA-<N>

**Date:** YYYY-MM-DD
**Type:** roster_addition | roster_removal | metric_addition | rung_redefinition
**Effective from:** Rung <ID>
**Change:** <description>
**Rationale:** <why this change is necessary>
**Impact on comparability:** <what cross-rung comparisons are affected>
**Approved by:** <human reviewer>
```

### 20.2 Rules

- Amendments take effect at the START of the next rung, never mid-rung.
- Roster additions are allowed; roster removals should be rare (prefer `excluded`).
- Metric additions are allowed; metric removals require strong justification.
- All amendments are logged in `plans/arc_d_v2/amendments.md`.

## 21. Plans Directory Restructuring

The current `plans/` directory has accumulated 96 files across three locations
with no clear separation between active and historical material. An agent
starting a new rung could mistakenly follow `r1_5_training_plan.md` or
`r1_5_forward_decision_tree.md` from the root — both are v1-lineage artifacts
that no longer govern execution.

### 21.1 Current State

```text
plans/
  AGENTS.md                              # Workflow docs (still relevant)
  r1_5_forward_decision_tree.md          # v1 lineage — STALE
  r1_5_training_plan.md                  # v1 lineage — STALE
  r1_follow_ups.md                       # v1 lineage — STALE
  r2_follow_ups.md                       # v1 lineage — STALE
  archive/                               # 66 files (pre-R1.5 era, already archived)
  sessions/                              # 25 files (R1.5-era session plans)
    2026-03-13_canonical-lineage-rebuild-proposal.md   # v1 of this plan — SUPERSEDED
    2026-03-13_r1-6-partner-semantics.md               # v1 lineage — STALE
    ...
    TEMPLATE.md
```

### 21.2 Target State

```text
plans/
  _templates/                            # Repo-wide plan templates
    governing_plan.md                    # Template for new initiatives
    sub_plan.md                          # Template for sub-plans
    sub_plan_registry.md                 # Template for sub-plan registries
    checkpoints.md                       # Template for checkpoint files
  AGENTS.md                              # Kept — review guidelines for plan files
  sessions/                              # Retained for non-governed session plans
    TEMPLATE.md                          # Session plan template (standalone work)
  arc_d_v2/                              # NEW — v2 lineage (governed initiative)
    lineage_plan.md                      # Governing plan (this document)
    amendments.md                        # Lineage amendment log
    sub_plan_registry.md                 # Index of all sub-plans across rungs
    r0/
      plan.md                            # R0* rung plan (created at rung start)
      checkpoints.md                     # Agent state file
      sub/                               # Sub-plans for R0* implementation work
    r1/
      plan.md
      checkpoints.md
      sub/
  archive/
    v1_root/                             # Moved from plans/ root
      r1_5_forward_decision_tree.md
      r1_5_training_plan.md
      r1_follow_ups.md
      r2_follow_ups.md
    v1_sessions/                         # Moved from plans/sessions/
      2026-03-06_*.md
      2026-03-08_*.md
      ...
      2026-03-13_canonical-lineage-rebuild-proposal.md
      2026-03-13_r1-6-partner-semantics.md
    pre_v1/                              # Existing archive/ contents, reorganized
      BIDDING_DEVELOPMENT_PLAN.md
      MASTER_PLAN.md
      ...  (66 existing files)
```

### 21.3 Migration Rules

1. **Move, don't delete.** All v1 plans are historical — they document the
   reasoning that led to the v2 lineage. Deleting them loses context.
2. **Root must be clean.** After migration, `plans/` root contains only
   `_templates/`, `AGENTS.md`, `sessions/`, and initiative directories
   (e.g., `arc_d_v2/`). No loose plan files.
3. **`arc_d_v2/lineage_plan.md` is the single governing document.** This is
   the canonical copy of this plan, moved from its drafting location in
   `plans/sessions/`. The evidence manifest's `governing_plan` field points here.
   CLAUDE.md "Active Governing Plans" table points here for agent discovery.
4. **Session plans remain available for non-governed work.** `plans/sessions/`
   is retained with its template for standalone bugfixes and small features
   that do not belong to a governed initiative. Work belonging to Arc D v2
   uses the governed structure (`plans/arc_d_v2/<rung>/sub/`), not sessions.
5. **`AGENTS.md` stays at `plans/` root.** It contains review guidelines for
   plan files. The repo-wide governing plan framework is defined in
   `docs/02_agent/AGENTS.md` section 12.
6. **Templates live in `plans/_templates/`.** These are repo-wide templates
   for governing plans, sub-plans, registries, and checkpoints. They are not
   specific to any initiative.

### 21.4 Impact on CLAUDE.md and Memory

After migration, verify:
- `CLAUDE.md` "Active Governing Plans" table points to `plans/arc_d_v2/lineage_plan.md`
- `CLAUDE.md` "Agent Execution Protocol" section is present (discovery, execution loop,
  handoff instructions)
- `MEMORY.md` references to plan file locations are updated
- Any `.claude/rules/` that reference `plans/sessions/` conventions are updated
- `docs/02_agent/AGENTS.md` section 12 (Governing Plan Framework) is present

## 22. Testing Strategy

### 22.1 Infrastructure Changes (Phase 0)

| Change | Test Approach |
|--------|---------------|
| NEW `generate_rung_tables.py` | Unit tests: verify CSV output schema matches §12 table templates; verify correct metric values against known fixture data |
| NEW `generate_evidence_manifest.py` | Unit tests: verify JSON schema matches §14; verify all required fields populated |
| NEW `--feature-set constrained` in `train_action_value.py` | Unit test: verify correct features selected per contract; integration test: SMOKE training run succeeds |
| NEW `generate_rung_report.py` | Unit tests: verify required sections render from canonical CSV inputs; integration test: `01_results.md` regenerates deterministically |
| ADAPT `generate_rung_charts.py` | Run existing tests (if any); manual visual check of multi-model chart |

### 22.2 Per-Rung Validation

During rung execution, use the Tier 1 / Tier 2 testing policy:

- **Tier 1 (during implementation):** Run targeted tests for any script touched
- **Tier 2 (before PR):** `make check-quiet` for each infrastructure PR

Per-rung data validation is built into the runbook (each step has a **Validates**
block). These are runtime checks, not unit tests.

### 22.3 Pre-PR Checklist

Before any PR in this lineage:
```bash
make check-quiet         # Full validation suite
uv run ruff check --fix  # Linter
uv run ruff format       # Formatter
```

## 23. Implementation Plan

### Phase 0: Infrastructure (before any rung execution)

1. **Restructure plans directory (§21)**
   - Move v1 root plans (`r1_5_*.md`, `r1_follow_ups.md`, `r2_follow_ups.md`) -> `plans/archive/v1_root/`
   - Move v1 session plans (`plans/sessions/*.md` except TEMPLATE.md) -> `plans/archive/v1_sessions/`
   - Move existing `plans/archive/` contents -> `plans/archive/pre_v1/`
   - Keep `plans/sessions/TEMPLATE.md` in place (for non-governed session plans)
   - Copy this plan -> `plans/arc_d_v2/lineage_plan.md` (canonical location)
   - Create `plans/arc_d_v2/amendments.md`
   - Create `plans/arc_d_v2/sub_plan_registry.md` (from `plans/_templates/sub_plan_registry.md`)
   - Verify `CLAUDE.md` "Active Governing Plans" table points to `plans/arc_d_v2/lineage_plan.md`
     (required for agent discovery per §17.5.1 and CLAUDE.md Agent Execution Protocol)
   - Update MEMORY.md references to plan file locations

2. **Create report directory scaffolding**
   - `docs/04_reports/arc_d_v2/`

3. **Add `constrained` feature set to `train_action_value.py`**
   - Add `"constrained"` key to `FEATURE_SETS` dict (~10 lines)
   - Maps to per-contract locked features (§5.1): suit=3, high=2, low=2
   - Add unit test verifying correct feature selection

4. **Add `--selection forward` flag to `train_action_value.py`**
   - Wire `forward_select` from `src/bid_euchre/models/feature_selection.py`
     into the AV training path for both `ols` and `two-stage` model classes
   - When `--selection forward` + `--model-class ols`: run forward selection with
     GroupKFold by hand_id per contract family
   - When `--selection forward` + `--model-class two-stage`: run forward selection
     separately for each sub-model (P(make) logistic, E[pts|make] OLS, E[pts|set] OLS)
   - When `--selection none` (default): use all features in `--feature-set` as-is
   - Not applicable to `--model-class gbt` (GBT handles feature selection internally)
   - Add unit tests verifying forward selection produces a subset for both OLS and
     two-stage paths
   - The forward selection machinery already exists — this is plumbing, not research

5. **Create/adapt scripts**
   - `generate_rung_tables.py` — NEW: reads run artifacts, emits standardized CSVs
     matching §12 table templates
   - `generate_evidence_manifest.py` — NEW: assembles manifest from run metadata
     matching §14 schema
   - `generate_interpretability.py` — NEW: SHAP analysis, selection path logging,
     decision comparison. Requires `shap` package (`uv add shap`).
   - `generate_rung_report.py` — NEW: renders `01_results.md` from canonical CSVs + PNGs
   - Adapt `generate_rung_charts.py` — generalize to multi-model + add interpretability charts

6. **Create roster and config templates**
   - H2H roster JSON: 6 primary + 2 legacy + anchor = 9 models, compatible with
     `run_arc_d_h2h_battery.py --roster` format
   - Comparator YAML config: all models as `bidding_policies`, compatible with
     `run_auction_comparator.py --config` format (anchor added via `--olsa-artifact`)

7. **Write tests for new scripts** (see §22.1)

8. **Validate full pipeline with SMOKE mode**
   - Run Steps 1–7 with `--mode SMOKE` (50 deals)
   - Verify all CSVs, PNGs, and manifest generated correctly
   - This is the "does the machinery work?" gate before real experiments

### Phase 0 Dependency Policy

**Phase 0 must complete before any rung execution begins.** Specifically:

- `--feature-set constrained` and `--selection forward` must be implemented
  and tested before R0* Step 2 (training).
- If either is missing when R0* begins, the affected models (`constrained_ols_av`,
  `selected_ols_av`, `selected_two_stage_av`) are **blocked, not auto-excluded**.
  The rung does not proceed without them — they are core roster members, not
  optional additions.
- The SMOKE validation (item 8 above) must exercise all 6 primary models.
  If any model fails SMOKE, Phase 0 is not complete.

This is a hard gate. Skipping Phase 0 and running R0* with a partial roster
defeats the multi-model comparison design.

**Phase 0 Readiness Checklist:**

| # | Item | Verification Command | Status |
|---|------|---------------------|--------|
| 1 | Plans directory restructured | `ls plans/arc_d_v2/lineage_plan.md` exists | |
| 2 | Report directory scaffolding created | `ls docs/04_reports/arc_d_v2/` exists | |
| 3 | `--feature-set constrained` implemented | `grep 'constrained' scripts/internal/train_action_value.py` finds FEATURE_SETS entry | |
| 4 | `--selection forward` implemented | `grep 'selection' scripts/internal/train_action_value.py` finds argparse flag | |
| 5 | New scripts created | All of: `generate_rung_tables.py`, `generate_rung_charts.py` (adapted), `generate_interpretability.py`, `generate_rung_report.py`, `generate_evidence_manifest.py` exist in `scripts/internal/` | |
| 6 | Roster JSON template created | Roster JSON with 9 models (6 primary + 2 legacy + anchor) exists | |
| 7 | Comparator YAML config template created | Config with 6 primary models as bidding_policies exists | |
| 8 | Tests pass for new scripts | `uv run python -m pytest tests/unit/test_<new_scripts>.py` passes | |
| 9 | SMOKE pipeline validated | Full Steps 1-7 completed with --mode SMOKE, all CSVs/PNGs/manifest generated | |

An agent must verify all 9 items before marking Phase 0 complete and proceeding to Phase 1.

### QUICK Sufficiency Rule

Proceed from QUICK to FULL when:
- No primary model is `BLOCKED`
- All required canonical tables can be generated
- At least one Tier 1 hypothesis is supported directionally (CI excludes zero
  or bound is met)
- No primary hypothesis result is within one CI-width of its surprise threshold
- No data sanity check fails

If these conditions are not met, outcome is `INVESTIGATE` or `PAUSE`, not
automatic FULL.

### Rerun / Supersession Procedure

If a rung must be rerun (e.g., data issue discovered, script bug):
1. Create a new timestamped run_id
2. Preserve prior artifacts in place
3. Mark prior manifest/artifacts `superseded` or `quarantined`
4. Record the supersession link in the new manifest
5. Regenerate canonical reports from the replacement run only

### Phase 1: R0* Execution

1. Execute runbook Steps 0–9 at QUICK scale (2,500 deals, seed=42)
2. Review results against QUICK sufficiency rule (above)
3. If sufficient, proceed to FULL
4. Execute FULL (50,000 deals × 3 seeds: 42, 123, 456)
5. Generate canonical reports

### Phase 2: R1 Execution (Partner Context)

1. Implement v2 partner feature extraction (`extract_partner_features_v2()`)
   in `auction_context.py` — 6 features as defined in §6.1:
   `partner_level_same_suit`, `partner_level_same_color`, `partner_level_off_color`,
   `partner_level_high`, `partner_level_low`, `partner_passed`
2. Update `--feature-set full` for R1: `r0` → `full` (39 hand + 6 partner = 45 features)
3. Regenerate training data with v8 schema (partner features in dataset)
4. Extend constrained-arm locked feature mapping: add 6 partner features
5. Add unit tests for partner feature extraction + schema-count validation
6. Continuation artifact remains fixed: frozen anchor `hybrid_r0_full.json` (§4.1)
7. Run SMOKE before QUICK
8. Execute runbook at QUICK, then FULL
9. Update `cross_rung_deltas.csv` and cross-rung progression charts
10. Compare all models' response to partner information — this is the clean
    ablation (same continuation policy, same objective, only context changes)

### Phase 3: R2 Execution (Opponent Context)

1. Implement opponent context extraction (`extract_opponent_features()`)
   in `auction_context.py` — 12 features as defined in §6.2:
   6 per opponent × 2 (left/right split)
2. Update `--feature-set full` for R2: 45 → 57 features (v9 schema)
3. Regenerate training data with v9 schema
4. Extend constrained-arm locked feature mapping: add 12 opponent features
5. Add unit tests for opponent feature extraction + schema-count validation
6. Continuation artifact remains fixed: frozen anchor `hybrid_r0_full.json` (§4.1)
7. Run SMOKE before QUICK
8. Execute runbook at QUICK, then FULL
9. Update `cross_rung_deltas.csv` and cross-rung progression charts

### Phase 4: R3 Execution (Moon/Loner Action Space Expansion)

R3 is split into two sub-phases because it requires engine changes before
model evaluation can begin.

**Phase 4A: Engine Expansion (multi-PR engineering effort)**
1. Implement moon/loner bid types in `enumerate_legal_actions()`
2. Implement overcall hierarchy + dealer takeover in auction resolution
3. Implement card exchange phase (new game phase between auction and trick play)
4. Implement 3-player trick play for loner (partner sits out)
5. Implement fixed scoring (±20 moon, ±40 loner) + defending team tricks
6. Update `hand_end` logging for new bid types and exchange details
7. Implement card exchange heuristic policies (mooner: 2 worst, partner: 2 best)
8. Update dataset generator for moon/loner counterfactuals
9. Add `is_moon`, `is_loner` action features
10. Unit tests for all new mechanics
11. SMOKE validation: run full pipeline with moon/loner actions enabled

Each item above is a sub-plan in `plans/arc_d_v2/r3/sub/`.

**Phase 4B: Standard rung evaluation**
1. Execute runbook Steps 0–9 with expanded action space
2. All 6 primary models train on same data (now including moon/loner actions)
3. H2H and comparator batteries include moon/loner bidding
4. SHAP analysis specifically examines: do models learn when to moon vs loner?
5. Decision comparison: how often does GBT choose moon where OLS chooses regular?

### Phase 5+: Subsequent Rungs

Any rung after R3 must define:
- Exact feature contract and schema version
- Constrained-arm locked feature additions
- Script changes required
- Test additions
- Canonical report changes, if any

R4 (card inference) follows standard feature-rung execution. Design deferred
until R2/R3 results inform which inference features are worth implementing.

## 24. Risks

### 24.1 Over-Process Risk

**Risk:** Too much governance scaffolding before answering live research questions.
**Mitigation:** Lock only the minimum contracts now (directory layout, report set,
metric set, manifest schema, roster). Governance can be refined after R0*.

### 24.2 Compute Budget Risk

**Risk:** 5 models × N rungs × 3 seeds × 50K deals × 36 matchups = significant compute.
**Mitigation:** Use QUICK (1 seed, 2,500 deals) for screening. Only FULL for
publication-grade evidence. SMOKE for script validation.

### 24.3 Script Drift Risk

**Risk:** New scripts created ad hoc that bypass the ownership map.
**Mitigation:** Script ownership map (§19) is the single source of truth.
New scripts require an amendment or explicit addition to the map.

### 24.4 Scope Creep Risk

**Risk:** Adding models, metrics, or analyses mid-rung breaks comparability.
**Mitigation:** Amendment process (§20) enforces rung-boundary changes only.

### 24.5 R0* Definition Risk

**Risk:** "Hand-only with AV framework" may not be directly comparable to
legacy R0 (bidless, tricks_won). The anchor comparison may conflate
objective (tricks_won → net_points) and context (partner features removed).
**Mitigation:** This is acknowledged and accepted. The anchor comparison measures
"total progress since R0," not isolated effects. Within-lineage comparisons
(R0* vs R1 vs R2) provide the controlled ablation.

## 25. Success Criteria

### 25.1 Infrastructure Criteria (Is the System Working?)

1. A rung summary can be audited without opening a notebook
2. Every chart traces to a nearby source CSV
3. Every finding traces through the evidence manifest to a run_id
4. The same report structure exists across all rungs
5. An autonomous agent can execute a rung from the runbook alone
6. Plans and Q&A are rung-scoped and easy to inspect
7. Cross-rung model comparison is meaningful (same tables, same metrics)

### 25.2 Research Criteria (Did We Learn Something?)

8. R0* establishes clear model rankings with non-overlapping CIs for at least
   the top and bottom models
9. At least one trained model demonstrates statistically significant improvement
   over the frozen anchor (CI excludes zero on pooled h2h_delta_vs_anchor)
10. The cross-rung delta table shows whether context features help, and for
    which model families — not just pooled, but faceted by contract type
11. The OLS trio (constrained/selected/full) resolves whether feature selection
    matters for linear models on action-value data
12. GBT feature importances at R1/R2 show whether new context features
    (partner suit-relative channels, opponent channels) are actually used
    or ignored by the tree splits

## Outcome

_To be filled after implementation._
