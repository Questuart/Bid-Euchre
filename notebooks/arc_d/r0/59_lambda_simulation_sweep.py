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
# # Lambda Simulation Sweep — Track D (R0 v2)
#
# **Protocol:** `plans/r0_v2_lambda_tuning_protocol.md` (Amendment v2)
#
# **Goal:** Analyze simulation-based lambda sweep results. This notebook
# READS pre-computed results from `scripts/internal/run_lambda_sweep.py`
# and produces diagnostics, visualizations, and the ADOPT/RETAIN decision.
#
# Unlike nb58 (offline replay using bidless dataset), this notebook evaluates
# lambda via full self-play simulation, which captures auction dynamics,
# contract selection interactions, and opponent responses.
#
# **Sections:**
# - S0: Setup & data loading
# - S1: Self-play screening (metrics, guardrails, epsilon-greedy, bootstrap CIs)
# - S2: Auction dynamics diagnostics (winning bid dist, contract mix)
# - S2.5: Appendix — nb58 vs Simulation comparison (caveated)
# - S3: Decision gate (ADOPT/RETAIN)
# - S4: Visualizations (2x3 figure)

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE (no sweep data), QUICK (partial), FULL (complete)
SEED = 42
SWEEP_OUTPUT = ""  # Path to lambda_sweep_v1 JSON from run_lambda_sweep.py
CHART_OUTPUT_DIR = ""  # Set via papermill; empty = skip chart save

# %%
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# %% [markdown]
# ## S0: Setup & Data Loading

# %%
# --- CWD-to-repo-root ---
_cwd = Path.cwd()
if _cwd.name == "r0" or _cwd.name == "arc_d":
    import os

    os.chdir(_cwd.parents[2] if _cwd.name == "r0" else _cwd.parents[1])
    print(f"Changed CWD to: {Path.cwd()}")

# %%
# --- Load sweep results ---
sweep_data = None

if SWEEP_OUTPUT:
    sweep_path = Path(SWEEP_OUTPUT)
    if sweep_path.exists():
        with open(sweep_path) as f:
            sweep_data = json.load(f)
        assert (
            sweep_data.get("schema") == "lambda_sweep_v1"
        ), f"Unexpected schema: {sweep_data.get('schema')}"
        print(f"Loaded sweep data: {sweep_path}")
        print(f"  Grid: {sweep_data['grid']}")
        print(f"  lambda*: {sweep_data['lambda_star']}")
        print(f"  Status: {sweep_data['status']}")
        print(f"  n_per: {sweep_data['n_per']}")
        print(f"  seed: {sweep_data['seed']}")
    else:
        print(f"WARNING: SWEEP_OUTPUT path not found: {sweep_path}")
        print("Running in SMOKE mode (no data).")
else:
    print("No sweep data available (SWEEP_OUTPUT is empty).")
    print("To use this notebook, run the lambda sweep first:")
    print(
        "  uv run python scripts/internal/run_lambda_sweep.py "
        "--artifact-path <path> --output <output.json>"
    )

# %% [markdown]
# ## S1: Self-Play Screening
#
# Metrics table, guardrail checks, epsilon-greedy selection, and paired
# bootstrap CI table.

# %%
if sweep_data:
    results_df = pd.DataFrame(sweep_data["results"])

    # --- Metrics overview table ---
    print(f"\n{'=' * 90}")
    print(
        f"SIMULATION SWEEP RESULTS "
        f"(n_per={sweep_data['n_per']:,}, seed={sweep_data['seed']})"
    )
    print(f"{'=' * 90}")
    print(
        f"{'lambda':>8} {'net_eppd':>10} {'bid_rate':>10} "
        f"{'make_rate':>10} {'guardrails':>12}"
    )
    print(f"{'-' * 90}")

    for _, row in results_df.iterrows():
        guard_str = (
            "PASS" if row.get("guardrails", {}).get("all_pass", False) else "FAIL"
        )
        marker = (
            " <- lambda*" if row["risk_lambda"] == sweep_data["lambda_star"] else ""
        )
        print(
            f"{row['risk_lambda']:>8.2f} {row['net_eppd']:>10.4f} "
            f"{row['bid_rate']:>10.3f} {row['make_rate']:>10.3f} "
            f"{guard_str:>12}{marker}"
        )
    print(f"{'=' * 90}")

    # --- Epsilon-greedy selection ---
    print(f"\nEpsilon-greedy selection (epsilon={sweep_data['epsilon']}):")
    print(f"  lambda* = {sweep_data['lambda_star']}")

    # --- Paired bootstrap CIs ---
    ci_rows = [r for r in sweep_data["results"] if "delta_vs_baseline" in r]
    if ci_rows:
        print(f"\n{'=' * 90}")
        print("PAIRED BOOTSTRAP CIs vs BASELINE (lambda=0.0)")
        print(f"{'=' * 90}")
        print(f"{'lambda':>8} {'delta':>10} {'95% CI':>24} {'excludes 0':>12}")
        print(f"{'-' * 90}")
        for r in ci_rows:
            ci_str = f"[{r['ci_95_lo']:+.4f}, {r['ci_95_hi']:+.4f}]"
            excl = "YES" if r.get("ci_excludes_zero", False) else "no"
            print(
                f"{r['risk_lambda']:>8.2f} {r['delta_vs_baseline']:>+10.4f} "
                f"{ci_str:>24} {excl:>12}"
            )
        print(f"{'=' * 90}")

    # --- Monotonicity diagnostic ---
    net_eppds = results_df.sort_values("risk_lambda")["net_eppd"].values
    diffs = np.diff(net_eppds)
    is_monotone_dec = all(d <= 0 for d in diffs)
    is_monotone_inc = all(d >= 0 for d in diffs)
    if is_monotone_dec:
        print("\nMonotonicity: net_eppd is monotonically DECREASING with lambda")
        print("  -> Higher risk aversion consistently hurts performance")
    elif is_monotone_inc:
        print("\nMonotonicity: net_eppd is monotonically INCREASING with lambda")
        print("  -> Higher risk aversion consistently helps performance")
    else:
        print("\nMonotonicity: net_eppd is NON-MONOTONIC across lambda grid")
        print("  -> Risk-return tradeoff has an interior optimum")
