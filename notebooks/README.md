# Notebooks Directory

**Purpose:** Exploratory analysis and visualization for Arc B development.

---

## Directory Structure

```
notebooks/
├── phase0_bidless/  - Phase 0 (bidless) hand analysis & diagnostics
│   ├── README.md                      # Phase 0 golden path guide
│   ├── 10_health_checks.ipynb         # Quick dataset validation
│   ├── 20_charts_reference.ipynb      # Comprehensive reference
│   └── 30_model_dev_and_eval.ipynb    # Exploratory template
├── sandbox/         - Exploratory notebooks (dated, ad-hoc)
│   └── YYYY_MM_DD_*.ipynb             # Individual explorations
├── README.md        - This file
└── .gitignore
```

---

## Philosophy

Notebooks here are **sandbox exploration tools**, not production artifacts:

1. **Versioned code, not outputs** — Notebooks are committed with cleared outputs
2. **Exploration-first** — Use for rapid iteration, hypothesis testing, charting
3. **Promote patterns, not notebooks** — Useful code graduates to `src/`
4. **No CI dependency** — Notebooks are never required by CI

---

## Usage

### Setup

```bash
# Install Jupyter if needed
pip install jupyter

# Start notebook server
jupyter notebook notebooks/
```

### Running Notebooks

```bash
# From repo root with PYTHONPATH set
PYTHONPATH=src jupyter notebook notebooks/
```

### Before Committing

Clear outputs to keep diffs clean:

```bash
# Clear all notebook outputs
jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace notebooks/**/*.ipynb
```

---

## Sandbox Notebooks

See `sandbox/README.md` for the sandbox notebook workflow.

---

## See Also

- `src/bid_euchre/reporting/` — Production visualization code
- `experiments/` — Reproducible experiment scripts
- `docs/03_TODO/REPO_REVIEW_2026_01_27.md` — Arc B roadmap context
