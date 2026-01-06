# Anti-Patterns and Prevention Guide

**Created:** 2026-01-04
**Purpose:** Document common mistakes and how to prevent them

This document catalogs **recurring problems** identified during cleanup and establishes **guardrails** to prevent them in the future.

---

## 🚨 **Recurring Anti-Patterns**

### 1. Hardcoding Parameters in Python Scripts

**❌ Bad Example:**
```python
# train_model.py
features = ['trump_count', 'trump_rb_count', 'is_bidder']  # HARDCODED!
n_hands = 50000  # HARDCODED!
```

**✅ Good Example:**
```python
# train_model.py
config = load_config(args.config)
features = config['features']['suit']
n_hands = config['parameters']['n_hands']
```

**Why it matters:**
- Can't reproduce experiments without editing code
- Changes require code commits, not just config updates
- Hard to track what parameters produced which results

**How to prevent:**
- ✅ Create config file FIRST
- ✅ Use `--config` argument in all experiment scripts
- ✅ Add to checklist in `CONTRIBUTING.md`

---

### 2. Manual `sys.path` Manipulation

**❌ Bad Example:**
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bid_euchre.sim import simulation
```

**Occurred in:** 11 different scripts before cleanup

**✅ Good Example:**
```python
# No sys.path needed!
from bid_euchre.sim import simulation
```

**Why it matters:**
- Boilerplate in every script
- Error-prone (wrong paths)
- Harder to read

**How to prevent:**
- ✅ Use `experiments/__init__.py` for automatic path setup
- ✅ Document in `CONTRIBUTING.md`
- ✅ Check in pre-commit hook

---

### 3. Inline Training via Shell Heredoc

**❌ Bad Example:**
```bash
python << 'EOF'
import pickle
# 100 lines of training code...
pickle.dump(model, f)
EOF
```

**Occurred:** During OLSa_v2 initial training (2026-01-04)

**✅ Good Example:**
```bash
PYTHONPATH=src python experiments/training/train_bidder_models.py \
  --config experiments/configs/train_bidder_models.yaml
```

**Why it matters:**
- Can't be version controlled properly
- No error handling
- No progress tracking
- Not reproducible

**How to prevent:**
- ✅ Always use proper Python scripts
- ✅ Pre-commit hook to detect heredoc training
- ✅ Reject PRs with inline training

---

### 4. Model Format Inconsistency

**❌ Bad Example:**
```python
# Saving raw model
pickle.dump(model, f)
```

**Occurred:** OLSa_v2 initial training, causing `TypeError: 'SimpleOLS' object is not subscriptable`

**✅ Good Example:**
```python
from bid_euchre.utils import save_model

