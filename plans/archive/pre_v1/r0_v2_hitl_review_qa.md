# R0 v2 HITL Review — Q&A Log

**Date:** 2026-03-03
**Purpose:** Section-by-section review of all v2 reports for promotion sign-off
**Outcome:** Follow-up PR plan for any issues found

---

## Review Order

1. `r0_promotion_report.md` — Gate status, headline metrics
2. `comparator_rankings.md` — v6 rankings, pairwise significance
3. `h2h_battery_analysis.md` — v4 matchups, self-play, dominance
4. `c33_ablation_report.md` — Wrapper + search decomposition
5. `dual_track_analysis.md` — Track agreement, archetypes
6. `contract_selection_oracle.md` — Regret decomposition
7. `pass_threshold_decision.md` — Threshold sweep
8. `lambda_decision.md` — Lambda tuning (NEW in v2)
9. `normalizer_offline_screen.md` — Normalizer screen (NEW in v2)
10. `model_arc_r0.md` — Model spec
11. `measurement_integrity_r0.md` — Methodology review
12. `r0_retrospective.md` — Campaign retrospective
13. `v1_v2_delta_review.md` — Delta review (just created)

---

## Q&A Log

### Report 1: r0_promotion_report.md

**Finding R1-1: Metric context mixing in executive summary**
- Problem: Headline table shows eval-instrument metrics (self-play, OLSa_Full, 50k deals) but the paragraph below references comparator metrics (hybrid_olsa, GluttonStrategy, 20k deals) without clear separation. A reader seeing bid_rate 82.8% and bid_rate 96.1% in adjacent text has no way to distinguish them.
- Fix: (B+C with definitions)
  1. Label headline table header with source context: "Self-play evaluation, OLSa_Full promotional arm, seed 42"
  2. Add Definition column to the key metrics table (remove Source column — context is in header)
  3. Separate comparator paragraph into its own labeled block: "Comparator context (single-seat, hybrid_olsa, GluttonStrategy opponent)"
- Decision: ACCEPTED — include in follow-up PR

**Q: Should the Date (2026-02-22) reflect v1 promotion or v2 revision?**
- A: Not raised as issue — date reflects the actual promotion decision, which hasn't changed. Version header already distinguishes v2.

**Finding R1-2: Gate Results section needs more context**
- Problem (a): The 4 Tier 1 checks are listed by name only (e.g., `artifact_integrity_olsa`). No definition of what each check verifies. A reader can't assess whether the gate is meaningful without knowing what "artifact integrity" and "no_nan_inf" actually test.
- Problem (b): The Tier 1 vs Tier 2 distinction is mentioned ("Full semantic gate checks introduced at R1+") but not explained. Why does R0 only get Tier 1? The implicit reason is that R0 has no predecessor to compare against (calibration, fairness, stability require a baseline), but that's not stated.
- Problem (c): No link to where the gate logic lives. A reader wanting to verify what these checks do has no pointer to the source.
- Fix:
  1. Add a "What it checks" column to the gate results table defining each check in one line
  2. Add a sentence explaining WHY R0 uses Tier 1 only (no predecessor baseline for Tier 2 checks)
  3. Add a source pointer: `src/bid_euchre/validation/arc_d_gate.py` (promotion gate) and `src/bid_euchre/diagnostics/semantic_gate.py` (semantic gate engine)
- Decision: ACCEPTED — include in follow-up PR

*Updated: R1-1 now includes pulling comparator metrics into the exec summary as a second labeled table (see below).*

**Finding R1-3: Evaluation Metrics tables lack context labeling and metric definitions**
- Problem: The OLSa_Full and OLSa tables (§Evaluation Metrics) have no header identifying the evaluation context (self-play evaluator, 50k deals per seed). A reader arriving from the exec summary where comparator numbers just appeared would be confused by the different bid_rate values. Additionally, metrics like `downside_var` are presented without any definition — a reader wouldn't know what it measures or whether lower/higher is better.
- Fix:
  1. Add context label to each subsection header (e.g., "OLSa_Full (Promotional Arm) — self-play evaluation, 50,000 deals per seed")
  2. Add a Definition column to EVERY metric table (exec summary, OLSa_Full, OLSa, and comparator). Repeat definitions in each table rather than cross-referencing — self-contained tables are easier to read.
  3. Pull comparator metrics into the exec summary as a second labeled table alongside the self-play table, so both contexts are visible upfront:
     - Table 1: "Self-play evaluation (OLSa_Full promotional arm, seed 42)" — net_eppd, bid_rate, make_rate, CVaR-5%, etc. with Definition column
     - Table 2: "Comparator context (hybrid_olsa, single-seat, GluttonStrategy, seed 42)" — net_eppd, bid_rate, make_rate, rank, with Definition column
     - Narrative paragraph about v2 bid-level search transformation follows as explanation
  4. Metric definitions to include:
     - **net_eppd** — Net expected points per deal (bidder − opponent), including 0 for all-pass redeals
     - **eppd** — Expected points per deal (bidder only), including 0 for all-pass redeals
     - **bid_rate** — Fraction of deals with an auction winner (higher = bids more often)
     - **make_rate** — Fraction of won auctions where the declaring team makes the contract
     - **CVaR-5%** — Average of the worst 5% of bidder point outcomes (tail risk; higher = less risky)
     - **net_CVaR-5%** — Average of the worst 5% of net point outcomes (tail risk; higher = less risky)
     - **downside_var** — Variance of deal outcomes below zero (loss dispersion; lower = more predictable losses)
