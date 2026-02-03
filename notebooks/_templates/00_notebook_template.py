# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags
#     formats: ipynb,py:percent
#     notebook_metadata_filter: jupytext,kernelspec,language_info
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   language_info:
#     name: python
# ---

# %% [markdown]
# # Notebook Template
#
# **Goal:** Keep notebooks thin and push reusable logic into `src/bid_euchre/`.
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
#

# %%
# MODE/SEED pattern (consistent with notebooks/phase0_bidless/README.md)
MODE = "QUICK"  # QUICK for fast iteration, FULL for rigor
SEED = 42


# %%
# Minimal imports (add only what you need)


# %%
# Example: load data via reusable helpers in src/
# from bid_euchre.diagnostics.notebook_data import load_or_generate_outcomes
# df = load_or_generate_outcomes(mode=MODE, seed=SEED)


# %%
# Analysis here...
