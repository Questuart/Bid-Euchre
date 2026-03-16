# Comparator Rankings Report — Review Notes

> **Report under review:** `docs/04_reports/arc_d_v1/r0/comparator_rankings.md`
> **Scope:** R0 only. Notes for potential future refactoring.
> **Status:** Running log — no modifications yet.

---

## Current Report Section Map

For reference, the report's current structure with line numbers:

| § | Heading | Lines | Status |
|---|---------|-------|--------|
| — | Header (Arc/Rung/Date/Methodology) | 1-6 | Keep |
| 1 | Rankings Table | 8-21 | Expand (Notes 1, 2, 3) |
| 2 | Pairwise Significance | 23-40 | Keep as-is |
| 3 | Behavioral Profiles | 42-80 | Minor edits |
| 4 | Key Observations | 82-106 | Keep as-is |
| 5 | Methodology | 108-119 | Reposition (Note 4) |
| 5a | — Supersession Note | 121-128 | Merge (Note 5) |
| 5b | — Bidder Identity Note | 130-136 | Merge (Note 5) |
| 5c | — What This Methodology Measures | 138-172 | **FIX (Note 12: "uncontested" is wrong)** |

---

## Proposed Refactored Section Outline

Below is the target structure for the refactored report. Each section includes
its header, a brief description of what it covers, the source (existing or new),
and which notes drive the change.

---

### Header (keep, minor update)

```
# R0 Comparator Rankings (v3, Single-Seat, 7 Bidders)

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-02-XX (v3; supersedes v2 4-way auction rankings)
**Methodology:** Single-seat evaluation · 10,000 deals per bidder · seed=42 · 10,000 bootstrap resamples
```

Update version to v3, add "Single-Seat" to title, update methodology one-liner.
Date TBD when experiment is re-run.

---

### §1. Summary (NEW — Note 9)

> Brief executive overview making the report self-contained for a reader
> unfamiliar with Arc D.

**Covers:**
- **What this is:** A self-play benchmark where each bidder evaluates random
  hands and plays declared contracts against GluttonStrategy. Measures
  intrinsic bidding quality in isolation.
- **Why it's run this way:** Provides an absolute benchmark ("is this model
  any good?") without requiring O(n²) pairwise matchups. Enables
  rung-over-rung progress tracking against a fixed reference point.
- **What it tells us:** Ranks 7 bidders on net_eppd. Three tiers emerge
  (competitive / weak / degenerate). hybrid_olsa ranks #2 behind the
  domain-expert modeloespecifico, with selective bidding as the dominant
  differentiator among trained models.
- **How to use it going forward:** Baseline for rung-over-rung tracking. Each
  new rung runs the same battery to measure absolute progress. Self-play
  rankings can diverge from competitive ordering — use H2H for promotion.
- **Arc context:** Where this fits in the R0 evaluation stack (alongside H2H
  battery, C33 ablation, and threshold calibration).

**Length target:** ~10-15 lines of prose.

---

### §2. Methodology (MOVED from current §5 — Note 4)

> Describes the experimental design so the reader understands the evaluation
> before seeing numbers.

**Covers:**
- Experimental design: single-seat evaluation (v3). One random seat per deal,
  `current_high_bid=0`, bid-or-pass, GluttonStrategy card play.
- Parameters: deal count, seed, bootstrap configuration.
- Metric definitions: net_eppd, eppd, bid_rate, make_rate, CVaR-5%.
- Extraction script and source data references.
- Auction-pressure sensitivity panel: notes that a secondary 4-way auction
  battery is available (v2 data) for readers interested in the contested-
  auction signal. Cross-references the sensitivity panel section (§8).
- **bid_rate formula** (Note 3): `bid_rate = hands_with_bids / deals_total`.
  In single-seat mode, this is the per-hand selectivity rate.

**Subsections:**

#### §2.1 What This Methodology Measures (and What It Does Not)

> Preserved from current §5c (lines 138-172). This is the strongest section
> in the current report — keep as-is with minor updates to reflect v3
> single-seat design.

**Updates needed:**
- **Factual correction (Note 12):** The current report says "no competing
  bidder in the auction" and "evaluates uncontested bidding" — this is wrong
  for the v2 4-way design (there IS a contested 4-seat auction). Under the
  v3 single-seat design, "uncontested" becomes accurate. Rewrite to match
  the actual methodology of whichever version the report describes.
- Clarify that net_eppd is measured from the declaring team's perspective
  (positive values are expected when the policy picks profitable contracts).

