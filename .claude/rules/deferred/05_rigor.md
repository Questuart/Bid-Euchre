# Rigor & Correctness Philosophy

> **Core principle:** This repo prioritizes technical correctness and statistical rigor over accessibility, convenience, or ease of explanation.

## Analysis Standards

### Sample Size Requirements

- **Flag inadequate sample sizes as critical blockers**, not "potential improvements"
- Minimum thresholds for statistical inference:
  - Bias detection (seat/suit): ≥2,000 deals
  - Feature correlation: ≥1,000 samples per group
  - Tail analysis (CDF/CCDF): ≥5,000 samples
  - Production reports: ≥50,000 samples
- N=100-200 is acceptable only for "does it run" smoke tests

### Statistical Validation

**Required for any inference claim:**
- Hypothesis tests with p-values (ANOVA, t-tests)
- Confidence intervals (bootstrap or parametric)
- Effect sizes (R², Cohen's d, not just p-values)
- Multiple comparison corrections when appropriate

**Bad:**
```python
# Visual inspection only
plt.boxplot([seat0_data, seat1_data, seat2_data, seat3_data])
# "Looks balanced to me"
```

**Good:**
```python
# Statistical test + visual
f_stat, p_value = f_oneway(seat0_data, seat1_data, seat2_data, seat3_data)
assert p_value > 0.05, f"Seat bias detected: p={p_value:.4f}"
plt.boxplot([seat0_data, seat1_data, seat2_data, seat3_data])
plt.title(f"Seat Balance Check (ANOVA p={p_value:.3f})")
```

### Fail-Fast Validation

**Use assert-style sanity gates in notebooks and pipelines:**

```python
# Assert expected data properties
assert len(df) == n_deals * n_seats * n_contracts
assert df.groupby('seat').size().nunique() == 1  # Equal seat counts
assert df['tricks_won'].between(0, 10).all()

# Assert statistical properties
mean_self_play = self_play_df['tricks_won'].mean()
assert 4.8 < mean_self_play < 5.2, f"Self-play bias: {mean_self_play:.2f}"
```

Gates should fail loud and early, not produce silent bad data.

## Code Review Priority Order

When reviewing code, notebooks, or experimental designs:

1. **Correctness** — logic bugs, edge cases, statistical validity, confounders
2. **Reproducibility** — seeds, determinism, data contracts
3. **Performance** — efficiency, scalability, resource usage
4. **Accessibility** — explanations, documentation, learning aids

### Examples

**Correctness > Accessibility:**
- Catch "seat 0 only for simplicity" if it defeats bias checks
- Flag hardcoded values that could mask variation (e.g., always trump='H')
- Identify when heuristics are treated as ground truth (correlation ≠ causation)

**Correctness > Convenience:**
- Demand parameterization (seeds, sample sizes) even for "quick demos"
- Require CI/CD-compatible validation even if "we'll just eyeball it"
- Insist on statistical power calculations before running experiments

## What This Means in Practice

### For Analysis & Notebooks

- Lead with confounder identification (sample size, hardcoded values, bias)
- Require statistical tests, not just visual inspection
- Treat exploratory analysis as hypothesis-generating, not hypothesis-testing
- Cache/version generated data to ensure reproducibility

### For Experimental Design

- Specify sample size requirements upfront (power analysis)
- Randomize/balance across all relevant factors (seat, trump, contract)
- Define success/failure criteria with thresholds before running
- Plan for multiple comparison corrections if testing many hypotheses

### For Code Review

- Correctness critiques come first, even if they're "nitpicky"
- Statistical issues are blockers, not suggestions
- Simplified/demo code must be clearly labeled as non-production
- Production code must have validation gates

### For Communication

- Explanatory insights are valuable but secondary to technical accuracy
- When in doubt, favor precision over simplicity
- Call out assumptions, limitations, and caveats explicitly
- Don't say "this looks good" without quantitative backing

## Anti-Patterns to Avoid

❌ Accepting "looks balanced" without ANOVA/chi-square test
❌ Treating 200 samples as sufficient for distribution claims
❌ Using "seat 0 for simplicity" when seat effects matter
❌ Hardcoding configuration values (trumps, contracts, seats)
❌ Presenting correlation as feature importance without caveat
❌ Visual-only validation in production pipelines
❌ Missing confidence intervals on reported metrics
❌ Running experiments without pre-specified success criteria

## Gold Standard Checklist

Before claiming analysis is "done":

- [ ] Sample size justified (power analysis or heuristic threshold)
- [ ] All relevant factors balanced/randomized (seat, trump, contract)
- [ ] Statistical tests included (not just visual inspection)
- [ ] Confidence intervals on key metrics
- [ ] Sanity gates/asserts pass
- [ ] Confounders identified and controlled
- [ ] Reproducible (seeds, cached data, versioned)
- [ ] Limitations explicitly stated

---

**Bottom line:** If it's not statistically defensible, it's not done. Rigor first, accessibility second.

See also @.claude/rules/deferred/35_integrity.md for deferral cost analysis requirements
when recommending deferral of methodology defects.