else:
    print("No sweep data available — skipping S1.")

# %% [markdown]
# ## S2: Auction Dynamics Diagnostics
#
# Per-run JSONL analysis: winning bid distributions, contract mix, and
# fraction of hands where at least one player bids (h >= 1).
#
# **Note:** This section requires access to the raw JSONL log files from
# each run directory. If running in skip-run mode without local data,
# this section will be skipped.

# %%
if sweep_data:
    # Attempt to load per-run JSONL diagnostics
    # This requires the run directories to be accessible locally
    print("S2: Auction dynamics diagnostics")
    print("  (Requires local run directories — skipped if data not available)")
    print("  To populate: re-run with --skip-run --manifest pointing to local data")
else:
    print("No sweep data available — skipping S2.")

# %% [markdown]
# ## S2.5: Appendix — nb58 vs Simulation Comparison
#
# **CAVEAT:** This comparison is for informational context ONLY. It is NOT
# decision evidence because:
# 1. nb58 uses offline replay (fixed opponents), simulation uses self-play
# 2. nb58 evaluates contract selection + bid level, simulation includes
#    full auction dynamics
# 3. Different data sources and sample sizes
#
# If both nb58 and simulation agree on lambda* direction, that increases
# confidence. If they disagree, simulation takes precedence (it captures
# interactions nb58 cannot).

# %%
if sweep_data:
    print("S2.5: nb58 vs Simulation comparison")
    print("  nb58 result: See notebook 58_lambda_tuning.py for offline replay results")
    print(
        f"  Simulation result: lambda* = {sweep_data['lambda_star']} "
        f"({sweep_data['status']})"
    )
    print("  NOTE: Simulation result takes precedence for decision-making.")
else:
    print("No sweep data available — skipping S2.5.")

# %% [markdown]
# ## S3: Decision Gate
#
# | Condition | Decision | Action |
# |-----------|----------|--------|
# | lambda* == 0.0 | RETAIN | Keep risk_lambda=0.0 |
# | lambda* > 0, CI excludes 0 | ADOPT (provisional) | Update configs, confirm via H2H |
# | lambda* > 0, CI includes 0 | RETAIN | Effect not significant |

# %%
if sweep_data:
    lambda_star = sweep_data["lambda_star"]
    status = sweep_data["status"]

    print(f"\n{'=' * 70}")
    print("DECISION GATE")
    print(f"{'=' * 70}")
    print(f"  lambda*:          {lambda_star}")
    print(f"  Status:           {status}")
    print(f"  Requires H2H:     {sweep_data['requires_h2h_confirmation']}")

    if lambda_star == 0.0:
        decision = "RETAIN"
        print(f"  Decision:         {decision}")
        print("  Rationale:        Baseline (lambda=0.0) is optimal or within epsilon")
        print("  Action:           No config changes needed")
    else:
        # Check if CI excludes zero
        star_result = next(
            (r for r in sweep_data["results"] if r["risk_lambda"] == lambda_star),
            None,
        )
        if star_result and star_result.get("ci_excludes_zero", False):
            decision = "ADOPT"
            print(
                f"  Decision:         {decision} (PROVISIONAL — requires H2H confirmation)"
            )
            print(f"  Delta vs baseline: {star_result['delta_vs_baseline']:+.4f}")
            print(
                f"  95% CI:           [{star_result['ci_95_lo']:+.4f}, "
                f"{star_result['ci_95_hi']:+.4f}]"
            )
            print("  Action:           Update configs, then run H2H battery to confirm")
        else:
            decision = "RETAIN"
            print(f"  Decision:         {decision}")
            print("  Rationale:        CI includes 0 — effect not significant")
            print("  Action:           No config changes needed")

    print(f"{'=' * 70}")

    # Machine-readable decision block
    print("\n```")
    print(f"LAMBDA_SWEEP_DECISION: {decision}")
    print(f"LAMBDA_STAR: {lambda_star}")
    print(f"STATUS: {status}")
    print("```")