#### §2.2 Version History

> Merged from current §5a + §5b (Note 5). Single subsection covering
> v1→v2→v3 progression.

**Covers:**
- v1 (5 bidders, 4-way auction), v2 (7 bidders, 4-way auction),
  v3 (7 bidders, single-seat).
- Bidder identity changes: v1 `hybrid_olsa` = OLSa_Full promotional arm;
  v2+ `hybrid_olsa` = constrained arm with Gaussian CDF wrapper.

---

### §3. Rankings Table (EXPANDED from current §1 — Notes 1, 2, 3, 6)

> Primary results table ranked by net_eppd. This is the headline output.

**Changes from current:**
- **Add spread metrics (Note 2):** std or IQR column for net_eppd.
- **Add CIs to bid_rate and make_rate (Note 3):** Bootstrap CIs for
  consistency with other metrics.
- **Add CVaR footnote (Note 6):** Explain zero-width CVaR CIs for heuristic
  bidders (set penalty floors at `-bid_n`).
- **Reference violin plot:** "See Figure 1 in notebook
  `45_comparator_deep_dive` for per-deal distributions."

**Numbers will change** when single-seat experiment runs. bid_rate in
particular will shift significantly (currently inflated by best-of-4 effect
in 4-way design).

---

### §4. Rankings by Contract Type (NEW — Note 1)

> Per-contract-type breakdown of key metrics, satisfying the repo-wide
> faceting convention.

**Covers:**
- Table: net_eppd, bid_rate, make_rate faceted by contract_type
  (suit / high / low) for each bidder.
- Brief narrative: are rankings preserved within each contract type?
  Does the Gaussian wrapper's selectivity concentrate in certain contract
  types (different sigma per contract)?

**Data source:** New notebook `45_comparator_deep_dive.py` parses raw JSONL
logs and computes per-contract-type metrics. Report cross-references the
notebook for detailed charts.

**Justification:** If faceted rankings are identical to pooled rankings, a
brief note saying so is sufficient — but the data must be shown.

---

### §5. Pairwise Significance (KEEP — current §2)

> Bootstrap permutation tests for net_eppd differences between
> adjacent-ranked bidders. No structural changes needed.

**Updates:** Re-run with v3 single-seat data. Numbers and possibly
significance levels will change.

---

### §6. Behavioral Profiles (KEEP — current §3)

> Per-bidder narrative descriptions explaining strategy and performance.

**Updates:**
- Update numbers to match v3 single-seat results.
- Clarify that bid_rate now reflects per-hand selectivity (not best-of-4
  probability). hybrid_olsa's bid_rate will decrease from 62.5%.
- Minor wording adjustments for accuracy.

---

### §7. Key Observations (KEEP — current §4)

> High-level takeaways from the rankings.

**Updates:**
- Update numbers to match v3 data.
- May need to adjust observation 2 ("selective bidding pays off") since the
  magnitude of the selectivity advantage may change in single-seat mode.
- Tier boundaries may shift slightly.

---

### §8. Auction-Pressure Sensitivity (NEW — from Workstream B)

> Secondary diagnostic showing the 4-way auction results for comparison.
> NOT the primary ranking — explicitly labeled as sensitivity analysis.

**Covers:**
- Brief explanation of the 4-way design and how it differs from single-seat.
- Summary table of 4-way rankings (v2 data, or re-run for consistency).
- Comparison: do rankings change? If so, why? (Best-of-4 selection,
  positional bias, bid_rate inflation.)
- Narrative: what the 4-way signal adds that single-seat misses
  (`current_high_bid` interaction, auction pressure).

**Length:** Compact — this is a diagnostic appendix, not the main event.

---

### §9. Provenance (KEEP — currently embedded in §5)

> Source data paths, gate status, extraction script references.

**Covers:**
- Extraction script path, source data path, battery metadata path.
- `gate_status: PROMOTED` cross-reference to promotion report.
- v3 artifact naming (TBD from Workstream B).

---

### Section Map: Current → Proposed