- Decision: ACCEPTED — include in follow-up PR (extends R1-1)

**Finding R1-4: Eval metrics and comparator table pooled without justification**
- Problem: Both the eval metrics tables (OLSa_Full / OLSa, 3 seeds) and the comparator rankings table are pooled across contract types with no faceting and no justification. Violates the repo-wide contract-type faceting rule.
- Fix: Add explicit pooling justification noting that the promotion report is a summary/decision document — per-contract breakouts are available in notebooks 40/45, comparator rankings §4, and model spec. Pooling is appropriate here because the promotion gate evaluates the bidder as a whole.
- Decision: ACCEPTED — include in follow-up PR

**Finding R1-5: Add model specification comparison between OLSa and OLSa_Full**
- Problem: The Attribution Gap section explains *why* the constrained arm outperforms the full arm, but the reader never sees *what's actually different*. The two arms use completely different feature sets (zero overlap for suit contracts), different intercepts, and different selection methods — but this is only described in prose. A side-by-side spec comparison would make the attribution gap self-evident.
- Fix: Add a "Model Specification Comparison" subsection between Multi-Seed Stability and Attribution Gap, containing:
  1. Summary table: selection method, feature counts per contract type
  2. Per-contract coefficient tables (suit, high, low) showing features, weights, intercepts, and residual variance side-by-side for both arms
  3. Closing observation: zero feature overlap for suit, nearly identical σ² (within 1%), confirming both arms reach similar R² via different paths
- Data source: `hybrid_r0.json` (OLSa) and `hybrid_r0_full.json` (OLSa_Full)
- Decision: ACCEPTED — include in follow-up PR

