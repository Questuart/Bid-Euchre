# Measurement Integrity — Deferral Cost Analysis

> Subordinate to `05_rigor.md`. Rigor-policy blockers (sample size, missing CIs,
> missing statistical tests) are always immediate — never deferred.

## When This Rule Applies

**Concrete triggers** — a defect affects:
- Metric definitions (how net_eppd, CVaR, bid_rate are computed)
- Sampling design (deal generation, seat/contract balance, self-play structure)
- Uncertainty estimates (bootstrap CIs, p-values, effect sizes)
- Promotion decision inputs (gate thresholds, comparator rankings, H2H deltas)

**Does NOT apply to:**
- Code quality issues (naming, refactoring, style)
- Rigor-policy blockers (always immediate per `05_rigor.md`)
- Feature requests unrelated to evaluation methodology
- Documentation wording or formatting

## Required Analysis

When recommending deferral of a methodology defect, provide three cost
dimensions:

1. **Fix-now:** PRs, experiment reruns, delay to current rung
2. **Fix-later + compounding:** Same fix cost, plus crosswalk/recalibration
   costs that accumulate per rung of deferral
3. **Never-fix:** Long-term impact on metric validity and decision quality

Present all three to the human decision-maker. Do not pre-decide.

## Scope Containment

If a methodology defect is discovered on an **unrelated PR**:
- Note the defect and its category (a/b/c)
- Recommend a follow-up issue or PR
- Do **not** expand the current PR scope to fix it

## Anti-Patterns

- **Deferral by file count:** "Only 2-3 PRs to fix" is not a cost analysis.
  Include experiment rerun costs, crosswalk complexity, and compounding.
- **COMPLETE = endorsement:** Marking a rung PROMOTED or ADVANCED does not
  mean the methodology is endorsed as ideal. It means (c) blockers are clear
  and (b) items have explicit cost descriptions.
- **Immediate-cost-only analysis:** Presenting only fix-now costs without
  fix-later compounding biases toward deferral. Always present all three.
- **Deferring rigor blockers:** `05_rigor.md` items (sample size, missing CIs,
  missing statistical tests) are always category (c). They cannot be deferred
  regardless of cost analysis.

## Filing Convention

Measurement integrity reviews are filed at:
`docs/04_reports/<rung>/measurement_integrity_<rung>.md`

See `docs/02_agent/MEASUREMENT_INTEGRITY_REVIEW.md` for the template.