| Current | Proposed | Notes |
|---------|----------|-------|
| Header | Header | Update version/methodology |
| *(none)* | **§1. Summary** | NEW (Note 9) |
| §5 Methodology | **§2. Methodology** | MOVED up (Note 4) |
| §5a Supersession Note | §2.2 Version History | MERGED (Note 5) |
| §5b Bidder Identity Note | §2.2 Version History | MERGED (Note 5) |
| §5c What This Measures | §2.1 What This Measures | MOVED into §2 |
| §1 Rankings Table | **§3. Rankings Table** | EXPANDED (Notes 1,2,3,6) |
| *(none)* | **§4. Rankings by Contract Type** | NEW (Note 1) |
| §2 Pairwise Significance | **§5. Pairwise Significance** | KEEP (renumbered) |
| §3 Behavioral Profiles | **§6. Behavioral Profiles** | KEEP (renumbered) |
| §4 Key Observations | **§7. Key Observations** | KEEP (renumbered) |
| *(none)* | **§8. Auction-Pressure Sensitivity** | NEW (Workstream B) |
| *(embedded in §5)* | **§9. Provenance** | EXTRACTED |

---

## Report Strengths

Before listing improvement areas, what's working well:

- **§5c "What This Methodology Measures"** is excellent — clearly explains
  confounding with GluttonStrategy, lack of auction interaction, and when to
  use H2H instead. This is the gold standard for methodology caveats.
- **§2 Pairwise Significance** with bootstrap permutation tests gives
  statistical rigor beyond just rankings.
- **§3 Behavioral Profiles** provides per-bidder narrative context that
  makes the raw numbers interpretable.
- **§5a Supersession Note** documents v1→v2 history transparently.

---

## Observations & Potential Changes

### Note 1: Contract-type faceting missing (§1 Rankings Table)

**Convention violation.** The §1 rankings table pools all contract types (suit,
high, low) into single aggregate metrics. The repo-wide convention requires all
tables/charts to be faceted by contract_type or explicitly justify pooling.

This matters because:
- Bidders may perform very differently by contract type (suit contracts have
  bowers/trump; high/low are no-trump)
- hybrid_olsa's selective bidding (62.5% bid rate) may be concentrated in
  certain contract types
- The Gaussian wrapper's residual variance (sigma) differs per contract type,
  so its selectivity effect varies

**Proposed change:** Add a contract-type breakdown table (either in §1
directly or referenced from a notebook). At minimum, show net_eppd, bid_rate,
and make_rate faceted by contract_type for each bidder.