else:
    print("No sweep data available — skipping S3.")

# %% [markdown]
# ## S4: Visualizations

# %%
if sweep_data:
    results_df = pd.DataFrame(sweep_data["results"])
    results_df = results_df.sort_values("risk_lambda").reset_index(drop=True)
    lambda_star = sweep_data["lambda_star"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(
        f"Lambda Simulation Sweep (Track D, R0 v2) — "
        f"n_per={sweep_data['n_per']:,}, seed={sweep_data['seed']}",
        fontsize=14,
    )

    # Plot 1: net_eppd vs lambda
    ax = axes[0, 0]
    ax.plot(
        results_df["risk_lambda"],
        results_df["net_eppd"],
        "o-",
        color="C0",
        label="Simulation",
    )
    ax.axvline(
        lambda_star,
        color="red",
        linestyle=":",
        alpha=0.7,
        label=f"lambda*={lambda_star}",
    )
    ax.set_xlabel("risk_lambda")
    ax.set_ylabel("Net EPPD")
    ax.set_title("Net EPPD vs Lambda")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 2: bid_rate vs lambda
    ax = axes[0, 1]
    ax.plot(results_df["risk_lambda"], results_df["bid_rate"], "o-", color="C0")
    ax.axhline(0.05, color="red", linestyle="--", alpha=0.5, label="Floor (0.05)")
    ax.axhline(0.95, color="orange", linestyle="--", alpha=0.5, label="Cap (0.95)")
    ax.axvline(lambda_star, color="red", linestyle=":", alpha=0.7)
    ax.set_xlabel("risk_lambda")
    ax.set_ylabel("Bid Rate")
    ax.set_title("Bid Rate vs Lambda")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 3: make_rate vs lambda
    ax = axes[0, 2]
    ax.plot(results_df["risk_lambda"], results_df["make_rate"], "o-", color="C0")
    ax.axhline(0.45, color="red", linestyle="--", alpha=0.5, label="Floor (0.45)")
    ax.axvline(lambda_star, color="red", linestyle=":", alpha=0.7)
    ax.set_xlabel("risk_lambda")
    ax.set_ylabel("Make Rate")
    ax.set_title("Make Rate vs Lambda")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 4: Forest plot (bootstrap CIs)
    ax = axes[1, 0]
    ci_rows = [r for r in sweep_data["results"] if "delta_vs_baseline" in r]
    if ci_rows:
        ci_df = pd.DataFrame(ci_rows).sort_values("risk_lambda")
        y_pos = range(len(ci_df))
        ax.errorbar(
            ci_df["delta_vs_baseline"],
            y_pos,
            xerr=[
                ci_df["delta_vs_baseline"] - ci_df["ci_95_lo"],
                ci_df["ci_95_hi"] - ci_df["delta_vs_baseline"],
            ],
            fmt="o",
            color="C0",
            capsize=4,
        )
        ax.axvline(0, color="black", linestyle="-", linewidth=1)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels([f"lambda={r['risk_lambda']}" for _, r in ci_df.iterrows()])
        ax.set_xlabel("Delta vs Baseline (net_eppd)")
        ax.set_title("Bootstrap 95% CIs vs Baseline")
    else:
        ax.text(
            0.5,
            0.5,
            "No bootstrap data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_title("Bootstrap CIs (no data)")
    ax.grid(True, alpha=0.3)

    # Plot 5: Winning bid distribution placeholder
    ax = axes[1, 1]
    ax.text(
        0.5,
        0.5,
        "Winning Bid Distribution\n(requires local JSONL data)",
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=10,
    )
    ax.set_title("Winning Bid Distribution")
    ax.grid(True, alpha=0.3)

    # Plot 6: Decision summary
    ax = axes[1, 2]
    ax.axis("off")
    decision_text = "RETAIN" if lambda_star == 0.0 else "ADOPT (provisional)"
    summary_text = (
        f"Lambda Sweep Decision\n"
        f"{'=' * 30}\n\n"
        f"lambda*: {lambda_star}\n"
        f"Status: {sweep_data['status']}\n"
        f"Decision: {decision_text}\n\n"
        f"Grid: {sweep_data['grid']}\n"
        f"Epsilon: {sweep_data['epsilon']}\n"
        f"n_per: {sweep_data['n_per']:,}\n"
        f"seed: {sweep_data['seed']}\n"
        f"pass_threshold: {sweep_data['pass_threshold']}\n\n"
        f"Protocol: r0_v2_lambda_tuning_protocol.md\n"
        f"  (Amendment v2)"
    )
    ax.text(
        0.05,
        0.95,
        summary_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )
    ax.set_title("Decision Summary")

    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        _chart_out = Path(CHART_OUTPUT_DIR)
        _chart_out.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            _chart_out / "lambda_simulation_sweep.png",
            dpi=150,
            bbox_inches="tight",
        )
        print(f"Saved: {_chart_out / 'lambda_simulation_sweep.png'}")
    plt.show()
else:
    print("No sweep data available — skipping S4 visualizations.")
