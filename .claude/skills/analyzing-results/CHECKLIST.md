# Statistical Rigor Checklist

Before claiming analysis is "done", verify every applicable item.

Derived from `.claude/rules/deferred/05_rigor.md` gold standard.

## Sample Size

- [ ] Sample size justified (power analysis or minimum threshold from metrics table)
- [ ] N ≥ 2,000 for bias detection (seat/suit)
- [ ] N ≥ 1,000 per group for feature correlation
- [ ] N ≥ 5,000 for tail analysis (CDF/CCDF)
- [ ] N ≥ 50,000 for production reports

## Balance & Randomization

- [ ] All relevant factors balanced/randomized (seat, trump suit, contract type)
- [ ] No hardcoded values masking variation (e.g., always trump='H')
- [ ] Seat balance verified: equal counts per seat
- [ ] Contract type distribution checked

## Statistical Tests

- [ ] Hypothesis test included (ANOVA, t-test, chi-square as appropriate)
- [ ] p-values reported with test statistic
- [ ] Confidence intervals computed (bootstrap or parametric)
- [ ] Effect sizes included (R², Cohen's d — not just p-values)
- [ ] Multiple comparison corrections applied if testing >3 hypotheses

## Validation Gates

- [ ] Assert-style sanity checks in place (fail-fast, not silent)
- [ ] Expected data properties verified (row counts, value ranges, completeness)
- [ ] Self-play sanity: mean tricks ≈ 5.0 per seat

## Traceability

- [ ] Results captured in committed artifacts (JSON/CSV), not just notebook outputs
- [ ] Reproduction command with seed documented
- [ ] Confounders identified and controlled (or explicitly noted as limitations)
- [ ] Limitations explicitly stated

## Anti-Patterns — Do NOT

- Accept "looks balanced" without ANOVA/chi-square test
- Treat N=200 as sufficient for distribution claims
- Use "seat 0 for simplicity" when seat effects matter
- Hardcode configuration values (trumps, contracts, seats)
- Present correlation as feature importance without caveat
- Run experiments without pre-specified success criteria
