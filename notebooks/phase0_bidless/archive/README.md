# Archived Phase 0 Notebooks

This directory contains notebooks that have been superseded by the refactored phase0 structure.

## Archived Notebooks

### 20_charts_reference.ipynb
**Archived:** 2026-02-01
**Reason:** Superseded by focused analysis notebooks (20_outcome_health_checks.ipynb, 30_feature_outcome_eval.ipynb)

**Original purpose:** Comprehensive analysis notebook with all diagnostic charts, production-quality reports, and multi-phase analysis workflow.

**Why archived:** This was a monolithic "kitchen sink" notebook that tried to do everything. The new structure splits this into:
- `20_outcome_health_checks.ipynb` - Focused outcome validation with fail-fast tests
- `30_feature_outcome_eval.ipynb` - Feature-outcome correlation analysis

**Restoration:** If you need the comprehensive chart reference, this notebook can still be run but may require updates to work with the new `load_or_generate_*()` functions.

---

### 30_model_dev_and_eval.ipynb
**Archived:** 2026-02-01
**Reason:** Replaced by improved feature-outcome analysis notebook

**Original purpose:** Template for custom exploratory analysis and model development.

**Why archived:** This was an early template that predated the `diagnostics` module helpers. The new `30_feature_outcome_eval.ipynb` provides a better starting point with:
- Proper use of `load_or_generate_features()`
- Statistical rigor (ANOVA, correlation tests, bootstrap CIs)
- Contract-type segregated analysis
- Built on tested diagnostic utilities

**Restoration:** For custom exploration, copy `30_feature_outcome_eval.ipynb` instead of using this archived template.

---

## Retrieval

If you need to restore or reference these notebooks:

```bash
# View archived notebook
git show HEAD:notebooks/phase0_bidless/archive/20_charts_reference.ipynb

# Copy to sandbox for modification
cp notebooks/phase0_bidless/archive/20_charts_reference.ipynb \
   notebooks/sandbox/$(date +%Y_%m_%d)_charts_exploration.ipynb
```

## See Also

- **Current notebooks:** `../README.md` - Updated workflow documentation
- **Refactoring context:** PR #185 - Phase 0 notebook refactoring