**Sections 4-8: No issues found.**
- Attribution Gap: Well-structured three-point explanation (enhanced by R1-5 above)
- Comparator Context: Rankings correct, v4→v6 reversal noted
- Gate Threshold Calibration: Two-stage calibration clearly documented, drift ratio included
- Provenance: Complete (artifact paths, SHAs, versions, risk_lambda=0.0)
- Companion Reports: Complete list of 8 companions + methodology review. (Note: v1_v2_delta_review.md and eventual onemodel_decision.md should be added once available — not logged as a finding since those reports don't exist yet in final form.)

---

### Deferred Action: Notebook Meta-Review

**Action: Agent-driven meta-review of all R0 notebooks after HITL Q&A and OneModel work complete.**
- Scope: All 8+ notebooks in `notebooks/arc_d/r0/` (40, 45, 50, 55, 56, 57, 58, 59)
- Purpose: Check for consistency with finalized v2 reports, stale inline code (e.g., nb55/nb56 inline `bid_level_search_vectorized` copies still have the pass_threshold bug from PR #514), contract-type faceting compliance, metric definition consistency, and any claims that need updating after OneModel decision.
- Timing: After HITL Q&A findings PR + OneModel decision are both resolved.
- Execution: Delegate to an agent that reads each notebook and cross-references against the final report suite.

---

### Report 2: comparator_rankings.md

**Finding R2-1: Reproduction command uses deprecated CLI injection pattern**
- Problem: The reproduction command in §9 (lines 444-453) uses `--olsa-artifact`, `--bidder-class`, `--bidder-name` CLI flags. These flags *append* a bidder to the config's roster, creating a duplicate 9th bidder when the 8-bidder `auction_comparator.yaml` is already complete. The v2 execution plan (§6.1) explicitly warned against this. Also, `PYTHONPATH=src` is unnecessary with `uv run`.
- Fix: Replace with config-pinned command matching actual v2 execution:
  ```
  uv run python scripts/internal/run_auction_comparator.py \
      --config experiments/configs/auction_comparator.yaml \
      --seed 42 --single-seat --n-per 5000 \
      --output-format json \
      --output data/artifacts/arc_d/r0/comparator_battery_r0_v6.json
  ```
- Decision: ACCEPTED — include in follow-up PR

**Finding R2-2: Contract-type rankings section still deferred**
- Problem: §4 (Rankings by Contract Type) is entirely deferred with "FULL-mode compute budget prioritized for H2H" justification. However, v2 re-ran both the comparator battery (20k deals) and notebook 45 — per-contract data should be available. The repo-wide contract-type faceting rule requires either faceted data or explicit pooling justification.
- Fix: Populate §4 with per-contract-type rankings from notebook 45 data. If only QUICK-mode resolution is available, include it with a note that FULL-mode per-contract CIs are deferred to R1.
- Decision: ACCEPTED — include in follow-up PR

**Note R2-N1: Investigate hybrid_olsa pass population and bid-level distribution**
- Observation: hybrid_olsa went from 19.7% to 96.1% bid_rate with bid-level search, but still passes on ~4% of hands. Two open questions: (a) What characterizes the hands that are still unbiddable? (mu distribution, contract types, feature profiles?) (b) What does the bid-level distribution look like — is it overwhelmingly level 1-2?
- Existing analysis: Notebook 45 S4 has bid-level histograms (covers question b). No notebook analyzes the pass population (question a is unaddressed).
- Action: Create a follow-up analysis task. Either add a "pass population profile" section to notebook 45 or a standalone analysis. This informs R1 model improvement priorities — if all passes are low-mu suit hands, that's different from passes spread across contract types.
- Decision: NOTED — track as task #31 (R1 analysis priority, not blocking v2 freeze)

**Finding R2-3: Remove Source B references — not used in rankings table**
- Problem: §3 preamble (lines 155-157) introduces a Source A/B distinction and §2.2 defines `std(net_pts)` as "Source B", but the actual rankings table has zero `^B` columns — every column is `^A`. This sets up an expectation that's never delivered.
- Fix: Remove the Source B concept from §3 preamble and drop `std(net_pts)` from §2.2 (or relabel it as available in notebook 45 only). Simplify the rankings table to just one source without A/B tagging.
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-2, 5-9: No issues found.**
- §1 Summary: Clear two-tier framing, version context
- §2 Methodology: Metric definitions table (Formula + Scope), limitations clearly stated
- §3 Rankings Table: Complete with CIs, notes on positive CVaR and 100% make_rate (Source B cleanup per R2-3)
- §5 Pairwise Significance: 7 pairs tested, 3 unresolved ties, cluster analysis
- §6 Behavioral Profiles: Thorough 8-bidder descriptions + expected vs observed
- §7 Key Observations: 7 quantitative observations
- §8 Auction-Pressure Sensitivity: Deferred with valid justification (H2H covers this)
- §9 Provenance: Complete (reproduction command fixed by R2-1)

---

### Cross-Cutting Finding: Report Numbering Scheme

**Finding X-1: Adopt per-rung numbered report filenames (Option B: category gaps)**
- Problem: 13+ report files in `docs/04_reports/r0/` have no implicit reading order or category distinction. A reader browsing the directory can't distinguish core analysis (promotion, comparator, H2H) from track decisions (lambda, threshold, normalizer) from governance (retrospective, methodology review).
- Fix: Rename all reports with numbered prefixes using category gaps:
  - **Core (01-09):** Reports directly supporting the promotion decision
    - `01_r0_promotion_report.md`, `02_model_arc_r0.md`, `03_comparator_rankings.md`, `04_r0_experiment_summary.md` (restructured from h2h_battery_analysis.md), `05_c33_ablation_report.md`, `06_dual_track_analysis.md`, `07_h2h_battery_analysis.md` (new, extracted from 04)
  - **Track decisions (10-19):** Per-track tuning outcomes
    - `10_contract_selection_oracle.md`, `11_pass_threshold_decision.md`, `12_lambda_decision.md`, `13_normalizer_offline_screen.md`, `14_onemodel_decision.md`
  - **Governance (20-29):** Process, methodology, retrospective
    - `20_measurement_integrity_r0.md`, `21_r0_retrospective.md`, `22_v1_v2_delta_review.md`, `23_phase0_to_r0_progression.md`
- Scope: Per-rung numbering (R1 gets its own 01-29 sequence). Cross-rung reports (dashboard) stay unnumbered outside `r0/`.
- Impact: Requires updating all inter-report cross-references (~50+ links across reports, notebooks, plans). Batch into the follow-up PR.
- Decision: ACCEPTED — include in follow-up PR

---

### Cross-Cutting Finding: Notebook-Only Analysis Anti-Pattern

**Finding X-2: Decision-critical analysis must not live only in notebooks**
- Problem: The Source B column issue in R2-3 revealed a broader pattern — analysis that influences modeling decisions or report claims may exist only in notebook outputs (which are gitignored and not reproducible without re-execution). If a notebook is the sole source of a metric, ranking, or adoption evaluation, that analysis is effectively unreproducible from committed state.
- Three-part fix:
  1. **Codify anti-pattern:** Add a rule to agent docs (`.claude/rules/`) and/or `CLAUDE.md` stating: *"Decision-critical analysis (metrics, rankings, adoption evaluations) must be reproducible from committed artifacts + scripts. Notebook outputs are exploratory supplements, not sources of truth for decisions."*
  2. **Audit existing notebooks:** Review all R0 notebooks (40, 45, 50, 55, 56, 57, 58, 59) to confirm no modeling decisions depend solely on notebook-only analysis not captured in reports or artifacts.
  3. **Extract if found:** If any decision-critical analysis lives only in notebooks, extract the results into committed artifacts or report sections.
- Timing: After HITL Q&A completes, before the notebook meta-review (task #30 → feeds into #27).
- Decision: ACCEPTED — track as task #30

---

### Report 3: h2h_battery_analysis.md

**Finding R3-1: Restructure into experiment summary + dedicated H2H report**
- Problem: The report covers 7 campaigns across 3 instruments (C33 ablation, comparator battery, H2H battery, plus threshold calibration). The title "H2H Battery Analysis" undersells ~60% of the content. §2 (C33) and §3 (Comparator) are summaries pointing to companion reports, but §4 (H2H full matrix) contains the full deep-dive — inconsistent depth.
- Fix:
  1. **Rename to `r0_experiment_summary.md`** (`04_r0_experiment_summary.md` under X-1). This becomes the "what did we run and what did we learn" evidence companion to the promotion report.
  2. **Extract §4 (H2H pairwise matrix, dominance structure, behavioral asymmetry) into a new `h2h_battery_analysis.md`** (`07_h2h_battery_analysis.md` under X-1). Same companion-report pattern as C33 and comparator.
  3. **Replace §4 in the experiment summary with a headline summary** — same depth as §2 and §3 (key results, link to companion). Include an **average H2H net_eppd_delta ranking table** (Option A) as the scannable summary: one row per bidder with avg delta, W/L/D record.
  4. **In the H2H companion report, include both ranking formats:**
     - **Option A (headline):** Average H2H delta ranking table (same as summary, for self-contained reading)
     - **Option C (detail):** Tier-based summary with per-bidder significant wins/losses/draws, preserving the partial-order and asymmetric-evidence structure
  5. **§5 (Gate Threshold Calibration) stays in the experiment summary** — it synthesizes across H2H data and feeds the promotion gate directly, so it belongs alongside the campaign overview rather than in the H2H detail report.
- Impact: One new report file, one restructured file, cross-reference updates.
- Decision: ACCEPTED — include in follow-up PR

**Finding R3-2: Reproduction commands use PYTHONPATH and CLI injection**
- Problem: §8 reproduction commands (lines 586–621) use `PYTHONPATH=src` (unnecessary with `uv run`) and the comparator command (lines 586–591) uses `--olsa-artifact`/`--bidder-class`/`--bidder-name` CLI injection pattern (same issue as R2-1, creates duplicate 9th bidder).
- Fix: Drop `PYTHONPATH=src` from all commands. Replace comparator command with config-pinned version (same fix as R2-1).
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-7: No issues found.**
- §1 What Was Done: Campaign inventory correct, bid_rate terminology fix (P6) present, methodology limitations thorough
- §2 C33 Ablation: Results, behavioral profile, v1-vs-v2 paradox well-explained, team-level breakouts included
- §3 Comparator Rankings: Summary matches companion report, 3-tier observation clear
- §4 H2H Full Matrix: Self-play sanity, dominance structure, pairwise matchups, behavioral asymmetry — comprehensive
- §5 Gate Threshold Calibration: Two-stage calibration, drift check, R1 implications — authoritative source
- §6 Artifact Inventory: Complete with schema versions and run directories
- §7 Conclusions: Seven numbered conclusions, all data-supported

---

### Report 4: c33_ablation_report.md

**Finding R4-1: Reproduction command uses `PYTHONPATH=src`**
- Problem: §11 reproduction command (line 481) uses `PYTHONPATH=src` prefix, unnecessary with `uv run`. Same class of issue as R2-1/R3-2.
- Fix: Drop `PYTHONPATH=src` from the command.
- Note: §9 Arc Context and §10 Companion Reports reference `h2h_battery_analysis.md` — will need updating when R3-1 rename executes.
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-10: No issues found.**
- Exec Summary: Clean 5-point structure (what/did/found/caveats/decision)
- §1 Motivation: v1-to-v2 context, three decisions informed, gate threshold cross-ref
- §2 Methodology: 4-cell design, paired deals, bootstrap CIs, P6 terminology fix
- §3 Architecture Comparison: Thorough side-by-side (decision mechanisms, behavioral, risk quantification)
- §4 Results: Self-play sanity, cross-matchups, v1-vs-v2, team breakout, per-contract
- §5 Component Decomposition: Strong analytical core — search vs wrapper from comparator data
- §6 Decision Divergence: Notebook 57 replay categories, calibration, interpretation
- §7-8 Interpretation & Decisions: Five findings, architecture validated
- §9 Arc Context: Clean timeline (needs R3-1 rename update)
- §10 Provenance: Complete

---

### Report 5: dual_track_analysis.md

**No issues found.**
- §1 Summary: Clean two-track framing, v4-to-v6 landscape shift
- §2 Dual-Track Rankings: Track definitions, both ranking tables, agreement/disagreement analysis with mechanism explanations (hybrid-vs-modelo reversal well-argued)
- §3 Archetype Classification: Criteria, SELECTIVE-dagger override justified, H2H by opponent archetype
- §4 Scatter Plots: Three plots (calibration, efficiency, conversion) with strong v6 observations. "Lesson has changed" insight in §4.2
- §5 Discussion: Exam-vs-tournament metaphor, 4 R1 implications, archetype overloading noted
- §6 Provenance: Complete (needs R3-1 rename cross-ref update)

---

### Report 6: contract_selection_oracle.md

**Finding R6-1: V1/V2 narrative interleaved rather than structured**
- Problem: §3.2 shows v1 decomposition table (pass-threshold 81.9%, CS 16.9%) as primary, with v2 numbers (CS 90.9%) introduced later in §3.6 as a bolt-on. §4 interpretation and §5 decisions still reference v1 framing ("calibrator addresses only 17%"). Since v2 supersedes v1 for decision-making, the report should lead with v2.
- Fix:
  1. Restructure §3 so v2 decomposition is primary (add v2 decomposition table), with v1 retained in a labeled comparison subsection
  2. Update §4 interpretation to lead with v2 context (CS regret 90.9% is the binding constraint)
  3. Update §5 decision reasoning to reflect v2 — the Path B decision is historically correct but the reasoning paragraph should note that v2 CS regret of 90.9% now makes the calibrator more relevant, though feature poverty remains the root cause
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-2, 6-8: No issues found.**
- Exec Summary: Good structure, v2 update context clear
- §1 Motivation: Contract distribution, oracle purpose, decision question
- §2 Methodology: Paired bidless design, construction path, v2 bid-level search, oracle definition, 3-way decomposition
- §6 Arc Context: Clean timeline
- §7 Provenance: Complete
- §8 Reproduction: Clean (no PYTHONPATH issue)

**Note: R1 follow-up updated.** P1 (HIGH/LOW feature enrichment) in `r1_follow_ups.md` updated with:
- v2 CS regret context (90.9%)
- Max 3 features per contract type constraint
- Per-feature ablation report requirement
- P3 (oracle re-analysis) updated with v2 decomposition numbers
- P4b added: per-contract H2H breakout of modelo vs hybrid (deferred to R1)

---

### Report 7: pass_threshold_decision.md

**Finding R7-1: Reproduction command uses `PYTHONPATH=src`**
- Problem: §7 provenance repro command (line 157) uses `PYTHONPATH=src` prefix, unnecessary with `uv run`. Same class as R2-1/R3-2/R4-1.
- Fix: Drop `PYTHONPATH=src`.
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-6: No issues found.**
- Exec Summary: RETAIN decision, monotonic decline table, v2 context well-integrated
- §1 Motivation: Oracle regret attribution, protocol reference
- §2 Methodology: Full spec (dataset, split, grid, guardrails, SESOI)
- §3 Results: 11-point sweep, guardrail disqualifications
- §4 Interpretation: Strong — model accuracy vs threshold calibration distinction
- §5 Decision: Clean criterion/result table
- §6 Implications: Four R1 implications including bid-level search interaction

---

### Report 8: lambda_decision.md

**Finding R8-1: H2H confirmation config is ephemeral**
- Problem: §8 reproduction command for H2H confirmation references `/tmp/lambda_h2h_confirmation.yaml` — a dynamically generated config that is not committed to the repo. The note acknowledges this ("generated dynamically by the sweep notebook") but it means the H2H confirmation step is not reproducible from committed state alone. Run ID is in provenance for result verification, but re-running requires regenerating the config via notebook 59. This is a moderate instance of X-2 (notebook-only analysis anti-pattern).
- Fix: Either (a) commit the H2H confirmation config to `experiments/configs/lambda_h2h_confirmation.yaml`, or (b) inline the matchup structure in the reproduction section so a reader can reconstruct the config without running notebook 59. Option (a) preferred — small YAML file, full reproducibility.
- Decision: ACCEPTED — include in follow-up PR

**Companion report cross-ref:** §8 references `h2h_battery_analysis.md` — needs R3-1 rename update.

**Sections 1-7: No issues found.**
- Exec Summary: RETAIN decision clearly stated, self-play vs H2H comparison table effective
- §1 Motivation: Utility formula defined, protocol reference, Track C dependency
- §2 Methodology: Two-phase design (self-play sweep + H2H confirmation), guardrail correction (v3 amendment) documented
- §3 Results — Self-Play: Full grid with CIs, guardrail pass/fail, epsilon-greedy selection rule
- §4 Results — H2H: Both rotations + paired average, auction dynamics (82% vs 18%), self-play diagnostics
- §5 Interpretation: Strong three-part structure — self-play reversal mechanism, screening tool value, model quality connection. Poker analogy apt.
- §6 Impact: Decision table, config surface impact, 4 R1 implications (CVaR validated, model quality, re-tune, joint optimization)
- §7 Provenance: Complete (sweep artifact, H2H run ID, seeds, bootstrap resamples)

---

### Report 9: normalizer_offline_screen.md

**Finding R9-1: Feature names incorrect in multiple places**
- Problem: The report uses `hybrid_r0.json` (OLSa constrained arm) per provenance §7, but feature names throughout the report match the *full* arm (hybrid_r0_full.json) instead. Specifically:
  - Exec summary (lines 38-39): Says HIGH and LOW both use `offsuit_non_ace_count` — wrong. Constrained arm uses `offsuit_aces` for HIGH and `offsuit_tens_count` for LOW.
  - §4 Interpretation (lines 181-184): Same error — "single feature each (`offsuit_non_ace_count`)"
  - §4 (line 183): Suit features listed as "trump suit count, off-ace count, offsuit non-ace count" — should be bowers, trump_count, offsuit_aces
  - Root cause: Likely confusion between the two arms — `offsuit_non_ace_count` IS a feature in the full arm's HIGH/LOW models, but not in the constrained arm.
- Fix: Correct all feature names to match `hybrid_r0.json`'s actual model specification (constrained arm):
  - Suit: bowers, trump_count, offsuit_aces (3 features)
  - HIGH: offsuit_aces (1 feature)
  - LOW: offsuit_tens_count (1 feature)
- Decision: ACCEPTED — include in follow-up PR

**Finding R9-2: Metric labeling inconsistent with other reports**
- Problem: The exec summary table uses "Net EPPD" (capitalized, spaced) while all other reports use `net_eppd` (lowercase, underscored). §3.3 uses "Net EPPD (mean actual_net)" which conflates metric name with computation method. §5 GO/NO_GO tables use `delta_net_eppd` and `accuracy_lift` — different naming again. This inconsistency makes it harder to cross-reference metrics across the report suite.
- Fix: Standardize to `net_eppd` and `accuracy` (or `oracle_accuracy`) throughout. Use computation notes in methodology (§2), not in metric labels.
- Decision: ACCEPTED — include in follow-up PR

**Finding R9-3: Regret decomposition table incomplete — pass threshold and bid level shares missing**
- Problem: §1 Motivation table (lines 46-51) shows CS regret at 90.9% but pass threshold and bid level shares are dashes ("—"). The full v2 decomposition from nb55 exists and should be reported. Without the other components: (a) reader can't verify shares sum to ~100%, (b) relative magnitude of non-CS regret is hidden, (c) inconsistent with the oracle report (Report 6, §3.6) which reports the full decomposition.
- Fix: Fill in the actual v2 pass-threshold and bid-level regret shares from nb55 v2 output.
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-8: No other issues found (beyond R9-1/R9-2/R9-3 above).**
- Exec Summary: Strong "model poverty, not miscalibration" framing (feature names fixed by R9-1, metric labels fixed by R9-2)
- §1 Motivation: Two failure modes (miscalibration vs model poverty) cleanly distinguished, trigger threshold, protocol + spec references (decomposition fixed by R9-3)
- §2 Methodology: Affine design (3 families, 6 params), softmax NLL, L-BFGS-B, evaluation metrics
- §3 Results: Diagnostic zero (65.2% disagreement, gap distribution), fitted parameters (all alphas at lower bound 0.5), validation (accuracy +4%, net_eppd -0.269, CI excludes 0 wrong direction), pass-decision shift (+1,042 net bidders, guardrail fail)
- §4 Interpretation: Three-signal model poverty diagnosis (alphas, disagreement, accuracy-net_eppd divergence), overestimate caveat for offline replay
- §5 Impact: Clear GO/NO_GO tables, R0 implications (no integration), R1 implications (3 priorities)
- §6 Arc Context: Clean timeline
- §7 Provenance: Complete (artifact path, schema, script, git SHA, seed, n_deals, n_hands, n_bootstrap)
- §8 Reproduction: Clean (uses `uv run`, all parameters explicit, no PYTHONPATH)

---

### Report 10: model_arc_r0.md

*(See below for findings)*



**Finding R10-1: Reproduction commands use `PYTHONPATH=src`**
- Problem: Both reproduction commands (lines 535, 546) use `PYTHONPATH=src` prefix, unnecessary with `uv run`. Same class as R2-1/R3-2/R4-1/R7-1.
- Fix: Drop `PYTHONPATH=src` from both commands.
- Decision: ACCEPTED — include in follow-up PR

**Finding R10-2: Comparator table has empty cells for ranks 4-8**
- Problem: The comparator battery table (lines 390-399) has `bid_rate` and `make_rate` columns populated for ranks 1-3 (hybrid_olsa_full, hybrid_olsa, modeloespecifico) but blank for ranks 4-8 (stricthellraiser through rankthetank). The data exists in `comparator_cis_r0_v6.json`. Missing cells suggest intentional omission rather than unavailable data, which is worse than no column at all.
- Fix: Populate all rows from comparator data. If behavioral metrics aren't meaningful for some bidders (e.g., rankthetank), add a footnote rather than leaving cells empty.
- Decision: ACCEPTED — include in follow-up PR

**Finding R10-3: "Key H2H Matchups" section only reports self-play**
- Problem: §Key H2H Matchups (line 416) title promises pairwise matchups but content is only self-play diagnostics (delta=−0.048, fullgame_eppd=4.894). A reader expects to see competitive matchups (e.g., hybrid_olsa vs modelo, vs stricthellraiser) under this heading.
- Fix: Either (a) add 2-3 key pairwise matchup summaries from H2H v4 data (hybrid_olsa vs top competitors), or (b) retitle to "H2H Self-Play Baseline" and add a sentence pointing to the companion report for pairwise results.
- Decision: ACCEPTED — include in follow-up PR

**Finding R10-4: Auction plumbing correctness not cited in report**
- Problem: The model spec report discusses auction health (contract mix, bid distributions) but doesn't cite the test suite as evidence that auction mechanics work correctly. The test suite covers bidding rules (`test_auction_bidding_rules.py`), sequential semantics (`test_bidding_sequential_semantics.py`), rules invariants (`test_rules_invariants.py` — bower ordering, follow-suit, LOW reversal), repeatability (`test_auction_repeatability.py`), and statistical properties (`test_simulation_validation.py` — tricks sum to 10, team averages in [4,6]). The dumb bidders exercise these paths implicitly. This is adequately tested but not documented in the report.
- Fix: Add a brief "Auction Plumbing Validation" subsection to the Auction Analysis section citing the 5 test files and noting that the comparator battery (including dumb bidders) runs through the full pipeline as an implicit integration test.
- Decision: ACCEPTED — include in follow-up PR

**Companion report cross-refs:** Lines 60 and 420 reference `h2h_battery_analysis.md` — needs R3-1 rename update.

**Sections 1-11: No other issues found.**
- Exec Summary: 5-part format (what/did/found/caveats/decision), companion report list comprehensive
- Data Inventory: Deals (31,612), rows (126,448), per-contract counts verified (sum checks out)
- Feature Health: 39 features clean, seat balance tight (max dev 0.58), per-contract top-5 stats
- Outcome Health: Mean tricks 5.00 (unbiased), sample size warning for HIGH/LOW present
- Auction Analysis: Contract selection frequency, bid distribution, feature names correct (offsuit_aces/offsuit_tens_count)
- Model Spec: Dual-arm design explained, both arms' features + coefficients + biases complete
- Model Performance: R² 0.24-0.29, MAE, good interpretive context (theoretical ceiling, variance)
- Attribution Gap: -0.1437, explanation cross-refs promotion report
- Feature Correlations: Top 5 by |r| per contract type, useful R1 reference
- Semantic Gate: 4 Tier 1 checks PASS
- Known Limitations: 6 well-stated points with companion report cross-references

---

### Report 11: measurement_integrity_r0.md

**Finding R11-1: Normalizer screen script path is wrong**
- Problem: Evaluation batteries table (line 23) lists "Notebook 59" as the script path for the normalizer screen. Notebook 59 is `59_lambda_simulation_sweep.py` (lambda analysis). The actual normalizer screen script is `scripts/internal/run_normalizer_offline_screen.py` (per Report 9 provenance).
- Fix: Correct script path to `scripts/internal/run_normalizer_offline_screen.py`.
- Decision: ACCEPTED — include in follow-up PR

**Finding R11-2: Evaluation batteries table is incomplete**
- Problem: Table lists 5 instruments but omits several major ones that feed into the promotion decision:
  - C33 ablation (3-arm, 90k deals, `arc_d_r0_c33_ablation.yaml`)
  - Eval dataset (50k deals × 3 seeds — foundation for promotion gate metrics)
  - Pass-threshold sweep (nb56, 10k deals)
  - Contract selection oracle (nb55, offline analysis)
  - OneModel comparison (Track F, 5k deals)
- For a measurement integrity review, the instrument inventory should be comprehensive.
- Fix: Add missing instruments to the batteries table with script path, deal count, seed, and version.
- Decision: ACCEPTED — include in follow-up PR

**Finding R11-3: L3 category mismatch (a) vs "B-L3" prefix**
- Problem: The limitations table classifies L3 (bid_rate conflation) as category (a), but the deferral cost section uses "B-L3" prefix implying category (b). The text says the H2H residual is "an inherent property of the H2H estimand, not a methodology defect" — which is (a)-class by definition. But having a B- deferral cost section contradicts this classification.
- Fix: Either (a) reclassify L3 as (b) since the comparator version was a real defect that was fixed, and the H2H residual is a partial deferral; or (b) keep L3 as (a) and move the "PARTIALLY RESOLVED" discussion into the L3 row notes, removing the B-L3 deferral cost section. Recommend option (a) — L3 was genuinely (b) for the comparator, partially resolved, with the H2H residual remaining as an acknowledged limitation.
- Decision: ACCEPTED — include in follow-up PR

**Sections: No other issues found.**
- Header: Standard fields, gate_status PROMOTED
- Limitations L1-L7: L1/L2 resolved, L3 partially resolved (category fixed by R11-3), L4 GluttonStrategy acknowledged, L5 pairwise-not-round-robin accepted, L6/L7 new v2 (a)-class items well-documented
- Deferral Costs: L1/L2 resolved with historical three-dimension costs retained, L3 residual explained
- Blockers: None (no (c)-class items)
- V2 Update Notes: Two new instruments + two new (a)-class limitations, CS regret 90.9%
- Sign-off: 6-item checklist complete

---

### Report 12: r0_retrospective.md

**No issues found.**
- Exec Summary: Five actionable lessons with PR evidence
- §1 Scope: 7 phases, 112 PRs, PR type distribution, velocity curve
- §2 What Worked: Design-first planning, convention-first, batch review, quality gates, parallel tracks
- §3 What Didn't Work: JSONL redesign chain, comparator v1→v6 iterations, notebook review debt, parser bugs
- §4 Process Patterns: Fix clustering (75% within 24h), plan→implementation chains, fail-safe gates, convention codification
- §4b V2 Lessons: Bid-level search impact, lambda reversal, normalizer accuracy-vs-value, pre-registered protocols
- §5 R1 Recommendations: Six actionable items tied to R0 lessons
- §6 Provenance: Complete

---

### Report 13: v1_v2_delta_review.md

**Finding R13-1: Pass-threshold v2 regret share is approximate**
- Problem: §6.1 regret decomposition table (line 241) shows "~5% (implied)" for the v2 pass-threshold regret share instead of the exact value from nb55 v2. For a systematic delta review, approximate implied values when exact numbers exist is imprecise. Same class as R9-3 (normalizer report had dashes for the same data).
- Fix: Replace "~5% (implied)" with the exact v2 pass-threshold and bid-level regret shares from nb55 v2 output.
- Decision: ACCEPTED — include in follow-up PR

**Sections 1-10: No other issues found.**
- Exec Summary: Root cause identified, 4 change categories quantified
- §1 What Changed: Code changes (5 PRs), battery changes, decision outcomes, explicit unchanged list
- §2 Comparator Rankings: Full v1→v2 ranking table with deltas/flags, behavioral profile, CVaR sign reversal, pairwise significance
- §3 H2H Battery: Key matchup deltas, self-play sanity (rankthetank resolved), fullgame_eppd, dominance structure
- §4 C33 Ablation: Scope change, core results, component decomposition, paradox explained, gate context reversal flagged
- §5 Dual-Track: Track agreement breakdown, archetype reclassification (SELECTIVE→empty), R1 target shift
- §6 Oracle & Pass-Threshold: Claim reversal documented (pass-threshold 81.9%→~5%, CS 16.9%→90.9%), threshold unchanged
- §7 New Reports: Lambda and normalizer summaries clean
- §8 Promotion & Model Spec: Itemized changes, identical gate status
- §9 Cross-Report Consistency: 3 sign reversals (all explained), 3 lost significances (mid-tier), 3 verdict changes, 7 new claims (all data-supported)
- §10 Assessment: All deltas trace to bid-level search, no invalidated conclusions, 3 HITL attention items

---

## Review Complete

**All 13 reports reviewed.** Summary of findings:

| Report | Findings | Key Issues |
|--------|----------|------------|
| 1. r0_promotion_report | R1-1 through R1-5 | Metric context mixing, gate context, metric definitions, pooling justification, model spec comparison |
| 2. comparator_rankings | R2-1, R2-2, R2-3 | CLI injection repro, deferred contract-type section, Source B cleanup |
| 3. h2h_battery_analysis | R3-1, R3-2 | Restructure into experiment summary + H2H companion, PYTHONPATH/CLI injection |
| 4. c33_ablation_report | R4-1 | PYTHONPATH in repro |
| 5. dual_track_analysis | (clean) | — |
| 6. contract_selection_oracle | R6-1 | V1/V2 narrative interleaving |
| 7. pass_threshold_decision | R7-1 | PYTHONPATH in repro |
| 8. lambda_decision | R8-1 | Ephemeral H2H config |
| 9. normalizer_offline_screen | R9-1, R9-2, R9-3 | Wrong feature names, metric labeling, incomplete regret decomposition |
| 10. model_arc_r0 | R10-1 through R10-4 | PYTHONPATH, empty comparator cells, H2H section title, auction plumbing citation |
| 11. measurement_integrity_r0 | R11-1, R11-2, R11-3 | Wrong script path, incomplete batteries table, L3 category mismatch |
| 12. r0_retrospective | (clean) | — |
| 13. v1_v2_delta_review | R13-1 | Approximate regret share |

**Cross-cutting findings:**
- X-1: Report numbering scheme (accepted)
- X-2: Notebook-only analysis anti-pattern (accepted, task #30)
- X-3: Absolute vs differential metric clarity (accepted, see below)

---

### Cross-Cutting Finding: Absolute vs Differential Metric Clarity

**Finding X-3: Reports inconsistently distinguish absolute vs differential metrics**
- Problem: The report suite uses several "eppd" metrics that look similar but measure fundamentally different things:
  - `net_eppd` (comparator): differential vs always-pass sentinels (single-seat)
  - `net_eppd` (eval): differential in self-play where both teams bid
  - `fullgame_eppd` (H2H): **absolute** scoring rate per deal (NOT a differential)
  - `delta` (H2H): differential between two bidders in contested auction
  - `eppd` (eval): absolute bidder points per deal
  A reader seeing `fullgame_eppd = 4.894` alongside `net_eppd = +2.131` could reasonably assume both are differentials — but one is absolute and one is net. This confusion is compounded by R1-3 (missing metric definitions) and R9-2 (inconsistent labeling).
- Fix: Extend R1-3's metric definition tables to explicitly tag each metric as **absolute** or **differential** and note the instrument context (comparator/eval/H2H). Ensure every table that reports an eppd-family metric labels whether it's absolute or net.
- Decision: ACCEPTED — subsumes into R1-3 metric definition work in follow-up PR

---

**Totals:** 25 findings across 11 reports. 2 reports clean. 3 cross-cutting findings.
