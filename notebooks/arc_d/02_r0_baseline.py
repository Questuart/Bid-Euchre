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
# # R0 Baseline — Eval Verification
#
# **Goal:** Full HITL evaluation of R0 baseline lock with rich analysis
# from JSONL eval logs plus artifact-side metrics and promotion gate.
#
# **Data source:** JSONL eval logs from `EVAL_RUN_DIR` (primary) or
# synthetic demo data (CI fallback when logs are not available).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
EVAL_RUN_DIR = "data/runs/arc_d_eval_r0_42_20260221_180253"  # R0 eval run
ARTIFACT_DIR = "data/artifacts/arc_d/r0"  # R0 artifact directory
RUNG_ID = "r0"  # R0 baseline
CHART_OUTPUT_DIR = ""  # dir for chart PNGs
PROMOTION_DECISION_PATH = "data/artifacts/arc_d/r0/promotion_decision_r0.json"
