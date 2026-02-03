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
├── .archive/        - Archived/deprecated notebooks (for reference)
├── README.md        - This file
└── .gitignore
```

**Note:** Old Phase 0 notebook stubs have been archived in `.archive/` for reference.

---

## Philosophy

Notebooks here are **sandbox exploration tools**, not production artifacts:

1. **Versioned code, not outputs** — Notebooks are committed with cleared outputs
2. **Exploration-first** — Use for rapid iteration, hypothesis testing, charting
3. **Promote patterns, not notebooks** — Useful code graduates to `src/`
4. **No CI dependency** — Notebooks are never required by CI

---

## Notebook Pairing (Jupytext)

All notebooks under `notebooks/` are **paired** using Jupytext:

- **Source of truth:** the `.py` file in percent format (review this in PRs)
- **Execution artifact:** the `.ipynb` file (kept in sync for Jupyter)
- **Sync rule:** run `make notebook-sync` before committing
- **Hygiene rule:** run `make notebook-check` to verify sync + cleared outputs

Template starter:

- `notebooks/_templates/00_notebook_template.py`
- `notebooks/_templates/00_notebook_template.ipynb`

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

Sync paired files and verify outputs are cleared:

```bash
make notebook-sync
make notebook-check
```

---

## Sandbox Notebooks

See `sandbox/README.md` for the sandbox notebook workflow.

---

## See Also

- `src/bid_euchre/reporting/` — Production visualization code
- `experiments/` — Reproducible experiment scripts
- `docs/03_TODO/REPO_REVIEW_2026_01_27.md` — Arc B roadmap context
