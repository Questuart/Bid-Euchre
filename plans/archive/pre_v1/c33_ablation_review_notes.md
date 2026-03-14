# C33 Ablation Report — Review Notes (Agent Handoff)

> **Goal:** Refactor the C33 ablation report and supporting notebooks to make the
> "selective restraint" mechanism empirically grounded rather than asserted.
>
> **Source report:** `docs/04_reports/r0/c33_ablation_report.md`
> **Scope:** R0 only. Changes do not persist to other rungs.

---

## Current Report Structure

The report has 8 sections:
1. Motivation
2. Methodology
3. Results (self-play sanity + cross-matchup tables + behavioral profile)
4. Interpretation
5. Impact & Decisions
6. Arc Context
7. Provenance
8. Reproduction

---

## Deliverables

### D1. Refactored ablation report (`docs/04_reports/r0/c33_ablation_report.md`)

The report needs structural changes. Proposed new section order:

| # | Section | Status | Notes |
|---|---------|--------|-------|
| 1 | Motivation | Keep as-is | |
| 2 | Methodology | Minor edits | Add bid_rate formula, clarify competitive vs intrinsic bid rate |
| **3** | **Architecture Comparison** | **NEW** | Consolidates all hybrid_olsa vs olsa differences |
| 4 | Results | Expand | Add distributional detail, team0/team1 breakout |
| **5** | **Decision Divergence Evidence** | **NEW** | References notebook 55; summarizes key findings |
| 6 | Interpretation | Revise | Currently §4; update to reference new evidence sections |
| 7 | Impact & Decisions | Keep as-is | Currently §5 |
| 8 | Arc Context | Keep as-is | Currently §6 |
| 9 | Provenance | Keep as-is | Currently §7 |
| 10 | Reproduction | Keep as-is | Currently §8 |

#### D1-a. New §3: Architecture Comparison (hybrid_olsa vs olsa)

**Purpose:** Make the ablation self-contained — the reader fully understands the
independent variable before seeing outcomes.

**Two subsections:**

**A. Bid/Pass Decision Mechanism (Gaussian EV wrapper)**
- Mechanics: Both bidders share identical OLS coefficients (`hybrid_r0.json`).
  OLS predicts mu (expected tricks). Difference is the decision layer:
  - hybrid_olsa: models full distribution via residual variance (sigma).
    P(make) = P(tricks >= bid) via normal CDF. Bids if EV > 0.
  - olsa: bids if mu >= bid - margin (floor-based). No distributional model.
- Benefits: accounts for prediction uncertainty, principled EV threshold (not
  hand-tuned margin), adapts per-contract via differing residual variance.
- Drawbacks: Gaussian assumption on discrete/bounded [0,10] data. Global sigma
  per contract (no heteroscedasticity). Misestimating sigma has directional
  consequences (overestimate → excessive passivity, observed at 16.2% competitive
  bid rate).

**B. Risk Quantification (analytical CVaR)**
- Mechanics: Gaussian model enables analytical CVaR-5% from left tail
  (mu - sigma * phi(z_0.05) / 0.05). Per-hand downside risk before play.
  Floor-based olsa can only measure CVaR empirically from realized outcomes.
- Benefits: risk-aware bid decisions pre-play, penalizes high-variance hands
  even when EV is positive, relevant given asymmetric set penalties.
- Drawbacks: inherits Gaussian assumptions, likely underestimates tail risk
  near boundaries, doesn't account for opponent strategy or trick dynamics.

#### D1-b. Expand §4 (new numbering) Results

Three additions to the results section:

1. **Distributional detail** — add to existing results tables:
   - Spread metrics: std, IQR, P5/P95 per matchup
   - Win/draw/loss breakdown per matchup
   - Contract-type faceting on all delta distributions

2. **Team0/team1 breakout** — all matchup summary tables must show team0 and
   team1 separately, not collapsed into a single matchup row. (Repo-wide
   convention, now in MEMORY.md Key Rules.)

3. **Bid rate clarification** — in the behavioral profile table:
   - Add formula: `bid_rate = hands_with_bids / deals_total` (from `evaluator.py:326`)
   - Clarify this is competitive (H2H) bid rate, not intrinsic bid rate
   - Show intrinsic bid rate from comparator runs alongside (~63-83%) so the
     reader sees the interaction effect

#### D1-c. New §5: Decision Divergence Evidence