save_model(
    model=model,
    features=['trump_count', 'is_bidder'],
    contract_type='suit',
    path='data/models/current/my_model/suit.pkl'
)
```

**Why it matters:**
- `RegressionBidder` expects dict format
- Legacy models incompatible with new code
- Hard to inspect model metadata

**How to prevent:**
- ✅ Use `model_io.save_model()` exclusively
- ✅ Document in `CONTRIBUTING.md`
- ✅ Add validation in model loading

---

### 5. Missing Config Files for Experiments

**❌ Bad Example:**
```python
# Script created first, config added later (or never)
```

**Occurred:** `train_bidder_aware_models.py` had no config initially

**✅ Good Example:**
1. Create `experiments/configs/train_bidder_models.yaml` FIRST
2. Then create training script that uses it

**Why it matters:**
- Can't reproduce without reverse-engineering code
- Parameters scattered across codebase
- No single source of truth

**How to prevent:**
- ✅ Config-first development workflow
- ✅ Pre-commit hook checks for corresponding config
- ✅ Reject scripts without configs in code review

---

### 6. Experiment Script Explosion

**❌ Bad Pattern:**
- Create new script for every slight variation
- End up with 50+ scripts in flat directory
- Hard to find anything

**Occurred:** 50 experiment scripts before reorganization

**✅ Good Pattern:**
- Use unified `run_experiment.py` with YAML configs when possible
- Organize remaining scripts by function
- Consolidate similar scripts

**Why it matters:**
- Cognitive overload
- Duplicate code
- Maintenance nightmare

**How to prevent:**
- ✅ Ask: "Can `run_experiment.py` do this?"
- ✅ Organize by function (analysis/, dashboards/, etc.)
- ✅ Periodic audits: "Are these scripts duplicates?"

---

### 7. No Tests for New Models

**❌ Bad Pattern:**
- Train model
- Declare "production ready"
- Never test in simulation

**Occurred:** OLSa_v2 trained without tests initially

**✅ Good Pattern:**
1. Train model
2. Write unit tests (`tests/unit/test_*_models.py`)
3. Write integration tests (`tests/integration/test_*_integration.py`)
4. Run head-to-head validation
5. THEN declare production ready

**Why it matters:**
- Models may not work in simulation
- Silent failures
- No confidence in results

**How to prevent:**
- ✅ Testing checklist in `CONTRIBUTING.md`
- ✅ Require tests before marking "production"
- ✅ CI/CD runs tests automatically

---

### 8. Leaving Backup Files in Repo

**❌ Bad Pattern:**
```
generate_dashboard.py
generate_dashboard.py.bak
generate_dashboard.py.bak2
__init__.py.bak
```

**Occurred:** 2 backup files found during cleanup

**✅ Good Pattern:**
- Use git for backups, not `.bak` files
- Clean up as you go

**Why it matters:**
- Clutter
- Confusing which is current
- Accidentally import wrong version

**How to prevent:**
- ✅ Add `*.bak*` to `.gitignore`
- ✅ Use git branches for experiments
- ✅ Clean up before commits

---

### 9. Deprecated Scripts in Main Folders

**❌ Bad Pattern:**
- Old scripts stay in main folder with "old" prefix
- No clear indication what's current
- Fear of deleting anything

**Occurred:** Scripts from Dec 2025 mixed with Jan 2026 scripts

**✅ Good Pattern:**
- Move to `_deprecated/` with README explaining why
- Clear separation: active vs historical
- Can always recover from git history

**Why it matters:**
- Confusion about what's current
- Accidental use of old code
- Can't find relevant scripts

**How to prevent:**
- ✅ Proactive deprecation when superseded
- ✅ Document in `_deprecated/README.md`
- ✅ Quarterly audits

---

### 10. Missing Data Lineage

**❌ Bad Pattern:**
- Model exists in `data/models/`
- No record of which training run produced it
- Can't reproduce

**Occurred:** Multiple model directories with unclear provenance

**✅ Good Pattern:**
```python
# In model metadata
metadata = {
    'training_data': 'data/training/bidder_aware_train.csv',
    'config': 'experiments/configs/train_bidder_models.yaml',
    'timestamp': '2026-01-04T00:15:00',
    'git_commit': 'b574432',
}
save_model(..., metadata=metadata)
```

**Why it matters:**
- Can't audit model quality
- Can't reproduce
- Can't debug issues

**How to prevent:**
- ✅ Use `model_io.save_model()` with metadata
- ✅ Document in model README
- ✅ Include config with model outputs

---

## ✅ **Prevention Checklist**

Use this before committing experiment changes:

### Before Creating New Experiment
- [ ] Checked if `run_experiment.py` can handle this
- [ ] Created YAML config file FIRST
- [ ] Added entry to `experiments/REGISTRY.yaml`
- [ ] Chose correct subdirectory (analysis/dashboards/etc)

### Before Committing
- [ ] No hardcoded parameters in Python
- [ ] No `sys.path.insert()` in experiment scripts
- [ ] No inline training via heredoc
- [ ] Used `model_io.save_model()` for models
- [ ] Wrote integration test
- [ ] No `.bak` or backup files
- [ ] Updated relevant documentation

### After Training Models
- [ ] Saved with metadata (training data, config, timestamp)
- [ ] Updated `data/models/README.md`
- [ ] Wrote unit tests
- [ ] Wrote integration tests
- [ ] Ran validation comparison
- [ ] Documented performance in `docs/BIDDER_MODELS.md`

---

## 🔧 **Automated Checks (TODO)**

These checks should be added to pre-commit hooks:

### `scripts/hooks/check_experiment_standards.sh`
```bash
#!/bin/bash
# Check for hardcoded parameters
if git diff --cached | grep -E "n_hands.*=.*[0-9]|seed.*=.*[0-9]" experiments/*.py; then
    echo "❌ Hardcoded parameters detected. Use config files."
    exit 1
fi

# Check for sys.path manipulation
if git diff --cached | grep "sys.path.insert" experiments/*.py; then
    echo "❌ Manual sys.path detected. Remove it (handled by __init__.py)"
    exit 1
fi

# Check for backup files
if git diff --cached --name-only | grep -E "\.bak|_old\.|_backup\."; then
    echo "❌ Backup files detected. Clean them up."
    exit 1
fi
```

---

## 📚 **Learning from History**

### Timeline of Issues
1. **Dec 2025:** Script explosion (50+ in flat directory)
2. **Dec 2025:** No test coverage for models
3. **Jan 2026:** Hardcoded training parameters
4. **Jan 2026:** Model format inconsistency bug
5. **Jan 2026:** Inline training workaround
6. **Jan 2026:** Comprehensive cleanup ✅

### What Worked
- ✅ Experiment registry (REGISTRY.yaml)
- ✅ Config-driven development
- ✅ Organized folder structure
- ✅ Comprehensive testing
- ✅ Proactive deprecation

---

**Remember:** These patterns emerged from real issues. The guardrails exist because we've already made these mistakes. Don't repeat them!

---

## Questions?

- Standards: See `docs/CONTRIBUTING.md`
- Structure: See `docs/FOLDER_STRUCTURE.md`
- Examples: See `experiments/REGISTRY.yaml`
