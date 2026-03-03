# R0 Report Q&A Log

> Session: 2026-03-02
> Purpose: Review R0 reports for accuracy, consistency, and completeness.
> Outcome: Findings will be converted to an actionable plan if edits are needed.

---

## Questions & Findings

<!-- Log each Q&A exchange below. Mark findings with severity: HIGH / MED / LOW -->

### Q1: Should the comparator battery include an oracle bidder?

**Question:** Would an oracle entry in the comparator help show the theoretical ceiling? Or would it invite overfitting?

**Answer:** No — the oracle is not a playable strategy (requires perfect outcome knowledge). Adding it to the comparator would:
- Collapse the nuanced 3-way regret decomposition (pass-threshold 82%, contract-selection 17%, overbid 1%) into a single net_eppd gap
- Create a misleading optimization target that incentivizes overfitting to the deal distribution
- Require coupling the battery to a fixed deal set (oracle decisions are pre-computed)

The oracle regret analysis (notebook 55, `contract_selection_oracle.md`) already provides the ceiling measurement with richer decomposition.

**Decision:** Table until post-R5. After model development is complete, add the oracle as a retrospective reference point ("how close did we get?"). Including it mid-development risks creating an optimization target. No action needed now.

---

### Q2: Why doesn't ModeloEspecifico have bid_rate=1.0 in the comparator?

**Question:** In single-seat mode (current_high_bid=0), shouldn't ModeloEspecifico always bid?

**Answer:** It has an artificial bid floor of 3 at `bidding.py:455` (`if 3 <= bid_n <= 10`). Hands where the formula `1.0*bowers + 0.5*trump + 0.5*aces` produces a score of 1 or 2 are rejected. This causes 1.4% of hands to pass unnecessarily.

**Full audit of all 7 comparator bidders:**

| Bidder | Floor | Ceiling | Issue? |
|--------|-------|---------|--------|
| modeloespecifico | **3** | 10 | **FIX** — lower to 1 |
| hybrid_olsa | 1 | 10 | OK (EV>0 gate is economic, not artificial) |
| stricthellraiser | 3 | 10 | OK — dumb baseline, floor is the design |
| olsa_full | 1 | 10 | OK |
| olsa | 1 | 10 | OK |
| fiveheadfred | 5 | 5 | OK — fixed-bid baseline by design |
| rankthetank | **3** | 10 | **FIX** — recalibrate thresholds for 1–10 |

**Decision:** Fix ModeloEspecifico (floor 3→1) and RanktheTank (recalibrate for 1–10). StrictHellRaiser and FiveHeadFred are intentional baselines — no change. Re-run comparator battery after code changes.

**Severity:** HIGH — affects comparator rankings, requires experiment re-run.

**Cascade:**
1. Code fix (ModeloEspecifico + RanktheTank)
2. Re-run comparator battery → v5
3. Re-run H2H battery → v3 (both bidders participate)
4. Re-generate reports: comparator_rankings, h2h_battery_analysis, c33_ablation, model_arc_r0, pass_threshold_decision (all cite comparator/H2H numbers)
5. Re-run notebooks: 45_comparator_deep_dive, 50_r0_matchups, possibly 55_oracle, 56_sweep
6. Update rung bundle → point to v5 comparator + v3 H2H data

---

### Q3: Should C33 ablation normalize bid_rate by seat position?

**Question:** The bid_rate in §2 is partly a function of seat position relative to dealer. Could seat-position bias inflate or deflate the reported bid_rate?

**Answer:** No normalization needed. The C33 design already controls for this:

1. **Symmetric seat assignment:** `[hybrid_olsa, olsa, hybrid_olsa, olsa]` in matchup 3, reversed in matchup 4. Each strategy occupies both team positions.
2. **Random dealer rotation:** `dealer_index = rng.randrange(4)` per deal (`simulation.py:105`). Auction order is `(dealer+offset)%4` for offset 1–4. Over 10k deals, each strategy gets ~equal turns as first/last bidder.
3. **Paired seat-swap:** Matchups 3 & 4 use same deals with strategies swapped. Any seat-position effect cancels in the pooled estimate (+0.21).
4. **Bid-rate dominated by EV threshold, not position:** hybrid_olsa bids 16–17%, olsa bids 84%. The decision boundary is the Gaussian EV > 0 gate, not auction position.

**Where seat normalization IS relevant:** Multi-bidder H2H (7-way battery) where more than 2 strategies compete and some seats see earlier bids. The C33 2-bidder design is specifically constructed to cancel seat effects.

**Decision:** No action needed for R0. For R1+, add **seat-balanced competitive bid rate** as the headline metric in §2: average the two reciprocal cross-matchups per bidder. Keep single-cell rates as supporting detail. Example from R0 data:
- hybrid_olsa: (16.2 + 16.5)/2 = 16.35%
- olsa: (83.8 + 83.5)/2 = 83.65%

Conclusions unchanged, but interpretation is cleaner. Low cost, high defensibility.

**Severity:** LOW — R1 enhancement, not a correction.

---

