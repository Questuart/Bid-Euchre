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
MATCHUP_RUN_DIR = "data/runs/arc_d_r0_h2h_battery_42_20260302_231835"
MODEL_NAME = "hybrid_olsa_r0"  # Model name in matchup_id strings

# %% [markdown]
# # §0 Setup

# %%
import os
from pathlib import Path

# C59: prefix audit — no plot_* calls from diagnostics.charts in this notebook

# Ensure CWD is repo root (Jupyter kernels start in notebook dir)
_cwd = Path.cwd()
if not (_cwd / ".git").exists():
    _root = _cwd
    while _root != _root.parent:
        _root = _root.parent
        if (_root / ".git").exists():
            os.chdir(_root)
            break
    else:
        print(f"WARNING: Could not find repo root from {_cwd}")
print(f"Working directory: {Path.cwd()}")

# %% [markdown]
# ## Available eval runs
# Run this cell to discover local eval data:

# %%
import glob as _g

for _p in sorted(_g.glob("data/runs/arc_d_r0_h2h*")):
    print(_p)

# %%
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
_max_deals = MODE_DEAL_COUNTS.get(MODE, 30)
if MODE not in MODE_DEAL_COUNTS:
    import warnings

    warnings.warn(f"Unknown MODE={MODE!r}, defaulting to 30 deals", stacklevel=2)

# --- Load matchup data from JSONL logs ---
_matchup_available = False
df_all = pd.DataFrame()

if MATCHUP_RUN_DIR:
    from bid_euchre.datasets.eval_dataset import build_eval_dataset

    logs_dir = Path(MATCHUP_RUN_DIR) / "logs"
    if logs_dir.is_dir():
        log_files = sorted(str(p) for p in logs_dir.glob("*.jsonl"))
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
                mdf = build_eval_dataset(lf, max_deals=_max_deals)
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
                f"{df_all.drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]} deals, "
                f"{df_all['matchup_id'].nunique()} matchups"
            )
    else:
        print(f"Logs directory not found: {logs_dir}")

if MATCHUP_RUN_DIR and not _matchup_available:
    print(
        f"WARNING: MATCHUP_RUN_DIR={MATCHUP_RUN_DIR!r} is set but no data was loaded.\n"
        "  Check that the path exists relative to the repo root."
    )

if not _matchup_available:
    # Synthetic demo data for CI / SMOKE
    rng = np.random.default_rng(SEED)
    n_deals = _max_deals
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
# ## Fail-Fast Validation
#
# Assert-style checks on loaded data to catch pipeline issues early.
# Emulates the 20_outcome_health S1 pattern.

# %%
if not df_all.empty:
    _validation_results = []

    # Check 1: tricks_won in valid range [0, 10]
    _range_ok = df_all["tricks_won"].between(0, 10).all()
    _validation_results.append(
        {"check": "tricks_won range [0,10]", "status": "PASS" if _range_ok else "FAIL"}
    )
    assert _range_ok, f"tricks_won out of range: {df_all['tricks_won'].describe()}"

    # Check 2: tricks sum to 10 per deal
    _deal_sums = df_all.groupby(["deal_id", "matchup_id"]).apply(
        lambda g: g.drop_duplicates("team")["tricks_won"].sum()
    )
    _zerosum_ok = (_deal_sums == 10).all() if len(_deal_sums) > 0 else True
    _validation_results.append(
        {
            "check": "zero-sum (t0+t1=10)",
            "status": "PASS" if _zerosum_ok else "FAIL",
        }
    )

    # Check 3: no missing contract_type
    _ct_ok = df_all["contract_type"].notna().all()
    _validation_results.append(
        {"check": "no missing contract_type", "status": "PASS" if _ct_ok else "FAIL"}
    )
    assert (
        _ct_ok
    ), f"Missing contract_type: {df_all['contract_type'].isna().sum()} nulls"

    # Check 4: no missing tricks_won
    _tw_ok = df_all["tricks_won"].notna().all()
    _validation_results.append(
        {"check": "no missing tricks_won", "status": "PASS" if _tw_ok else "FAIL"}
    )
    assert _tw_ok, f"Missing tricks_won: {df_all['tricks_won'].isna().sum()} nulls"

    print("=== Fail-Fast Validation ===")
    for r in _validation_results:
        print(f"  [{r['status']}] {r['check']}")
    print(f"\nAll {len(_validation_results)} checks passed.")
