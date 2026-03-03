# Comparator Rankings Report — Refactor Plan

> **Goal:** Refactor `docs/04_reports/r0/comparator_rankings.md` to be
> self-contained, convention-compliant, and empirically grounded.
>
> **Scope:** Report refactor + supporting notebook. No code changes, no
> experiment runs — this plan assumes all prerequisites are complete.
>
> **Source notes:** `plans/comparator_rankings_review_notes.md` (12 notes)
>
> **Output:** Refactored report + new notebook `45_comparator_deep_dive.py`

---

## Prerequisites (assumed complete)

Before executing this plan, the following must be done:

1. **Bidder fixes merged** — ModeloEspecifico ceiling removed (`<= 6` → `<= 10`),
   OLSa-family floor lowered (`3 <=` → `1 <=`), RanktheTank thresholds
   recalibrated from empirical data. See `plans/comparator_experiment_redesign.md`
   Fixes A, B, C.

2. **Comparator battery re-run** — Single-seat mode (v3) as primary. 10k+ deals
   per bidder, seed=42, 10k bootstrap resamples. Artifact at
   data/artifacts/arc_d/r0/comparator_cis_r0_v3.json.

3. **4-way battery available** — Either re-run for consistency or use existing v2
   data as the auction-pressure sensitivity panel.

4. **Raw JSONL logs available** — Per-deal game logs in `data/runs/` for each
   bidder's single-seat run. Required for the notebook's per-deal and
   per-contract-type analysis.

---

## PR Strategy