### Q4: C33 ablation — H2H or comparator? + Does hybrid_olsa search bid levels?

**Q4a:** C33 is **H2H** (4 matchups, paired deals, seat-swapped). Both bidders compete in the same auction. Not comparator (single-seat isolation).

**Q4b:** HybridOLSa does **NOT** search for a lower bid level. It evaluates `bid_n = floor(mu)` only (`bidding.py:1027`). If EV is negative at that level, it skips the contract entirely — it never tries `bid_n - 1`.

**Finding:** A hand with `mu=4.8` → `bid_n=4`. If EV < 0 at bid 4, a bid of 3 might have positive EV (higher P(make), lower set penalty). The current "greedy single-point" design leaves this value on the table. A bid-level search variant would loop from `floor(mu)` down to 1 and pick the level with highest positive utility.

**Decision:** Implement at **R1, not R0**. Rationale:
- R0 is promoted/frozen — changing the promotional model retroactively breaks governance
- v5 cascade (Q2) is already pending for baseline bidder fixes — don't compound with a promotional model change
- R1 is the improvement rung; bid-level search interacts with P1 (HIGH/LOW enrichment) for potential compounding
- Implement as `bid_level_search=True/False` param on HybridOLSaBidder so R0 behavior is preserved

**Severity:** HIGH — potential significant net_eppd improvement. Tracked in r1_follow_ups.md.

---

### Q5: Should olsa_full be renamed to hybrid_olsa_full?

**Question:** Is `olsa_full` actually a hybrid (Gaussian wrapper) bidder?

**Answer:** No. `olsa_full` uses `OLSaBidder` (floor-based, no Gaussian wrapper) with the full-arm artifact (`hybrid_r0_full.json`, 7 features). The "hybrid" prefix means Gaussian CDF wrapper — `olsa_full` doesn't have it. Rename would be misleading.

**Finding: Missing comparator variant.** The 2×2 matrix of (wrapper × arm) has a gap:

| | Floor-based | Gaussian wrapper |
|---|---|---|
| Constrained (3 features) | `olsa` | `hybrid_olsa` |
| Full arm (7 features) | `olsa_full` | **missing** |

`HybridOLSaBidder` + `hybrid_r0_full.json` is trivial to create (class already accepts any `hybrid_olsa_v1` artifact). Would answer: "Does the Gaussian wrapper help the full-arm model as much as it helps the constrained arm?"

**Decision:** Log as finding. Plan to add `hybrid_olsa_full` to comparator in a separate plan (v5 re-run or R1).

**Severity:** MED — missing experimental variant, not an error in existing data.

---

### Q6: Chart citations in reports should include links

**Question:** Reports reference charts as prose ("See notebook S3, Chart 3a") without clickable links or inline images. Can we improve this?

**Current state:** No chart PNGs committed. Charts are generated on-demand into `data/reports/` (gitignored) or within notebook execution. Reports cite by notebook name + section number only.

**Options:**
1. **Relative links to notebook .py files** — e.g., `[Chart 3a](../../../notebooks/arc_d/r0/57_c33_ablation_deep_dive.py)`. Works on GitHub, no binary files, consistent with data policy.
2. **Commit chart PNGs to `docs/04_reports/r0/charts/`** — embed as `![caption](charts/foo.png)`. Inline rendering on GitHub but adds binary files to git.

**Decision:** TBD — to be planned separately. Affects all R0 reports + report conventions for R1+.

**Severity:** LOW — UX improvement, not a correctness issue.

**Sub-decision:** Use option 1 (relative links to notebook .py files). Consistent with data policy, no binary files.

---

### Q7: Contract-type breakout missing from key reports

**Question:** Are all reports breaking out analysis by contract_type?

**Answer:** No. Four reports have zero contract_type references:

| Report | contract_type mentions | Severity |
|--------|----------------------|----------|
| **dual_track_analysis.md** | 0 | **HIGH** — all tables pooled, hides contract-type behavioral differences |
| **h2h_battery_analysis.md** | 0 | **HIGH** — H2H deltas are pooled, no per-contract breakdown |
| **measurement_integrity_r0.md** | 0 | OK — methodology discussion, no data tables |
| **pass_threshold_decision.md** | 0 | **MED** — sweep is inherently pooled, but should note contract-type composition |

Key gaps in dual_track_analysis.md:
- §2.2 comparator rankings: pooled net_eppd only, no per-contract facets
- §3.2 archetype assignment: bid_rate/make_rate pooled, hiding that hybrid_olsa bids 98% suit
- §3.3 H2H by archetype: pooled deltas
- §4 scatter plots: pooled metrics, no contract-type coloring or faceting

The repo convention (MEMORY.md "Key Rules") requires: "Every chart/table MUST be faceted by contract_type or justify pooling." These reports don't justify the pooling.

**Decision:** Add contract_type breakouts during the v5 re-run cascade (Q2). Include in the report regeneration step. For dual_track_analysis specifically, add per-contract-type columns to §2.2 and faceted scatter plots in §4.

**Severity:** HIGH — violates repo convention, masks contract-type behavioral differences.