else:
    print("WARNING: No data loaded — skipping validation.")

# %%
print("=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {'matchup logs' if _matchup_available else 'synthetic demo'}")
print(f"  Run directory:  {MATCHUP_RUN_DIR or 'N/A (synthetic)'}")
print(
    f"  Total deals:    {df_all.drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]:,}"
)
print(f"  Total rows:     {len(df_all):,} (4 per deal)")
print(
    f"  Matchups:       {df_all['matchup_id'].nunique() if 'matchup_id' in df_all.columns else 'N/A'}"
)
print(f"  Mode:           {MODE}")
print(
    f"  Contract types: {dict(df_all.drop_duplicates(subset=['matchup_id', 'deal_id'])['contract_type'].value_counts()) if not df_all.empty else 'N/A'}"
)

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
# # §2.5 Tricks Delta Distribution
#
# Violin plots of per-deal tricks delta (mean team0 tricks_won minus mean
# team1 tricks_won) by matchup, faceted by contract_type. Self-play violins
# (centered on zero) serve as visual null reference.

# %%
if not df_all.empty and "contract_type" in df_all.columns:
    # Compute per-deal team delta: team0_tricks - team1_tricks
    _deal_delta = (
        df_all.groupby(["matchup_id", "deal_id", "contract_type"])
        .apply(
            lambda g: pd.Series(
                {
                    "delta": (
                        g[g["team"] == 0]["tricks_won"].mean()
                        - g[g["team"] == 1]["tricks_won"].mean()
                    )
                }
            )
        )
        .reset_index()
    )

    ctypes = sorted(_deal_delta["contract_type"].unique())
    matchup_ids = sorted(_deal_delta["matchup_id"].unique())
    n_panels = max(1, len(ctypes))
    fig, axes = plt.subplots(
        1, n_panels, figsize=(6 * n_panels, max(4, len(matchup_ids) * 0.7)), sharey=True
    )
    if not hasattr(axes, "__len__"):
        axes = [axes]

    for ax, ctype in zip(axes, ctypes):
        ct_data = _deal_delta[_deal_delta["contract_type"] == ctype]
        violin_data = []
        labels = []
        colors = []
        for mid in matchup_ids:
            vals = ct_data[ct_data["matchup_id"] == mid]["delta"].values
            if len(vals) > 0:
                violin_data.append(vals)
                labels.append(mid.replace(MODEL_NAME, "R0")[:30])
                colors.append("#CCCCCC" if "self_play" in mid else "#4CAF50")

        if violin_data:
            parts = ax.violinplot(
                violin_data,
                positions=range(len(violin_data)),
                vert=False,
                showmedians=True,
            )
            for i, pc in enumerate(parts.get("bodies", [])):
                pc.set_facecolor(colors[i])
                pc.set_alpha(0.7)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=8)
            ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
            ax.set_xlabel("Tricks Delta (team0 - team1)")
            ax.set_title(f"Tricks Delta Distribution: {ctype}")
            ax.invert_yaxis()

    plt.tight_layout()
    plt.show()
