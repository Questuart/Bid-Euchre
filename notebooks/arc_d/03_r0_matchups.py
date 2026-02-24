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
# # R0 Head-to-Head Matchup Analysis
#
# **Goal:** Evaluate HybridOLSaBidder R0 against heuristic opponents in
# auction-mode head-to-head matchups with seat rotation and self-play control.
#
# **Data source:** Per-matchup JSONL logs from `MATCHUP_RUN_DIR` parsed via
# `build_eval_dataset()`. Each matchup produces a log file containing
# per-deal auction and outcome data.
#
# **Matchup design:**
# - All trick play uses GluttonStrategy (constant); only bidding policies vary.
# - Seat rotation: `[A, B, A, B]` vs `[B, A, B, A]` detects positional bias.
# - Self-play control: `[A, A, A, A]` validates fairness.
# - Contract_type is determined by auction winner (auction mode).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
MATCHUP_RUN_DIR = ""  # Path to h2h run (empty = skip matchup analysis, show demo)
MODEL_NAME = "hybrid_olsa_r0"  # Model name in matchup_id strings

# %% [markdown]
# # §0 Setup

# %%
import glob as glob_mod
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE)

# --- Load matchup data from JSONL logs ---
_matchup_available = False
df_all = pd.DataFrame()

if MATCHUP_RUN_DIR:
    from bid_euchre.datasets.eval_dataset import build_eval_dataset

    logs_dir = Path(MATCHUP_RUN_DIR) / "logs"
    if logs_dir.is_dir():
        log_files = sorted(glob_mod.glob(str(logs_dir / "*.jsonl")))
        frames = []
        for lf in log_files:
            lf_path = Path(lf)
            # Extract matchup_id from filename pattern: <run_id>_<matchup_id>.jsonl
            # The run_id is the directory name; the suffix after it is the matchup_id
            stem = lf_path.stem
            run_dir_name = Path(MATCHUP_RUN_DIR).name
            if stem.startswith(run_dir_name + "_"):
                mid = stem[len(run_dir_name) + 1 :]
            else:
                mid = stem
            try:
                mdf = build_eval_dataset(lf, max_deals=max_deals)
                if not mdf.empty:
                    mdf["matchup_id"] = mid
                    frames.append(mdf)
                    print(f"  Loaded {mid}: {mdf['deal_id'].nunique()} deals")
            except Exception as exc:
                print(f"  WARNING: Could not load {lf_path.name}: {exc}")

        if frames:
            df_all = pd.concat(frames, ignore_index=True)
            _matchup_available = True
            print(
                f"\nTotal: {len(df_all)} rows, "
                f"{df_all['deal_id'].nunique()} deals, "
                f"{df_all['matchup_id'].nunique()} matchups"
            )
    else:
        print(f"Logs directory not found: {logs_dir}")

if not _matchup_available:
    # Synthetic demo data for CI / SMOKE
    rng = np.random.default_rng(SEED)
    n_deals = max_deals or 30
    matchup_ids = [
        "hybrid_olsa_r0_vs_modeloespecifico",
        "modeloespecifico_vs_hybrid_olsa_r0",
        "hybrid_olsa_r0_self_play",
    ]
    rows = []
    for mid in matchup_ids:
        for deal_id in range(n_deals):
            contract = rng.choice(["suit", "high", "low"])
            trump = rng.choice(["C", "D", "H", "S"]) if contract == "suit" else None
            t0 = rng.integers(2, 9)
            t1 = 10 - t0
            for seat in range(4):
                team = 0 if seat in (0, 2) else 1
                rows.append(
                    {
                        "deal_id": deal_id + n_deals * matchup_ids.index(mid),
                        "hand_id": deal_id + n_deals * matchup_ids.index(mid),
                        "seat": seat,
                        "team": team,
                        "contract_type": contract,
                        "trump": trump,
                        "tricks_won": t0 if seat in (0, 2) else t1,
                        "is_bidder": seat == 0,
                        "is_declaring_team": team == 0,
                        "winning_bid": int(rng.integers(5, 11)),
                        "made_bid": bool(rng.random() > 0.3),
                        "matchup_id": mid,
                    }
                )
    df_all = pd.DataFrame(rows)
    print(
        f"Using synthetic demo data ({n_deals} deals/matchup, "
        f"{len(matchup_ids)} matchups)"
    )

print(f"MODE={MODE}, matchup_available={_matchup_available}")


# --- R0 team-resolution helpers ---
def _r0_team(matchup_id: str) -> int:
    """Return 0 or 1 indicating which team MODEL_NAME occupies.

    Convention: in ``A_vs_B``, A sits on seats 0,2 (team 0).
    If MODEL_NAME appears in the second position, R0 is team 1.
    Self-play defaults to team 0 (symmetric, doesn't matter).
    """
    if "self_play" in matchup_id:
        return 0
    parts = matchup_id.split("_vs_")
    if len(parts) == 2 and MODEL_NAME in parts[1]:
        return 1
    return 0