**Single PR.** The report refactor and notebook are one concept ("comparator
rankings v3 report"). The notebook exists solely to support the report with
charts and faceted data. Splitting them would leave the report with dangling
cross-references.

**PR title:** `docs: refactor comparator rankings report (v3, single-seat)`

---

## Target Report Structure

The refactored report has 9 sections. This is the authoritative specification —
each section below includes what it covers, what changed from the current
report, and acceptance criteria.

---

### Header

```markdown
# R0 Comparator Rankings (v3, Single-Seat, 7 Bidders)

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** <date of v3 battery run>
**Methodology:** Single-seat evaluation · <N> deals per bidder · seed=42 · 10,000 bootstrap resamples
```

**Changes:** Update version to v3, add "Single-Seat" to title, update
methodology one-liner with actual deal count.

---

### §1. Summary

> **Status:** NEW. The current report has no introductory section.

**Purpose:** Make the report self-contained. A reader unfamiliar with Arc D
should understand what this is, why it was run, and what it tells us before
hitting any numbers.

**Content (5 paragraphs, ~15 lines total):**

1. **What this is.** A self-play benchmark where each bidder evaluates random
   hands uncontested (`current_high_bid=0`) and plays declared contracts with
   GluttonStrategy handling all card play. Measures intrinsic bidding quality
   in isolation.

2. **Why it's run this way.** Provides an absolute benchmark ("is this model
   any good?") without requiring O(n²) pairwise matchups. Enables rung-over-rung
   progress tracking against a fixed reference point.

3. **What it tells us.** Ranks 7 bidders on net_eppd. State the top-line result:
   which bidder leads, how many tiers emerge, what the dominant differentiator
   is (selective bidding vs always-bid).

4. **How to use it.** Baseline for rung-over-rung tracking. Self-play rankings
   can diverge from competitive ordering — use H2H battery for promotion
   decisions. Cross-reference `h2h_battery_analysis.md`.

5. **Arc context.** Where this fits in the R0 evaluation stack (alongside H2H
   battery, C33 ablation, and threshold calibration).

**Acceptance criteria:**
- [ ] A reader with no prior context can understand the report's purpose
- [ ] Cross-references H2H battery and C33 ablation reports
- [ ] No numbers — this is framing, not results

---

### §2. Methodology

> **Status:** MOVED from current §5. Expanded for v3 single-seat design.

**Purpose:** Reader understands the experimental design before seeing numbers.

**Subsections:**

#### §2.1 Experimental Design

- Single-seat evaluation (v3): one random seat per deal, `current_high_bid=0`,
  bid-or-pass. GluttonStrategy handles all card play for all 4 seats.
- Parameters: deal count, seed, bootstrap config.
- Key distinction from H2H: no contested auction, no opponent bidding strategy.
  This measures intrinsic policy quality, not competitive performance.

#### §2.2 Metric Definitions

- **net_eppd:** `sum(declaring_pts − defending_pts) / total_deals`. Pass deals
  contribute 0 to numerator, 1 to denominator. Positive = the bidder picks
  profitable contracts on average.
- **eppd:** `sum(declaring_pts) / total_deals`. Always positive if any bids are
  made; ignores the opponent's points.
- **bid_rate:** `hands_with_bids / total_deals`. In single-seat mode, this is
  the per-hand selectivity rate — the fraction of random hands the policy
  considers worth bidding on.
- **make_rate:** `contracts_made / contracts_bid`. Fraction of bid contracts
  where `tricks_won >= bid_n`.
- **CVaR-5%:** Mean of the worst 5% of per-hand outcomes (by `bidder_team_points`).
  A tail-risk metric: lower (more negative) = worse downside.

#### §2.3 Version History

> Merged from current §5a + §5b. Single subsection.

- **v1** (5 bidders, 4-way auction): Initial battery.
  `hybrid_olsa` referred to OLSa_Full promotional arm.
- **v2** (7 bidders, 4-way auction): Added `olsa_full` and `olsa` as separate
  entries. `hybrid_olsa` redefined to constrained arm with Gaussian CDF wrapper.
- **v3** (7 bidders, single-seat): Current. Replaces 4-way auction with
  single-seat evaluation. Bidder bug fixes applied (see §6a). Numbers are
  not directly comparable to v1/v2 due to methodology change.

#### §2.4 What This Methodology Measures (and What It Does Not)

> Preserved from current §5c. The strongest section in the current report.

**Rewrite guidance:** Under v3 single-seat, "uncontested" is now factually
correct. Rewrite to match:

- **Strengths:** Absolute scale, progress tracking, reproducible exam. Keep
  current language (it's accurate for v3).
- **Limitations:**
  - Confounded by GluttonStrategy (keep as-is).
  - "No auction interaction" — now accurate. State clearly: single-seat mode
    with `current_high_bid=0`, no auction mechanics. For auction-pressure
    analysis, see §8.
  - Self-play vs competitive divergence (keep as-is, with H2H cross-ref).
- **Bottom line:** Keep the current closing paragraph.

**Acceptance criteria:**
- [ ] Every claim about the methodology is factually correct for v3
- [ ] "Uncontested" language is present AND justified (single-seat, no auction)
- [ ] bid_rate formula is stated explicitly
- [ ] Version history covers v1→v2→v3 with bidder identity clarification
- [ ] Metric definitions match actual computation in extraction script

---

### §3. Rankings Table

> **Status:** EXPANDED from current §1. New columns, footnotes, notebook ref.

**Content:** All 7 bidders ranked by net_eppd descending. Same table structure
as current but with additions:

**New columns (from review Note 2):**
- `std` or `IQR` for net_eppd (spread metric)

**New footnotes (from review Note 6):**
- Explain zero-width CVaR CIs: "Zero-width CVaR CIs indicate that the worst
  5% of outcomes for these bidders all incur the same set penalty (−bid_n),
  reflecting their narrow bid-level distribution."

**Notebook reference (from review Note 10):**
- "See notebook `45_comparator_deep_dive`, Figure 1 for per-deal net_eppd
  distributions (violin plot)."

**Data source:** v3 single-seat data from
data/artifacts/arc_d/r0/comparator_cis_r0_v3.json.

**Acceptance criteria:**
- [ ] All numbers are from v3 single-seat data
- [ ] At least one spread metric (std or IQR) is included
- [ ] CVaR footnote explains zero-width CIs
- [ ] Cross-references notebook violin plot
- [ ] bid_rate and make_rate have bootstrap 95% CIs (review Note 3)

---

### §4. Rankings by Contract Type

> **Status:** NEW. Satisfies repo-wide contract-type faceting convention.

**Content:** Per-contract-type breakdown table showing net_eppd, bid_rate, and
make_rate for each bidder, faceted by contract_type (suit / high / low).

**Format:**

```markdown
| Bidder | Contract | net_eppd [95% CI] | bid_rate | make_rate |
|--------|----------|-------------------|----------|-----------|
| modeloespecifico | suit | ... | ... | ... |
| modeloespecifico | high | ... | ... | ... |
| modeloespecifico | low  | ... | ... | ... |
| hybrid_olsa | suit | ... | ... | ... |
| ... | ... | ... | ... | ... |
```

**Narrative (2-3 sentences):** Are rankings preserved within each contract type?
Does hybrid_olsa's selectivity concentrate in certain contract types?

**Data source:** New notebook `45_comparator_deep_dive.py` computes per-contract
metrics from raw JSONL logs.

**Justification:** If faceted rankings match pooled rankings, state it
explicitly: "The pooled ranking order is preserved within each contract type."
If they diverge, explain why.

**Acceptance criteria:**
- [ ] Table shows all 7 bidders × 3 contract types
- [ ] Narrative explains whether rankings are preserved or diverge
- [ ] Data sourced from notebook (not manual computation)

---

### §5. Pairwise Significance

> **Status:** KEEP from current §2. Update numbers only.

**Content:** Bootstrap permutation test results for adjacent-ranked bidders.
Same format as current.

**Changes:** Update all numbers to v3 single-seat data. Significance levels
may change; update the narrative accordingly.

**Acceptance criteria:**
- [ ] All numbers from v3 data
- [ ] Narrative accurately reflects which pairs are significant

---

### §6. Behavioral Profiles

> **Status:** RESTRUCTURED into §6a and §6b. This is the most substantive
> change in the refactor.

The current §3 blends description and results in a single narrative per bidder.
The refactored version separates them to make the reader's mental model explicit:
first understand what each model IS, then compare predictions to results.

#### §6a. Bidder Descriptions

> What each model IS. Decision logic, algorithm, bid range. Written as if the
> reader has not seen the results yet.

For each of the 7 bidders, provide:

1. **Algorithm** (1-2 sentences): What class of model, what inputs.
2. **Decision logic** (2-3 sentences): How it chooses whether/what to bid.
3. **Bid range**: What bid levels are reachable.
4. **Expected behavior** (1-2 sentences): What we'd predict about bid_rate,
   make_rate, and net_eppd before seeing the data.

**Draft sketches for each bidder** (implementing agent should refine based on
post-fix code):

**modeloespecifico** — Hand-coded feature-weighted formula. Computes a score
per contract: suit = `1.0*bowers + 0.5*trump_count + 0.5*offsuit_aces`,
HIGH = `offsuit_aces`, LOW = `offsuit_tens_count`. Score is floored to a bid
level (1-10). Picks the highest-scoring contract across all candidates.
*Expected:* High bid_rate (formula is simple, most hands produce a score ≥ 1),
high make_rate (formula tracks real trick-taking ability from domain expertise).

**hybrid_olsa** — OLS regression (3 constrained features from `hybrid_r0.json`)
predicts expected tricks (mu). Gaussian CDF wrapper models the full distribution
via residual variance (sigma) to compute P(make) and expected value (EV). Bids
only when EV > 0 — the only bidder with an analytical pass threshold. Bid
range 1-10.
*Expected:* Lower bid_rate than always-bid models (passes on negative-EV hands),
higher make_rate when it does bid (self-selected for profitability), strong
net_eppd from avoiding costly sets.

**olsa_full** — OLS regression with all 39 forward-selected features
(`hybrid_r0_full.json`). Floor-based threshold: bids `floor(mu)` if ≥ 1.
No distributional model — no P(make) or EV computation. Bid range 1-10.
*Expected:* Always bids (floor ≥ 1 is easy to reach with 39 features), higher
eppd than constrained models (more features = better predictions), but lower
net_eppd than hybrid_olsa (no selectivity filter).

**olsa** — OLS regression with 3 constrained features (`hybrid_r0.json`).
Same floor-based threshold as olsa_full. Identical OLS coefficients to
hybrid_olsa but without the Gaussian CDF wrapper. Bid range 1-10.
*Expected:* Similar to olsa_full but slightly worse predictions (fewer features).
Serves as the attribution baseline: the difference between olsa and hybrid_olsa
isolates the wrapper effect (see C33 ablation).

**rankthetank** — Rank-sum heuristic using `score_hand_scalar()` (composite
hand strength score). Maps strength to bid level via empirically calibrated
thresholds derived from the canonical bidless dataset. Evaluates all 6 contract
types (4 suits + HIGH + LOW) and picks the strongest. Bid range 1-10.
*Expected:* High bid_rate (rank-sum is generous), moderate make_rate (thresholds
approximate expected tricks but don't account for hand composition nuances),
negative net_eppd (overbids on marginal hands).

**fiveheadfred** — Fixed bidder: always bids 5 Spades if able. No hand
evaluation — completely ignores the dealt cards. Bid range: exactly 5.
*Expected:* Always bids (by definition), moderate make_rate (5 tricks is
achievable on many hands by chance), negative net_eppd (bidding without hand
evaluation guarantees overbidding on weak hands and underbidding on strong ones).

**stricthellraiser** — Escalation bidder: bids `current_high_bid + 1` (or 3
if no prior bid), always Spades. In single-seat mode (`current_high_bid=0`),
always bids 3 Spades. No hand evaluation. Bid range: 3 (in single-seat).
*Expected:* Always bids, low make_rate (bid level has no relationship to hand
strength), worst net_eppd (systematic overbidding is heavily penalized).

**Note on stricthellraiser in single-seat mode:** In single-seat mode with
`current_high_bid=0`, StrictHellRaiser always bids 3 Spades. This is a
degenerate but interpretable baseline: it measures "what happens when you
always bid 3 regardless of your hand." Its escalation logic (bid higher when
outbid) is inert in single-seat mode.

#### §6b. Expected vs Observed

> Compare predictions from §6a to actual results. Frame as "surprises."

**Format:** For each bidder, a short paragraph covering:
1. Did the results match predictions? (Usually yes for heuristic bidders.)
2. Any surprises? (e.g., hybrid_olsa's bid_rate in single-seat mode, the
   magnitude of the olsa_full vs olsa gap, rankthetank's post-calibration
   behavior.)
3. What the result tells us about the bidder's design.

**Key narratives to include:**

- **hybrid_olsa's bid_rate** will be notably different from v2 (was 62.5% under
  4-way best-of-4). The single-seat rate is the true per-hand selectivity.
  Explain what this means for the "selective bidding" interpretation.

- **modeloespecifico's bid_rate** may change after removing the `<= 6` ceiling.
  Previously, strong suit hands (score > 6) were silently dropped. Post-fix,
  these hands now produce bids of 7-9.

- **rankthetank's behavior** after threshold recalibration. The v2 battery had
  miscalibrated HIGH/LOW thresholds (dead code). Post-fix, rankthetank should
  show meaningful HIGH/LOW bid differentiation for the first time.

- **stricthellraiser's single-seat behavior** — always bids 3 Spades, so its
  make_rate reflects "how often can you make 3 tricks with a random hand playing
  Spades as trump?" This is an interesting empirical baseline.

**Acceptance criteria:**
- [ ] §6a descriptions match the post-fix code (not the bugged versions)
- [ ] §6a is written as predictions (before seeing data)
- [ ] §6b explicitly compares predictions to results
- [ ] §6b calls out any surprises or notable findings
- [ ] hybrid_olsa bid_rate change from v2 is explained
- [ ] StrictHellRaiser single-seat degeneracy is noted

---

### §7. Key Observations

> **Status:** KEEP from current §4. Update numbers, re-evaluate claims.

**Content:** High-level takeaways. Same structure as current (numbered list).

**Updates needed:**
- Update all numbers to v3 data.
- Re-evaluate tier boundaries (they may shift with new data).
- "Selective bidding pays off" (observation 2) — the magnitude may change.
  Update the hybrid_olsa vs olsa_full gap.
- "Gap to close" (observation 4) — update the modeloespecifico vs hybrid_olsa
  gap.
- Consider adding an observation about the bidder bug fixes if they changed
  rankings (e.g., "rankthetank improved after threshold recalibration").

**Acceptance criteria:**
- [ ] All numbers from v3 data
- [ ] Tier boundaries re-evaluated and accurate
- [ ] No stale references to v2 numbers

---

### §8. Auction-Pressure Sensitivity

> **Status:** NEW. Secondary diagnostic panel showing 4-way auction results.

**Purpose:** Preserve the auction-interaction signal without conflating it with
the primary (single-seat) ranking. Explicitly labeled as supplementary.

**Content:**

1. **Brief explanation** (2-3 sentences): What the 4-way design is, how it
   differs from single-seat (best-of-4 selection, positional bias, bid_rate
   inflation).

2. **Summary table:** 4-way rankings (v2 data or re-run). Same columns as §3
   but labeled "4-way auction" with a note that these are NOT the primary
   rankings.

3. **Comparison narrative** (3-5 sentences): Do rankings change between
   single-seat and 4-way? If so, why? Expected explanations: best-of-4
   effect benefits selective bidders less (they already pass on weak hands),
   bid_rate inflation makes always-bid policies look comparable.

4. **What the 4-way signal adds:** The `current_high_bid` interaction signal
   that single-seat misses. Note that this is more relevant for future policies
   with opponent modeling.

**Length target:** Compact — ~20-30 lines total. This is a diagnostic appendix.

**Acceptance criteria:**
- [ ] Explicitly labeled as secondary/supplementary
- [ ] 4-way table has different column header or label from §3
- [ ] Comparison narrative explains any ranking differences
- [ ] Does NOT undermine the primary single-seat rankings

---

### §9. Provenance

> **Status:** EXTRACTED from current §5. Standard provenance table.

**Content:** Machine-readable traceability table following the experiment report
template convention.

```markdown
| Item | Value |
|------|-------|
| gate_status | PROMOTED (see r0_promotion_report.md) |
| Artifact (primary) | data/artifacts/arc_d/r0/comparator_cis_r0_v3.json |
| Artifact (4-way) | data/artifacts/arc_d/r0/comparator_cis_r0_v2.json |
| Extraction script | scripts/internal/extract_comparator_cis.py |
| Battery metadata | data/artifacts/arc_d/r0/comparator_battery_r0_v3.json |
| Git SHA | <commit hash> |
| Seed | 42 |
| n_deals | <per bidder> |
| Schema | comparator_v3 |
```

Note: Use plain text for artifact paths (not backticks) to avoid docs-check
lint failures on gitignored paths.

**Acceptance criteria:**
- [ ] `gate_status` present (lint requirement)
- [ ] Both v3 and v2 artifact paths listed
- [ ] Artifact paths in plain text, not backticks

---

## Notebook Specification: `45_comparator_deep_dive.py`

> **Location:** `notebooks/arc_d/r0/45_comparator_deep_dive.py`
> **Format:** Jupytext percent-format (.py), paired with .ipynb
> **Purpose:** Produce all per-deal and per-contract-type analysis that the
> report cross-references.

### S1: Setup & Data Loading

- Load raw JSONL game logs from each bidder's single-seat run
  (`data/runs/auction_comparator_{name}_{seed}_*/logs/*.jsonl`)
- Parse into a per-deal DataFrame with columns:
  `bidder_name`, `deal_id`, `contract_type`, `trump_suit`, `bid_n`,
  `tricks_won`, `declaring_pts`, `defending_pts`, `net_pts`, `made`
- Handle pass deals (no bid → exclude from bid-conditional metrics,
  include in per-deal metrics with 0 contribution)
- **Assert gate:** verify expected bidder count (7), deal count per bidder

**Key implementation note:** The extraction script `extract_comparator_cis.py`
already has JSONL parsing logic at lines 41-96 (`_parse_jsonl_points`), but it
does NOT extract `contract_type`. The notebook must parse the JSONL directly.
Reuse the log-parsing pattern from the H2H notebook
(`50_r0_matchups.py`) if applicable.

### S2: Per-Deal Distributions (Figure 1 — referenced from report §3)

**Violin plot of per-deal net_eppd for each bidder.**

- Y-axis: 7 bidders in ranked order (matching §3 table)
- X-axis: per-deal net points (declaring_pts − defending_pts)
- One violin per bidder
- Annotate with mean ± CI marker overlaid on each violin
- **Faceted by contract_type** (3 panels: suit / high / low)
- Self-play zero-reference line (dashed at x=0)

**Assert gate:** Self-play consistency — mean net_pts for pass deals is 0.

### S3: Contract-Type Breakdown (Table — referenced from report §4)

**Per-contract-type metrics table.**

- Compute net_eppd, bid_rate, make_rate per bidder per contract_type
- Bootstrap 95% CIs on net_eppd
- Output as formatted markdown table for copy-paste into report
- **Assert gate:** bid_rate × 3 contract types ≈ overall bid_rate
  (within rounding)

### S4: Bid-Level Distribution

**Histogram of bid levels by bidder.**

- X-axis: bid level (1-10)
- Y-axis: count or proportion
- One panel per bidder (or stacked/grouped)
- **Faceted by contract_type**
- Highlights: stricthellraiser should show a spike at 3 (single-seat),
  modeloespecifico should now show bids above 6 (post-fix),
  rankthetank should show full 1-10 range (post-calibration)

**Assert gate:** No bids outside [1, 10]. fiveheadfred has only bid=5.

### S5: Summary Statistics

- Print key summary numbers for easy reference from the report
- Per-bidder: n_deals, n_bids, bid_rate, make_rate, net_eppd, std, CVaR-5%
- Per-contract-type aggregated across all bidders

### Notebook Conventions

- All charts faceted by contract_type (or justify pooling)
- `MODE` parameter for SMOKE/QUICK/FULL (default SMOKE for fast iteration)
- Assert gates at each section boundary
- No data artifacts committed — notebook reads from `data/runs/`

---

## Files to Create / Modify

| File | Action | What Changes |
|------|--------|--------------|
| `docs/04_reports/r0/comparator_rankings.md` | **Rewrite** | Full refactor per section specs above |
| `notebooks/arc_d/r0/45_comparator_deep_dive.py` | **Create** | New notebook per spec above |
| `notebooks/arc_d/r0/45_comparator_deep_dive.ipynb` | **Create** | Jupytext-paired ipynb (auto-generated) |
| `docs/04_reports/r0/h2h_battery_analysis.md` | **Minor edit** | Update §3 comparator cross-reference to note v3 methodology |
| `docs/04_reports/README.md` | **Minor edit** | Update comparator_rankings entry with v3 date |

---

## Validation Checklist

Before opening the PR:

- [ ] `make check-quiet` passes (repo-lint + ruff + pytest + notebook-check + docs-check)
- [ ] `make notebook-check` passes (Jupytext sync, outputs cleared)
- [ ] All charts in notebook faceted by contract_type
- [ ] All matchup/summary tables show appropriate breakdowns
- [ ] Report cross-references to notebook are valid (correct figure numbers)
- [ ] Report cross-references to other reports are valid relative links
- [ ] `gate_status` present in §9 Provenance
- [ ] No data artifacts committed (data/runs/, data/reports/)
- [ ] No backtick-quoted artifact paths (docs-check lint)
- [ ] Worktree workflow used (not main checkout)

---

## Key Files to Read Before Implementing

### Must-read
- `plans/comparator_rankings_review_notes.md` — the review notes driving changes
- `plans/comparator_experiment_redesign.md` — experiment redesign + bidder fixes
- `docs/04_reports/r0/comparator_rankings.md` — the report being refactored
- `src/bid_euchre/strategy/bidding.py` — all 7 bidder classes (post-fix versions)
- `scripts/internal/extract_comparator_cis.py` — CI extraction, metric computation

### Should-read
- `docs/04_reports/r0/c33_ablation_report.md` — reference for report quality/structure
- `docs/04_reports/r0/h2h_battery_analysis.md` — cross-referenced report
- `notebooks/arc_d/r0/50_r0_matchups.py` — reference for notebook patterns
- `docs/02_agent/EXPERIMENT_REPORTS.md` — 8-section template convention

### Reference
- `CLAUDE.md` — project conventions
- `.claude/rules/05_rigor.md` — statistical rigor requirements
- `.github/pull_request_template.md` — PR template
- `docs/01_core/DATA_CONTRACT.md` — logging schema (for JSONL parsing)