else:
    print("No data for tricks delta distribution.")

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

        n_deals = opp_df.drop_duplicates(subset=["matchup_id", "deal_id"]).shape[0]
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

    # Build summary with team breakout: two rows per matchup (team0, team1)
    summary_rows = []
    for mid in matchup_ids:
        mdf = df_all[df_all["matchup_id"] == mid]
        n = mdf["deal_id"].nunique()
        r0_t = _r0_team(mid)

        for team_id in [0, 1]:
            team_label = "R0" if team_id == r0_t else "opp"
            team_tricks = mdf[mdf["team"] == team_id]["tricks_won"].mean()

            # Per contract type breakdown
            ct_means = {}
            if "contract_type" in mdf.columns:
                for ctype in sorted(mdf["contract_type"].unique()):
                    grp = mdf[
                        (mdf["contract_type"] == ctype) & (mdf["team"] == team_id)
                    ]
                    ct_means[ctype] = (
                        round(grp["tricks_won"].mean(), 3) if len(grp) > 0 else None
                    )

            summary_rows.append(
                {
                    "matchup": mid,
                    "team": f"team{team_id} ({team_label})",
                    "n_deals": n,
                    "mean_tricks": round(team_tricks, 3),
                    **{
                        f"tricks_{ct}": ct_means.get(ct)
                        for ct in sorted(ct_means.keys())
                    },
                }
            )

    df_summary = pd.DataFrame(summary_rows)
    print("=== Summary Table (team breakout) ===")
    print(df_summary.to_string(index=False))

    # Pooled ME delta table (one row per matchup for ranking)
    delta_rows = []
    for mid in matchup_ids:
        mdf = df_all[df_all["matchup_id"] == mid]
        n = mdf["deal_id"].nunique()
        r0_t = _r0_team(mid)
        opp_t = 1 - r0_t
        r0_tricks = mdf[mdf["team"] == r0_t]["tricks_won"].mean()
        opp_tricks = mdf[mdf["team"] == opp_t]["tricks_won"].mean()
        me_delta = r0_tricks - opp_tricks

        ct_deltas = {}
        if "contract_type" in mdf.columns:
            for ctype in sorted(mdf["contract_type"].unique()):
                grp = mdf[mdf["contract_type"] == ctype]
                ct_r0 = grp[grp["team"] == r0_t]["tricks_won"].mean()
                ct_opp = grp[grp["team"] == opp_t]["tricks_won"].mean()
                ct_deltas[ctype] = round(ct_r0 - ct_opp, 3)

        delta_rows.append(
            {
                "matchup": mid,
                "n_deals": n,
                "r0_tricks": round(r0_tricks, 3),
                "opp_tricks": round(opp_tricks, 3),
                "ME_delta": round(me_delta, 3),
                **{f"delta_{ct}": ct_deltas.get(ct) for ct in sorted(ct_deltas.keys())},
            }
        )

    df_deltas = pd.DataFrame(delta_rows)
    print("\n=== ME Delta Table (R0 advantage) ===")
    print(df_deltas.to_string(index=False))

    # Overall competitive ranking bar chart with bootstrap CIs
    competitive = df_deltas[~df_deltas["matchup"].str.contains("self_play")]
    if not competitive.empty:
        # Bootstrap 95% CIs on ME delta per matchup
        rng_rank = np.random.RandomState(SEED)
        n_boot = 10_000
        ci_lo_list, ci_hi_list = [], []
        for mid in competitive["matchup"]:
            mdf = df_all[df_all["matchup_id"] == mid]
            r0_t = _r0_team(mid)
            opp_t = 1 - r0_t
            # Per-deal delta: R0 tricks - opp tricks
            deal_agg = mdf.groupby(["deal_id", "team"])["tricks_won"].mean().unstack()
            if r0_t in deal_agg.columns and opp_t in deal_agg.columns:
                per_deal_delta = (deal_agg[r0_t] - deal_agg[opp_t]).values
                boot_means = np.array(
                    [
                        rng_rank.choice(
                            per_deal_delta, size=len(per_deal_delta), replace=True
                        ).mean()
                        for _ in range(n_boot)
                    ]
                )
                ci_lo_list.append(np.percentile(boot_means, 2.5))
                ci_hi_list.append(np.percentile(boot_means, 97.5))
            else:
                ci_lo_list.append(np.nan)
                ci_hi_list.append(np.nan)

        competitive = competitive.copy()
        competitive["ci_lo"] = ci_lo_list
        competitive["ci_hi"] = ci_hi_list

        fig_rank, ax_rank = plt.subplots(figsize=(10, max(3, len(competitive) * 0.5)))
        colors = ["#4CAF50" if d > 0 else "#F44336" for d in competitive["ME_delta"]]
        labels = competitive["matchup"].str.replace(MODEL_NAME, "R0")
        me_vals = competitive["ME_delta"].values
        xerr_lo = np.maximum(me_vals - competitive["ci_lo"].values, 0)
        xerr_hi = np.maximum(competitive["ci_hi"].values - me_vals, 0)
        ax_rank.barh(
            labels,
            me_vals,
            xerr=[xerr_lo, xerr_hi],
            color=colors,
            capsize=3,
        )
        ax_rank.axvline(0, color="black", linewidth=0.8)
        ax_rank.set_xlabel("ME Delta (R0 Advantage) [95% CI]")
        ax_rank.set_title("Competitive Ranking: Tricks Advantage")
        ax_rank.invert_yaxis()
        plt.tight_layout()
        plt.show()
else:
    print("No data for summary table.")