def _r0_sign(matchup_id: str) -> int:
    """Return +1 if R0 is team 0, -1 if R0 is team 1."""
    return 1 if _r0_team(matchup_id) == 0 else -1


# %% [markdown]
# # §1 Matchup Overview
#
# Win rate table by matchup (both seat directions), aggregated across
# all contract types.

# %%
if not df_all.empty:
    # Aggregate per matchup: R0 vs opponent mean tricks
    overview_rows = []
    for mid in sorted(df_all["matchup_id"].unique()):
        mdf = df_all[df_all["matchup_id"] == mid]
        n_deals = mdf["deal_id"].nunique()
        r0_t = _r0_team(mid)
        opp_t = 1 - r0_t
        r0_tricks = mdf[mdf["team"] == r0_t]["tricks_won"].mean()
        opp_tricks = mdf[mdf["team"] == opp_t]["tricks_won"].mean()
        # Win rate: fraction of deals where R0's team scored more tricks
        deal_agg = mdf.groupby(["deal_id", "team"])["tricks_won"].mean().unstack()
        if r0_t in deal_agg.columns and opp_t in deal_agg.columns:
            r0_win_rate = (deal_agg[r0_t] > deal_agg[opp_t]).mean()
        else:
            r0_win_rate = np.nan
        overview_rows.append(
            {
                "matchup": mid,
                "deals": n_deals,
                "r0_tricks": round(r0_tricks, 3),
                "opp_tricks": round(opp_tricks, 3),
                "r0_win_rate": round(r0_win_rate, 3),
            }
        )

    df_overview = pd.DataFrame(overview_rows)
    print("=== Matchup Overview ===")
    print(df_overview.to_string(index=False))
else:
    print("No matchup data available.")

# %% [markdown]
# # §2 Tricks Distribution
#
# Violin + box plot of tricks_won by matchup, faceted by contract_type.

# %%
if not df_all.empty and "contract_type" in df_all.columns:
    matchup_ids = sorted(df_all["matchup_id"].unique())
    ctypes = sorted(df_all["contract_type"].unique())

    fig, axes = plt.subplots(
        1,
        len(ctypes),
        figsize=(6 * len(ctypes), max(4, len(matchup_ids) * 0.6)),
        sharey=True,
    )
    if not hasattr(axes, "__len__"):
        axes = [axes]
    for ax, ctype in zip(axes, ctypes):
        data = []
        labels = []
        for mid in matchup_ids:
            subset = df_all[
                (df_all["matchup_id"] == mid) & (df_all["contract_type"] == ctype)
            ]
            if not subset.empty:
                data.append(subset["tricks_won"].values)
                labels.append(mid.replace("hybrid_olsa_r0", "R0")[:30])
        if data:
            ax.boxplot(data, vert=True, labels=labels)
            ax.set_title(f"Tricks Won: {ctype}")
            ax.set_ylabel("Tricks Won")
            ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.show()
else:
    print("No data for tricks distribution.")

# %% [markdown]
# # §3 Self-Play Fairness
#
# R0 self-play: team0 vs team1 delta should be ~0, per contract_type.

# %%
self_play_ids = [mid for mid in df_all["matchup_id"].unique() if "self_play" in mid]
if self_play_ids and not df_all.empty:
    for mid in self_play_ids:
        mdf = df_all[df_all["matchup_id"] == mid]
        print(f"\n=== Self-Play: {mid} ===")

        if "contract_type" in mdf.columns:
            for ctype in sorted(mdf["contract_type"].unique()):
                grp = mdf[mdf["contract_type"] == ctype]
                t0 = grp[grp["team"] == 0]["tricks_won"]
                t1 = grp[grp["team"] == 1]["tricks_won"]
                delta = t0.mean() - t1.mean()
                # t-test for difference from zero
                if len(t0) >= 2 and len(t1) >= 2:
                    t_stat, p_val = stats.ttest_ind(t0, t1)
                    print(
                        f"  {ctype}: team0={t0.mean():.3f}, team1={t1.mean():.3f}, "
                        f"delta={delta:+.3f}, t={t_stat:.3f}, p={p_val:.4f}"
                    )
                    if p_val < 0.05:
                        print("    WARNING: Significant team imbalance (p < 0.05)")
                else:
                    print(
                        f"  {ctype}: insufficient data (n_t0={len(t0)}, n_t1={len(t1)})"
                    )
        else:
            t0 = mdf[mdf["team"] == 0]["tricks_won"]
            t1 = mdf[mdf["team"] == 1]["tricks_won"]
            delta = t0.mean() - t1.mean()
            print(f"  Overall: delta={delta:+.3f}")