**Justification for pooling (if kept):** If adding a full faceted table is too
heavy, the report should at least include a sentence justifying why pooled
metrics are sufficient here (e.g., "Contract-type breakdowns are available in
notebook 50_r0_matchups; the pooled ranking order is preserved within each
contract type.").

---

### Note 2: No distributional detail in results (§1 Rankings Table)

The §1 rankings table shows point estimates + CIs for net_eppd and eppd, but no
spread or shape metrics. Same issue identified in the C33 ablation review.

**Missing:**
- Spread: std, IQR, or P5/P95 per bidder
- Shape: any indication of skewness (the CVaR-5% gives left-tail info, but
  nothing about the right tail or overall distribution)
- Per-deal outcome distributions (histograms or violin plots)

**Why it matters:** Two bidders could have the same mean net_eppd but very
different variance profiles. The CVaR-5% column partially addresses this, but
it's a single tail quantile, not a full distributional picture.

**Proposed change:** Add spread metrics to the §1 table (at least std or
IQR) and reference a notebook with per-deal distribution visualizations.

---

### Note 3: bid_rate and make_rate lack confidence intervals (§1 Rankings Table)

Every other metric in the §1 rankings table has bootstrap 95% CIs, but bid_rate
and make_rate are bare point estimates. This is inconsistent.

**Why it matters:** bid_rate for hybrid_olsa (0.625) is the single most
important behavioral distinction in the table. Without a CI, the reader can't
tell if this is 0.625 +/- 0.001 or +/- 0.05.

**Proposed change:** Add CIs to bid_rate and make_rate, or add a footnote
explaining their omission (see Open Question 2 resolution below).

---

### Note 4: Methodology section placement (§5 → move before §1)

The report's current flow is:
1. §1 Rankings Table
2. §2 Pairwise Significance
3. §3 Behavioral Profiles
4. §4 Key Observations
5. §5 Methodology (including sub-notes)

The §5 methodology section appears *after* the results and observations. The
standard experiment report template (`docs/02_agent/EXPERIMENT_REPORTS.md`) puts
methodology before results.

**Proposed change:** Move §5 (including all subsections) to appear after the
header/intro, before §1 Rankings Table. This lets the reader understand the
evaluation design before interpreting numbers.

**Counter-argument:** Some readers prefer results-first for quick reference.
If so, the header already has a one-line methodology summary
("10,000 deals per bidder, seed=42, 10,000 bootstrap resamples"). This could
be expanded slightly as a sufficient upfront summary, keeping detailed
methodology at the bottom as reference.

---

### Note 5: Redundant v1→v2 naming notes (§5a + §5b)

Two subsections both explain the v1→v2 naming change:
- §5a "Supersession Note" (lines 121-128)
- §5b "Bidder Identity Note" (lines 130-136)

These cover substantially the same ground (v1 had 5 bidders, v2 has 7;
`hybrid_olsa` identity changed between versions).

**Proposed change:** Merge into a single "Version History" or "Naming Note"
subsection that covers both the supersession and the identity change.

---

### Note 6: CVaR-5% floor values unexplained (§1 Rankings Table)

Three heuristic bidders show CVaR-5% values with zero-width CIs:
- rankthetank: -6.000 [-6.000, -6.000]
- fiveheadfred: -5.000 [-5.000, -5.000]
- stricthellraiser: -6.000 [-6.000, -6.000]

The report doesn't explain why these CIs have zero width.

**Why it matters:** A metric with zero variance is hitting a boundary condition
in the scoring formula. The reader may wonder if this is a bug or an artifact.

**Proposed change:** Add a brief footnote to the §1 table explaining the floor
(see Open Question 3 resolution below for the exact mechanism).

---

### Note 7: Duplication with H2H battery analysis report (cross-report)

The H2H battery analysis report (`h2h_battery_analysis.md` §3) contains a
near-complete copy of the comparator rankings:
- Same rankings table (H2H §3.2 ≈ this report's §1)
- Same pairwise significance table (H2H §3.3 ≈ this report's §2)
- Same observations (H2H §3.4 ≈ this report's §4)

This creates maintenance burden — any update to the comparator rankings must
be mirrored in the H2H report.

**Options:**
- A. **Keep duplication, add cross-reference warning** — note in both reports
  that they duplicate content and must be updated together
- B. **Remove from H2H report, cross-reference only** — the H2H report's §3
  becomes a summary + link to this report
- C. **Status quo** — accept duplication as the cost of self-contained reports

**Recommendation:** Option B. The H2H report is already long (500+ lines).
Moving the comparator section to a cross-reference reduces its scope to what
it uniquely covers (H2H matchups, thresholds). The comparator_rankings.md
report is the authoritative source for self-play rankings.

---

### Note 9: Missing summary / executive overview (top of report)

The report has no introductory section. It goes directly from the header
metadata (Arc/Rung/Date/Methodology one-liner) into the rankings table. A
reader unfamiliar with the Arc D context has no way to understand:

1. **What this is:** A self-play evaluation where each bidder plays
   independently against GluttonStrategy (the card-playing policy). No
   contested auction — each bidder declares uncontested.
2. **Why it was run this way:** Provides an absolute benchmark ("is this
   model any good?") rather than a relative comparison ("which is better?").
   Enables rung-over-rung progress tracking against a fixed reference point
   without requiring O(n²) pairwise matchups.
3. **What it tells us:** Ranks 7 bidders on net_eppd. hybrid_olsa ranks #2
   behind the domain-expert modeloespecifico, with a 0.624 gap that R1+ aims
   to close. Three tiers emerge (competitive / weak / degenerate). Selective
   bidding via the Gaussian wrapper is the dominant differentiator among
   trained models.
4. **How to use it going forward:** Baseline for rung-over-rung tracking.
   Each new rung runs the same battery to measure absolute progress. But
   self-play rankings can diverge from competitive ordering (see H2H
   battery) — use this for benchmarking, H2H for promotion decisions.
5. **Arc context:** Where this fits in the R0 evaluation stack (alongside
   H2H battery, C33 ablation, and threshold calibration).

The information for all 5 points *exists* in the report — it's scattered
across §3 Behavioral Profiles, §4 Key Observations, and §5c What This
Methodology Measures. But none of it appears before the reader hits the
rankings table.

**Proposed change:** Add a new section immediately after the header
(before §1 Rankings Table) that covers these 5 points in ~10-15 lines.
This would subsume the motivation currently implied across §4 and §5c
without removing those sections (they provide detail the summary doesn't).

This is related to Note 4 (methodology placement) — if a summary section
is added, it partially addresses the "methodology comes after results"
issue by putting the design rationale upfront. The detailed §5 methodology
can stay at the bottom as reference.

---

### Note 10: Violin plot of per-deal distributions (§1 Rankings Table)

The rankings table shows only summary statistics. A violin plot showing the
per-deal net_eppd distribution for each bidder would make the table's numbers
tangible — the reader could see the shape, spread, and tails at a glance.

**What it should show:**
- Y-axis: 7 bidders (ranked order, matching the table)
- X-axis: per-deal net_eppd (or bidder_team_points)
- One violin per bidder showing the full distribution
- Faceted by contract_type (convention requirement)
- Annotated with mean + CI markers overlaid on each violin

**Data source challenge:** The existing comparator battery artifacts only
contain summary-level metrics (per-bidder aggregates). The violin plot needs
per-deal outcome arrays, which requires reading the raw JSONL game logs from
`data/runs/auction_comparator_{name}_{seed}_*/logs/*.jsonl`. The extraction
script (`extract_comparator_cis.py`) already parses these into per-deal arrays
(lines 41-96) but doesn't expose them at notebook-friendly granularity.

**Where to build this:** Two options:
- **Option A:** Add to existing `40_r0_baseline.py` §11 (Comparator Battery).
  Pro: keeps comparator visuals in one place. Con: that notebook already uses
  summary data, not per-deal data; adding JSONL parsing changes its character.
- **Option B:** New dedicated notebook (e.g., `45_comparator_deep_dive.py`).
  Pro: clean separation, room for faceted charts + distribution analysis.
  Con: another notebook to maintain.

**Recommendation:** Option B. The per-deal JSONL loading + contract-type
faceting + violin plots + potential distributional analysis is substantial
enough to warrant its own notebook. This also provides the natural home for
Note 1 (contract-type faceted table) and Note 2 (distributional detail).

**Connection to other notes:**
- Subsumes Note 8 (visual cross-reference) — the report would reference this
  notebook
- Provides the data infrastructure for Note 1 (contract-type faceting) and
  Note 2 (distributional detail)
- If built, the report's §1 would reference the violin plot figure from this
  notebook

---

### Note 12: "Uncontested bidding" claim is factually incorrect (§5c)

**Correctness issue.** The current §5c (lines 140-143) states:

> "There is no competing bidder in the auction — the bidder under test declares
> contracts uncontested"

and

> "No auction interaction. Real games have contested auctions where one bidder's
> bid changes which contracts the opponent gets to play. This battery evaluates
> uncontested bidding — a fundamentally different task."

This is **wrong** for the v2 4-way design. The code runs a real sequential
auction where all 4 seats call `choose_bid()` with strictly increasing bids
enforced. There IS mechanical auction interaction: `current_high_bid` rises
as seats bid, later seats are forced to pass or bid higher, and the winner is
whichever seat can outbid the others.

What's true is that there's no *strategic* interaction — all 4 copies use the
same policy, so there's no opponent modeling or adaptive behavior. But the
auction mechanics are fully contested.

**Under the v3 single-seat design, "uncontested" becomes accurate** — the
single seat evaluates with `current_high_bid=0` and no other seat participates.
So the current report's language accidentally describes the *proposed* design
rather than the *current* one.

**Proposed change (P1):** Fix this immediately regardless of which design the
report ultimately describes:
- If the report stays on v2 data temporarily: rewrite to accurately describe
  the 4-way contested auction with identical policies.
- When the report moves to v3 data: "uncontested" language becomes correct, but
  should clarify *why* (single-seat, no auction, `current_high_bid=0`).

The H2H battery report (`h2h_battery_analysis.md` §1.4) also describes the
comparator as "uncontested" — same correction needed there.

---

### Note 8: No visual cross-reference (whole report)

*Subsumed by Note 10.* If a comparator deep-dive notebook is created (Note 10),
the report would reference it for visualizations, resolving this gap.

---

### Note 11: Comparator experimental design — single-seat redesign

**Status:** Extracted to standalone plan.

See `plans/comparator_experiment_redesign.md` for the full analysis of
4-way auction vs single-seat evaluation design, including code path traces,
three identified artifacts (best-of-4 selection, LOD positional bias,
non-zero-centered net_eppd), pros/cons of single-seat alternative, and
implementation path.

**Decision (2026-02-26):** Make single-seat the **primary** comparator
methodology; retain 4-way auction as a **secondary diagnostic** ("auction-
pressure sensitivity"). Re-run at R0 — zero backward-compatibility cost.
The report quality improvements (Notes 1-10 above) can proceed in parallel
on existing data.

---

## Open Questions — RESOLVED

### Q1: Contract-type data availability → NOT AVAILABLE

**Finding:** The extraction script (`scripts/internal/extract_comparator_cis.py`)
does **not** facet by contract_type. It parses JSONL logs at the hand level and
computes pooled aggregates only (lines 41-96). The function `_parse_jsonl_points`
collects `bidder_team_points` and `net_bidder_team_points` arrays without
recording which contract type each hand used.

**Implication for Note 1:** Adding contract-type faceting to the report requires
one of:
- **Option A:** Modify the extraction script to parse contract_type from the
  JSONL `hand_end` records and compute per-contract-type metrics. Then re-run
  on existing logs (no new simulation needed).
- **Option B:** Build the faceting in a notebook that reads the raw JSONL logs
  directly, and cross-reference from the report.

Option B is lower-risk (no script modification) and follows the pattern used
in the H2H report (notebook produces charts, report references them).

### Q2: bid_rate variance → DETERMINISTIC (with caveat)

**Finding:** Both `OLSaBidder.choose_bid()` (line 730) and
`HybridOLSaBidder.choose_bid()` (line 980) are **purely deterministic** given
the same hand, model artifact, and auction state. There is no randomness in the
bid decision — it's a function of:
- Hand features (deterministic from dealt cards)
- OLS weights + bias (fixed in artifact)
- Residual variance / sigma (fixed in artifact)
- `current_high_bid` from auction state (deterministic given other bids)

However, bid_rate **does** have sampling variance from the deal sequence. The
10,000 deals are a sample from the deal distribution. A different seed would
produce different deals and potentially a different bid_rate. So bid_rate has
variance from the deal-sampling process, not from the decision function.

**Implication for Note 3:** CIs on bid_rate **are** appropriate — they capture
deal-sampling uncertainty ("if we drew a different 10k deals, how much would
bid_rate change?"). The bootstrap already handles this if bid_rate is computed
per-resample. However, the current extraction script computes bid_rate as a
simple fraction (line 117), not as a bootstrapped statistic.

Adding bid_rate CIs would require modifying the bootstrap to resample
per-deal indicator variables. This is low-effort but touches the extraction
script.

### Q3: CVaR floor explanation → SCORING FORMULA FLOORS

**Finding:** The CVaR-5% is the mean of the worst 5% of per-hand
`bidder_team_points` (line 99-102 of extraction script, line 128). From
`scoring.py`, the scoring rules are:

- **Made bid:** bid team gets `tricks_won` (ranges 3-10 since bid ≥ 3)
- **Set bid:** bid team gets `-winning_bid` (ranges -3 to -10)

For the worst 5% of outcomes, the bidder was set. The set penalty is
`-winning_bid`. So:
- A bidder that bids 5 and gets set → **-5 points**
- A bidder that bids 6 and gets set → **-6 points**

The zero-width CIs mean that the worst 5% of hands for these bidders
**all** get set at the same bid level:
- **fiveheadfred:** worst 5% all get set at bid=5 → CVaR-5% = -5.000
- **rankthetank:** worst 5% all get set at bid=6 → CVaR-5% = -6.000
- **stricthellraiser:** worst 5% all get set at bid=6 → CVaR-5% = -6.000

This makes sense: these heuristic bidders have simple, formulaic bid levels.
Their worst outcomes cluster at a single set penalty because they consistently
bid the same amount on hands they can't make.

**Implication for Note 6:** The report should add a brief footnote:
"Zero-width CVaR CIs indicate that the worst 5% of outcomes for these bidders
all incur the same set penalty (-bid_n), reflecting their narrow bid-level
distribution."

---

## Priority Assessment

| Note | Section | Impact | Effort | Priority |
|------|---------|--------|--------|----------|
| 12. "Uncontested bidding" is wrong | §5c | High (correctness) | Low | P0 |
| 11. Experimental design (single-seat) | → `comparator_experiment_redesign.md` | High (correctness) | Medium | SEPARATE PLAN |
| 9. Summary / executive overview | NEW (top) | High (readability) | Low | P1 |
| 1. Contract-type faceting | §1 | High (convention) | Medium | P1 |
| 10. Violin plot (per-deal dist.) | §1 / notebook | High (evidence) | Medium | P1 |
| 2. Distributional detail | §1 | Medium | Medium | P2 |
| 6. CVaR floor explanation | §1 | Medium | Low | P2 |
| 7. H2H duplication | cross-report | Medium | Medium | P2 |
| 3. bid/make rate CIs | §1 | Low | Low | P3 |
| 4. Methodology placement | §5→top | Low | Low | P3 |
| 5. Redundant naming notes | §5a+§5b | Low | Low | P3 |
| 8. Visual cross-reference | whole report | — | — | Subsumed by 10 |