Summarizes findings from notebook D3 (55_c33_ablation_deep_dive). Should include:
- Reference to the EV distribution charts (5a)
- Decision divergence counts table (5b)
- Worked example hand summary (5c)
- Narrative connecting evidence to the "selective restraint" interpretation

---

### D2. Violin plot addition to `notebooks/arc_d/r0/50_r0_matchups.py`

**Scope:** ~10-15 lines. matplotlib already imported, per-deal data already loaded.

**Change:** Add a 4-panel violin plot of per-deal net_eppd_delta for all 4
matchups. Self-play violins (centered on zero) serve as visual null reference;
cross-matchup violins show the distributional shift. Faceted by contract_type.

Referenced from the ablation report's results section.

---

### D3. New notebook: `notebooks/arc_d/r0/55_c33_ablation_deep_dive.py`

**Purpose:** Produces all evidence for the "selective restraint" claim. R0-only,
does not persist to other rungs. Keeps `50_r0_matchups.py` focused on competitive
ranking; this notebook goes deep on *how and why* the wrapper works.

**Sections:**

**S1: Setup & data loading**
- Load C33 ablation run data (40k deals)
- Load model artifact (`hybrid_r0.json`) for replay

**S2: Decision replay**
- For each deal in the cross-matchups, replay through both decision layers
  (Gaussian EV wrapper and floor-based threshold) to capture per-hand:
  mu, sigma, P(make), EV, bid/pass decision
- This may require checking whether eval logs already capture these traces
  or if hands must be replayed through the model artifact

**S3: Aggregate EV distribution (note 5a)**
- **Overlaid histograms** (faceted by contract_type): X = EV of bid decision,
  two distributions (olsa vs hybrid_olsa). Shows olsa's negative-EV tail that
  hybrid_olsa truncates.
- **2x2 decision scatterplot** (faceted by contract_type): X = olsa's predicted
  EV, Y = hybrid_olsa's P(make). Color by decision outcome (both bid, both pass,
  olsa-only bid, hybrid-only bid). Shows decision boundary geometrically.

**S4: Decision divergence table (note 5b)**
- Counts: both bid / both pass / olsa-only bid / hybrid-only bid
- Per-category: mean EV, mean tricks_won, mean net_eppd
- Expected: "olsa-only bid" (restraint zone) dominates divergence and has
  negative or marginal EV

**S5: Worked example hand (note 5c)**
- 1 illustrative deal from the restraint zone (olsa bids, hybrid passes)
- Show: hand features, mu, sigma, P(make), EV calculation step-by-step
- Show actual outcome (did olsa make or get set?) to close the narrative

**S6: Summary**
- Key counts and findings for reference from the ablation report

---

## Dependencies

```
D3 (new notebook) ──produces evidence──> D1-c (new report section §5)
D2 (violin in 50_) ──referenced by────> D1-b (report results §4)
D1-a (architecture section) ────────────> no dependency, can go first
D1-b (results expansion) ──────────────> partially depends on D2, D3
```

**Suggested execution order:**
1. D1-a (architecture section) — standalone, no data dependency
2. D3 (new notebook) — data exploration, produces evidence
3. D2 (violin plot in 50_) — small addition
4. D1-b + D1-c (results expansion + evidence summary) — references D2 and D3
5. D1 final pass — renumber sections, update cross-references, revise interpretation

---

## Open Questions (resolve before planning)

1. **Decision trace data:** Do the existing C33 ablation eval logs capture
   per-hand mu/sigma/P(make)/EV, or will the notebook need to replay hands
   through the model artifact? Check JSONL log schema and the bidding policy's
   logging behavior.

2. **EV formula confirmation:** Verify the exact EV formula used by the Gaussian
   wrapper in `src/bid_euchre/strategy/bidding.py` — need the precise
   reward/penalty terms to compute EV for the histograms.

3. **Bid rate in comparator context:** The intrinsic bid rate numbers (~62.5%
   and ~82.8%) appear in different reports. Confirm which run/seed/context
   produced each number for accurate citation.

---

## Conventions to Follow

- **Contract-type faceting:** ALL charts and tables MUST be faceted by
  contract_type or justify pooling
- **Matchup team breakout:** ALL matchup summary tables MUST show team0 and
  team1 separately
- **Bid rate clarity:** Always distinguish competitive (H2H) bid rate from
  intrinsic (comparator/self-play) bid rate
- **Jupytext:** Edit .py files, not .ipynb. Use `jupytext --sync` for pairing.
- **Notebook naming:** 55_ prefix slots between existing 50_ (matchups) and
  any future 60_ notebooks