else:
    print("No self-play matchup found — skipping fairness check.")

# %% [markdown]
# # §4 Seat Rotation Validation
#
# A-vs-B vs B-vs-A: the mean tricks delta should approximately flip sign.
# This validates that results are not driven by positional advantage.

# %%
if not df_all.empty:
    matchup_ids = sorted(df_all["matchup_id"].unique())

    # Find rotation pairs: X_vs_Y and Y_vs_X
    pairs_found = []
    seen = set()
    for mid in matchup_ids:
        if "self_play" in mid or mid in seen:
            continue
        # Try to find the reverse
        parts = mid.split("_vs_")
        if len(parts) == 2:
            reverse = f"{parts[1]}_vs_{parts[0]}"
            if reverse in matchup_ids:
                pairs_found.append((mid, reverse))
                seen.add(mid)
                seen.add(reverse)

    if pairs_found:
        print("=== Seat Rotation Validation ===")
        for fwd, rev in pairs_found:
            fwd_df = df_all[df_all["matchup_id"] == fwd]
            rev_df = df_all[df_all["matchup_id"] == rev]
            # Compute R0-relative delta for each seat arrangement
            fwd_raw = (
                fwd_df[fwd_df["team"] == 0]["tricks_won"].mean()
                - fwd_df[fwd_df["team"] == 1]["tricks_won"].mean()
            )
            rev_raw = (
                rev_df[rev_df["team"] == 0]["tricks_won"].mean()
                - rev_df[rev_df["team"] == 1]["tricks_won"].mean()
            )
            fwd_r0_delta = fwd_raw * _r0_sign(fwd)
            rev_r0_delta = rev_raw * _r0_sign(rev)
            spread = abs(fwd_r0_delta - rev_r0_delta)
            print(f"\n  {fwd}: R0 delta = {fwd_r0_delta:+.3f}")
            print(f"  {rev}: R0 delta = {rev_r0_delta:+.3f}")
            print(f"    Spread = {spread:.3f}")
            if spread > 1.0:
                print("    WARNING: Large spread — possible positional bias")
            else:
                print("    OK: R0-relative deltas are consistent across seat positions")
    else:
        print("No rotation pairs found.")
else:
    print("No data for seat rotation validation.")

# %% [markdown]
# # §5 Per-Opponent Analysis
#
# For each opponent: tricks distribution, make rate, contract selection.
# Groups forward and reverse matchups together.

# %%
if not df_all.empty and "contract_type" in df_all.columns:
    matchup_ids = sorted(df_all["matchup_id"].unique())
    # Identify unique opponents (exclude self-play)
    opponents = set()
    for mid in matchup_ids:
        if "self_play" in mid:
            continue
        parts = mid.split("_vs_")
        if len(parts) == 2:
            for p in parts:
                if MODEL_NAME not in p:
                    opponents.add(p)

    for opp in sorted(opponents):
        # Gather all matchups involving this opponent
        opp_ids = [mid for mid in matchup_ids if opp in mid and "self_play" not in mid]
        opp_df = df_all[df_all["matchup_id"].isin(opp_ids)]
        if opp_df.empty:
            continue

        n_deals = opp_df["deal_id"].nunique()
        print(f"\n{'=' * 50}")
        print(f"Opponent: {opp} ({n_deals} deals across {len(opp_ids)} matchup(s))")
        print(f"{'=' * 50}")

        # Contract selection
        deal_opp = opp_df[opp_df["seat"] == 0]
        if "contract_type" in deal_opp.columns:
            print("\nContract selection:")
            print(deal_opp["contract_type"].value_counts().to_string())

        # Make rate by contract type
        if "is_bidder" in opp_df.columns and "made_bid" in opp_df.columns:
            bidder_opp = opp_df[opp_df["is_bidder"] == True]  # noqa: E712
            if not bidder_opp.empty:
                print("\nMake rate by contract_type:")
                for ctype in sorted(bidder_opp["contract_type"].unique()):
                    grp = bidder_opp[bidder_opp["contract_type"] == ctype]
                    mr = grp["made_bid"].mean()
                    print(f"  {ctype}: {mr:.3f} (n={len(grp)})")

        # Mean tricks by contract type — R0-relative
        print("\nMean tricks_won by contract_type (R0-relative):")
        for ctype in sorted(opp_df["contract_type"].unique()):
            grp = opp_df[opp_df["contract_type"] == ctype]
            # Aggregate per matchup with correct team assignment
            for omid in sorted(grp["matchup_id"].unique()):
                mg = grp[grp["matchup_id"] == omid]
                r0_t = _r0_team(omid)
                r0_val = mg[mg["team"] == r0_t]["tricks_won"].mean()
                opp_val = mg[mg["team"] == (1 - r0_t)]["tricks_won"].mean()
                print(f"  {ctype} [{omid}]: R0={r0_val:.3f}, opp={opp_val:.3f}")
else:
    print("No data for per-opponent analysis.")

# %% [markdown]
# # §6 Performance by Contract
#
# R0 tricks faceted by contract_type x opponent.

# %%
if not df_all.empty and "contract_type" in df_all.columns:
    matchup_ids = sorted(df_all["matchup_id"].unique())
    # Exclude self-play for this chart
    competitive_ids = [mid for mid in matchup_ids if "self_play" not in mid]
    competitive_df = df_all[df_all["matchup_id"].isin(competitive_ids)]

    if not competitive_df.empty:
        ctypes = sorted(competitive_df["contract_type"].unique())
        fig, axes = plt.subplots(
            1, len(ctypes), figsize=(6 * len(ctypes), 5), sharey=True
        )
        if not hasattr(axes, "__len__"):
            axes = [axes]
        for ax, ctype in zip(axes, ctypes):
            ctype_df = competitive_df[competitive_df["contract_type"] == ctype]
            # Group by matchup_id, compute R0's team mean tricks
            r0_means = {}
            for mid in ctype_df["matchup_id"].unique():
                mg = ctype_df[ctype_df["matchup_id"] == mid]
                r0_t = _r0_team(mid)
                r0_means[mid] = mg[mg["team"] == r0_t]["tricks_won"].mean()
            means = pd.Series(r0_means).sort_values(ascending=False)
            if not means.empty:
                labels = [m.replace(MODEL_NAME, "R0")[:25] for m in means.index]
                ax.barh(labels, means.values)
                ax.set_xlabel("Mean Tricks (R0)")
                ax.set_title(f"R0 Performance: {ctype}")
                ax.invert_yaxis()
        plt.tight_layout()
        plt.show()
else:
    print("No data for performance by contract.")

# %% [markdown]
# # §7 Summary Table
#
# Rank R0 among opponents per contract_type with ME delta.

# %%
if not df_all.empty:
    matchup_ids = sorted(df_all["matchup_id"].unique())

    # Build summary: for each matchup, compute R0 tricks advantage
    summary_rows = []
    for mid in matchup_ids:
        mdf = df_all[df_all["matchup_id"] == mid]
        n = mdf["deal_id"].nunique()
        r0_t = _r0_team(mid)
        opp_t = 1 - r0_t
        r0_tricks = mdf[mdf["team"] == r0_t]["tricks_won"].mean()
        opp_tricks = mdf[mdf["team"] == opp_t]["tricks_won"].mean()
        me_delta = r0_tricks - opp_tricks

        # Per contract type breakdown
        ct_deltas = {}
        if "contract_type" in mdf.columns:
            for ctype in sorted(mdf["contract_type"].unique()):
                grp = mdf[mdf["contract_type"] == ctype]
                ct_r0 = grp[grp["team"] == r0_t]["tricks_won"].mean()
                ct_opp = grp[grp["team"] == opp_t]["tricks_won"].mean()
                ct_deltas[ctype] = round(ct_r0 - ct_opp, 3)

        summary_rows.append(
            {
                "matchup": mid,
                "n_deals": n,
                "r0_tricks": round(r0_tricks, 3),
                "opp_tricks": round(opp_tricks, 3),
                "ME_delta": round(me_delta, 3),
                **{f"delta_{ct}": ct_deltas.get(ct) for ct in sorted(ct_deltas.keys())},
            }
        )

    df_summary = pd.DataFrame(summary_rows)
    print("=== Summary Table ===")
    print(df_summary.to_string(index=False))

    # Overall competitive ranking bar chart
    competitive = df_summary[~df_summary["matchup"].str.contains("self_play")]
    if not competitive.empty:
        fig_rank, ax_rank = plt.subplots(figsize=(10, max(3, len(competitive) * 0.5)))
        colors = ["#4CAF50" if d > 0 else "#F44336" for d in competitive["ME_delta"]]
        ax_rank.barh(
            competitive["matchup"].str.replace(MODEL_NAME, "R0"),
            competitive["ME_delta"],
            color=colors,
        )
        ax_rank.axvline(0, color="black", linewidth=0.8)
        ax_rank.set_xlabel("ME Delta (R0 Advantage)")
        ax_rank.set_title("Competitive Ranking: Tricks Advantage")
        ax_rank.invert_yaxis()
        plt.tight_layout()
        plt.show()
else:
    print("No data for summary table.")
