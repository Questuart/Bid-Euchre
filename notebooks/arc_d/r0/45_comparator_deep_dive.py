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
# # Comparator Deep Dive — R0 Single-Seat Battery (v4)
#
# **Goal:** Produce Source B supplemental metrics for the comparator rankings
# report and cross-validate against the Source A extraction artifact.
#
# **Data source:** Per-bidder JSONL game logs from single-seat comparator runs
# (4 seats per bidder, merged). Parsed via `build_eval_dataset()`.
#
# **Sections:**
# - S0: Setup & data loading
# - S1: Cross-validation with Source A
# - S2: Per-deal net-points distributions (violins, bid-conditional)
# - S3: Contract-type breakdown (per-bidder × contract_type)
# - S4: Bid-level distribution (histogram of bid levels)
# - S5: Summary statistics (Source B metrics for report §3)
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42
ARTIFACT_PATH = "data/artifacts/arc_d/r0/comparator_cis_r0_v6.json"
BATTERY_PATH = "data/artifacts/arc_d/r0/comparator_battery_r0_v6.json"
RUNS_DIR = "data/runs"

# %% [markdown]
# # S0: Setup & Data Loading

# %%
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure CWD is repo root
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

# %%
from bid_euchre.analysis.stats import bootstrap_ci
from bid_euchre.datasets.eval_dataset import build_eval_dataset

# %% [markdown]
# ## Load Source A artifact

# %%
with open(ARTIFACT_PATH) as f:
    source_a = json.load(f)

ranked_order = source_a["ranked_order"]
print(f"Schema: {source_a['schema']}")
print(f"Ranked order: {ranked_order}")
print(f"Bidders: {len(source_a['bidders'])}")

# %% [markdown]
# ## Load per-bidder JSONL data
#
# Run resolution rule: use most-recent matching directory per bidder per seat
# (identical to `extract_comparator_cis.py` line 226-244).

# %%
runs_dir = Path(RUNS_DIR)
bidder_names = list(source_a["bidders"].keys())

# MODE-based deal cap (only for fast iteration; FULL uses all data)
DEAL_CAP = {"SMOKE": 30, "QUICK": 2000, "FULL": None}[MODE]

frames = []
for name in bidder_names:
    seat_frames = []
    for seat in range(4):
        pattern = f"auction_comparator_{name}_seat{seat}_{SEED}_*"
        candidates = sorted(runs_dir.glob(pattern))
        if not candidates:
            raise FileNotFoundError(
                f"No run dir for {name} seat {seat} (pattern: {pattern})"
            )
        run_dir = candidates[-1]  # most recent by lexicographic sort
        log_files = sorted(run_dir.glob("logs/*.jsonl"))
        if not log_files:
            raise FileNotFoundError(f"No JSONL in {run_dir}/logs/")

        # build_eval_dataset with skip_redeals=False to include pass deals
        df_seat = build_eval_dataset(
            log_files[0], skip_redeals=False, max_deals=DEAL_CAP
        )
        df_seat["seat_slot"] = seat
        seat_frames.append(df_seat)

    df_bidder = pd.concat(seat_frames, ignore_index=True)
    df_bidder["bidder_name"] = name
    frames.append(df_bidder)

df = pd.concat(frames, ignore_index=True)
print(
    f"Total rows: {len(df):,} ({len(df) // 4:,} deal-seats across {len(bidder_names)} bidders)"
)

# %% [markdown]
# ## Derive net_pts column
#
# For each deal: compute declaring team points minus defending team points.
# Pass deals (redeal_flag=True) get net_pts=0.

# %%
# For bid-hands: sum points_won by team, then compute declaring - defending
# For pass deals: net_pts = 0

# For bid-hands, we need team-level points. Group by (bidder_name, deal_id, seat_slot)
# to get one bidder row per deal per seat-slot. The bidder's team points and opponent
# team points can be derived from the 4 per-seat rows.

# Approach: for each deal, the bidder's team = bidder_team, opponent = 1 - bidder_team.
# points_won in the dataset is already per-team (same for all seats on that team).
# So the bidder row's points_won is the bidder team's total, and we need the
# opponent's total.

# Get bidder-seat rows (one per deal per bidder per seat-slot)
bidder_rows = df[(df["is_bidder"] == True)].copy()  # noqa: E712

# Get opponent team points: for each (bidder_name, deal_id, seat_slot),
# find a row from the opponent team
opponent_rows = df[
    (df["is_declaring_team"] == False) & (~df["redeal_flag"].fillna(False))  # noqa: E712
].copy()
opponent_pts = (
    opponent_rows.groupby(["bidder_name", "deal_id", "seat_slot"])["points_won"]
    .first()
    .rename("opponent_pts")
)

bidder_rows = bidder_rows.set_index(["bidder_name", "deal_id", "seat_slot"])
bidder_rows = bidder_rows.join(opponent_pts)
bidder_rows["net_pts"] = bidder_rows["points_won"] - bidder_rows["opponent_pts"]
bidder_rows = bidder_rows.reset_index()

# Pass deals: get unique (bidder_name, deal_id, seat_slot) from redeal rows
pass_rows = df[(df["redeal_flag"] == True) & (df["seat"] == 0)].copy()  # noqa: E712
pass_rows["bidder_name"] = pass_rows["bidder_name"]  # already set
pass_rows["net_pts"] = 0.0
pass_rows["opponent_pts"] = 0.0

# Combine into per-deal dataset: one row per (bidder_name, deal_id, seat_slot)
bid_deals = bidder_rows[
    [
        "bidder_name",
        "deal_id",
        "seat_slot",
        "contract_type",
        "trump",
        "winning_bid",
        "made_bid",
        "points_won",
        "opponent_pts",
        "net_pts",
        "redeal_flag",
    ]
].copy()
bid_deals["is_bid"] = True

pass_deals = pass_rows[
    [
        "bidder_name",
        "deal_id",
        "seat_slot",
        "contract_type",
        "trump",
        "winning_bid",
        "made_bid",
        "points_won",
        "opponent_pts",
        "net_pts",
        "redeal_flag",
    ]
].copy()
pass_deals["is_bid"] = False

deals = pd.concat([bid_deals, pass_deals], ignore_index=True)
deals = deals.sort_values(["bidder_name", "seat_slot", "deal_id"]).reset_index(
    drop=True
)

print(f"Per-deal rows: {len(deals):,}")
print(f"  Bid deals: {deals['is_bid'].sum():,}")
print(f"  Pass deals: {(~deals['is_bid']).sum():,}")

# %% [markdown]
# ## Compute per-bidder summary metrics

# %%
summary = []
for name in ranked_order:
    bd = deals[deals["bidder_name"] == name]
    n_total = len(bd)
    n_bids = bd["is_bid"].sum()
    bid_rate = n_bids / n_total if n_total > 0 else 0.0
    make_rate = bd.loc[bd["is_bid"], "made_bid"].mean() if n_bids > 0 else 0.0
    net_eppd = bd["net_pts"].sum() / n_total if n_total > 0 else 0.0
    eppd = bd.loc[bd["is_bid"], "points_won"].sum() / n_total if n_total > 0 else 0.0
    std_net = bd["net_pts"].std()

    summary.append(
        {
            "bidder": name,
            "n_total": n_total,
            "n_bids": int(n_bids),
            "bid_rate": bid_rate,
            "make_rate": make_rate,
            "net_eppd": net_eppd,
            "eppd": eppd,
            "std_net_pts": std_net,
        }
    )

summary_df = pd.DataFrame(summary)
summary_df

# %% [markdown]
# ## Assert gates

# %%
# Gate: 8 bidders loaded (v6 roster: 4 heuristic + 2 OLSa + 2 hybrid)
assert len(bidder_names) == 8, f"Expected 8 bidders, got {len(bidder_names)}"

# Gate: pass deals have net_pts == 0
assert (
    deals.loc[~deals["is_bid"], "net_pts"] == 0
).all(), "Pass deals should have net_pts=0"

# Gate: per-bidder deal counts are consistent across bidders (within MODE tolerance)
deal_counts = deals.groupby("bidder_name")["deal_id"].count()
if MODE == "FULL":
    # All bidders should have same total deals (4 seats × N deals/seat)
    assert deal_counts.nunique() == 1, f"Unequal deal counts: {deal_counts.to_dict()}"

print("S0 gates PASSED")

# %% [markdown]
# # S1: Cross-Validation with Source A

# %%
print("Cross-validating notebook metrics against Source A artifact...")
print(
    f"{'Bidder':<25} {'Metric':<10} {'Notebook':>10} {'Source A':>10} {'Delta':>10} {'OK?':>5}"
)
print("-" * 75)

all_ok = True
for name in ranked_order:
    sa = source_a["bidders"][name]
    bd = deals[deals["bidder_name"] == name]
    n_total = len(bd)

    # net_eppd
    nb_net_eppd = bd["net_pts"].sum() / n_total
    sa_net_eppd = sa["net_eppd"]
    delta_net = abs(nb_net_eppd - sa_net_eppd)
    ok_net = delta_net < 0.02  # wider tolerance for SMOKE mode (fewer deals)
    if MODE == "FULL":
        ok_net = delta_net < 0.01
    all_ok &= ok_net
    print(
        f"{name:<25} {'net_eppd':<10} {nb_net_eppd:>10.4f} {sa_net_eppd:>10.4f} {delta_net:>10.4f} {'OK' if ok_net else 'FAIL':>5}"
    )

    # eppd
    nb_eppd = bd.loc[bd["is_bid"], "points_won"].sum() / n_total
    sa_eppd = sa["eppd"]
    delta_eppd = abs(nb_eppd - sa_eppd)
    ok_eppd = delta_eppd < 0.02
    if MODE == "FULL":
        ok_eppd = delta_eppd < 0.01
    all_ok &= ok_eppd
    print(
        f"{'':<25} {'eppd':<10} {nb_eppd:>10.4f} {sa_eppd:>10.4f} {delta_eppd:>10.4f} {'OK' if ok_eppd else 'FAIL':>5}"
    )

if MODE == "FULL":
    assert all_ok, "Cross-validation FAILED — Source A/B disagree beyond tolerance"
elif not all_ok:
    print(
        f"\nWARNING: Some metrics exceed tolerance (expected in {MODE} mode with deal cap)"
    )
else:
    print("\nAll cross-validations passed.")

# %% [markdown]
# # S2: Per-Deal Distributions (Figure 1 — report §3 cross-ref)
#
# Bid-conditional distributions only. Pass deals excluded since they have no
# contract_type and net_pts=0 by definition. Violin means differ from §3
# net_eppd for bidders with bid_rate < 1 because §3 includes pass deals
# as zeros in the denominator.

# %%
bid_only = deals[deals["is_bid"]].copy()

fig, axes = plt.subplots(1, 4, figsize=(20, 6), sharey=True)

panels = [
    ("All bid-hands", bid_only),
    ("Suit", bid_only[bid_only["contract_type"] == "suit"]),
    ("High", bid_only[bid_only["contract_type"] == "high"]),
    ("Low", bid_only[bid_only["contract_type"] == "low"]),
]

for ax, (title, panel_df) in zip(axes, panels):
    violin_data = []
    violin_labels = []
    violin_means = []

    for name in ranked_order:
        bd = panel_df[panel_df["bidder_name"] == name]
        if len(bd) == 0:
            continue
        violin_data.append(bd["net_pts"].values)
        violin_labels.append(name)
        violin_means.append(bd["net_pts"].mean())

    if not violin_data:
        ax.set_title(f"{title} (no data)")
        continue

    parts = ax.violinplot(
        violin_data,
        positions=range(len(violin_data)),
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for pc in parts["bodies"]:
        pc.set_alpha(0.6)

    # Mean markers
    ax.scatter(
        range(len(violin_means)),
        violin_means,
        color="red",
        zorder=5,
        s=30,
        label="Mean",
    )

    # Zero reference
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)

    ax.set_xticks(range(len(violin_labels)))
    ax.set_xticklabels(violin_labels, rotation=45, ha="right", fontsize=8)
    ax.set_title(title)
    if ax == axes[0]:
        ax.set_ylabel("Net points per bid-hand")

fig.suptitle(
    "Figure 1: Per-Deal Net Points Distribution (bid-hands only)",
    fontsize=12,
    fontweight="bold",
)
fig.text(
    0.5,
    -0.02,
    "Pass deals excluded. Violin means differ from report §3 net_eppd for bidders\n"
    "with bid_rate < 1 (hybrid_olsa, modeloespecifico) because §3 includes pass deals "
    "as zeros in the denominator.",
    ha="center",
    fontsize=9,
    style="italic",
)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### Bid-rate reconciliation table
#
# For bid_rate=1.0 bidders, violin mean should equal §3 net_eppd (within rounding).

# %%
print(
    f"{'Bidder':<25} {'bid_rate':>10} {'Violin mean':>12} {'net_eppd (§3)':>14} {'Match?':>8}"
)
print("-" * 72)
for name in ranked_order:
    sa = source_a["bidders"][name]
    bd = bid_only[bid_only["bidder_name"] == name]
    v_mean = bd["net_pts"].mean() if len(bd) > 0 else float("nan")
    net_eppd = sa["net_eppd"]
    br = sa["bid_rate"]
    # For bid_rate=1.0, violin mean ≈ net_eppd (both denominators = total_deals)
    match = abs(v_mean - net_eppd) < 0.02 if br == 1.0 else "N/A"
    match_str = str(match) if isinstance(match, bool) else match
    if MODE == "FULL" and br == 1.0:
        assert (
            abs(v_mean - net_eppd) < 0.01
        ), f"{name}: violin mean {v_mean:.4f} != net_eppd {net_eppd:.4f}"
    print(f"{name:<25} {br:>10.4f} {v_mean:>12.4f} {net_eppd:>14.4f} {match_str:>8}")

# %% [markdown]
# # S3: Contract-Type Breakdown (report §4 cross-ref)
#
# Per bidder × contract_type: bid_rate_ct, make_rate_ct, net_eppd_ct.
# net_eppd_ct = sum(net_pts for bids of this type) / total_deals
# (unconditional denominator so per-facet values sum to pooled net_eppd).

# %%
contract_types = ["suit", "high", "low"]
ct_rows = []

for name in ranked_order:
    bd = deals[deals["bidder_name"] == name]
    n_total = len(bd)
    overall_net_eppd = bd["net_pts"].sum() / n_total

    for ct in contract_types:
        ct_bids = bd[(bd["is_bid"]) & (bd["contract_type"] == ct)]
        n_ct_bids = len(ct_bids)

        bid_rate_ct = n_ct_bids / n_total
        make_rate_ct = ct_bids["made_bid"].mean() if n_ct_bids > 0 else float("nan")
        net_eppd_ct = ct_bids["net_pts"].sum() / n_total

        # Bootstrap CI on net_eppd_ct (resample deals, compute contribution)
        if n_ct_bids >= 20 and MODE != "SMOKE":
            ct_net_pts = ct_bids["net_pts"].values
            # Bootstrap the mean of ct contributions, then scale by (n_ct / n_total)
            _, ci_lo, ci_hi = bootstrap_ci(
                list(ct_net_pts), statistic=np.mean, seed=SEED, n_bootstrap=5000
            )
            # Scale CIs by proportion factor: ct_mean * n_ct / n_total
            scale = n_ct_bids / n_total
            ci_lo_scaled = ci_lo * scale
            ci_hi_scaled = ci_hi * scale
        else:
            ci_lo_scaled = float("nan")
            ci_hi_scaled = float("nan")

        ct_rows.append(
            {
                "bidder": name,
                "contract_type": ct,
                "n_bids": n_ct_bids,
                "bid_rate_ct": bid_rate_ct,
                "make_rate_ct": make_rate_ct,
                "net_eppd_ct": net_eppd_ct,
                "net_eppd_ct_ci_lo": ci_lo_scaled,
                "net_eppd_ct_ci_hi": ci_hi_scaled,
            }
        )

    # Verify additivity
    ct_sum = sum(
        r["net_eppd_ct"]
        for r in ct_rows[-3:]  # last 3 rows = this bidder's 3 types
    )
    if MODE == "FULL":
        assert (
            abs(ct_sum - overall_net_eppd) < 0.01
        ), f"{name}: sum(net_eppd_ct)={ct_sum:.4f} != net_eppd={overall_net_eppd:.4f}"

ct_df = pd.DataFrame(ct_rows)

# %% [markdown]
# ### Contract-type table (markdown-ready)

# %%
print("| Bidder | Contract | n_bids | bid_rate_ct | make_rate_ct | net_eppd_ct |")
print("|--------|----------|--------|-------------|--------------|-------------|")
for _, row in ct_df.iterrows():
    mr = f"{row['make_rate_ct']:.3f}" if not np.isnan(row["make_rate_ct"]) else "N/A"
    print(
        f"| {row['bidder']:<20} | {row['contract_type']:<8} | {row['n_bids']:>6} "
        f"| {row['bid_rate_ct']:.4f}      | {mr:<12} | {row['net_eppd_ct']:+.4f}      |"
    )

# %% [markdown]
# ### Additivity check

# %%
print(f"{'Bidder':<25} {'sum(ct)':>10} {'overall':>10} {'delta':>10}")
print("-" * 58)
for name in ranked_order:
    bd = deals[deals["bidder_name"] == name]
    n_total = len(bd)
    overall = bd["net_pts"].sum() / n_total
    ct_sum = ct_df[ct_df["bidder"] == name]["net_eppd_ct"].sum()
    print(f"{name:<25} {ct_sum:>10.4f} {overall:>10.4f} {ct_sum - overall:>10.4f}")

# %% [markdown]
# # S4: Bid-Level Distribution

# %%
fig, axes = plt.subplots(2, 4, figsize=(20, 8))
axes = axes.flatten()

for idx, name in enumerate(ranked_order):
    ax = axes[idx]
    bd = bid_only[bid_only["bidder_name"] == name]

    if len(bd) == 0:
        ax.set_title(name)
        continue

    for ct, color in [("suit", "#4477AA"), ("high", "#EE6677"), ("low", "#228833")]:
        ct_bids = bd[bd["contract_type"] == ct]
        if len(ct_bids) == 0:
            continue
        bids = ct_bids["winning_bid"].values
        ax.hist(
            bids,
            bins=np.arange(0.5, 11.5, 1),
            alpha=0.5,
            label=ct,
            color=color,
            edgecolor="white",
        )

    ax.set_title(name, fontsize=10)
    ax.set_xlabel("Bid level")
    ax.set_ylabel("Count")
    ax.set_xlim(0.5, 10.5)
    ax.legend(fontsize=7)

# Hide unused subplot
if len(ranked_order) < 8:
    axes[7].set_visible(False)

fig.suptitle(
    "Figure 2: Bid-Level Histograms by Contract Type", fontsize=12, fontweight="bold"
)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### Bid-level assert gates

# %%
# Gate: no bids outside [1, 10]
assert bid_only["winning_bid"].between(1, 10).all(), "Bids outside [1, 10] found"

# Gate: fiveheadfred should only bid 5
fred_bids = bid_only[bid_only["bidder_name"] == "fiveheadfred"]["winning_bid"]
assert (fred_bids == 5).all(), f"FiveHeadFred has non-5 bids: {fred_bids.unique()}"

# Gate: stricthellraiser in single-seat mode always bids 3 (current_high_bid=0)
shr_bids = bid_only[bid_only["bidder_name"] == "stricthellraiser"]["winning_bid"]
assert (shr_bids == 3).all(), f"StrictHellRaiser has non-3 bids: {shr_bids.unique()}"

print("S4 gates PASSED")

# %% [markdown]
# # S5: Summary Statistics (Source B metrics for report §3)
#
# Per-bidder: bid_rate + bootstrap CI, make_rate + bootstrap CI, std(net_pts).
# These supplement Source A with uncertainty on rates and volatility metrics.

# %%
s5_rows = []
for name in ranked_order:
    bd = deals[deals["bidder_name"] == name]
    n_total = len(bd)
    n_bids = bd["is_bid"].sum()

    # bid_rate bootstrap CI (indicator: 1 if bid, 0 if pass)
    bid_indicator = bd["is_bid"].astype(float).values
    if MODE != "SMOKE" and len(bid_indicator) > 20:
        br_est, br_lo, br_hi = bootstrap_ci(
            list(bid_indicator), statistic=np.mean, seed=SEED, n_bootstrap=10000
        )
    else:
        br_est = bid_indicator.mean()
        br_lo, br_hi = br_est, br_est

    # make_rate bootstrap CI (indicator: 1 if made, 0 if set; bid-hands only)
    bid_hands = bd[bd["is_bid"]]
    if MODE != "SMOKE" and len(bid_hands) > 20:
        make_indicator = bid_hands["made_bid"].astype(float).values
        mr_est, mr_lo, mr_hi = bootstrap_ci(
            list(make_indicator), statistic=np.mean, seed=SEED, n_bootstrap=10000
        )
    else:
        mr_est = bid_hands["made_bid"].mean() if len(bid_hands) > 0 else 0.0
        mr_lo, mr_hi = mr_est, mr_est

    # std(net_pts) — computed on ALL deals (zeros for passes)
    all_net = deals[deals["bidder_name"] == name]["net_pts"]
    std_net = float(all_net.std())

    # net_eppd (for cross-check)
    net_eppd = all_net.sum() / n_total

    s5_rows.append(
        {
            "bidder": name,
            "n_deals": n_total,
            "n_bids": int(n_bids),
            "bid_rate": br_est,
            "bid_rate_ci_lo": br_lo,
            "bid_rate_ci_hi": br_hi,
            "make_rate": mr_est,
            "make_rate_ci_lo": mr_lo,
            "make_rate_ci_hi": mr_hi,
            "std_net_pts": std_net,
            "net_eppd": net_eppd,
        }
    )

s5_df = pd.DataFrame(s5_rows)

# %% [markdown]
# ### Source B summary table (markdown-ready for report §3)

# %%
print(
    "| Bidder | n_deals | n_bids | bid_rate [95% CI] | make_rate [95% CI] | std(net_pts) | net_eppd |"
)
print(
    "|--------|---------|--------|-------------------|--------------------|--------------|---------:|"
)
for _, row in s5_df.iterrows():
    br_ci = f"{row['bid_rate']:.4f} [{row['bid_rate_ci_lo']:.4f}, {row['bid_rate_ci_hi']:.4f}]"
    mr_ci = f"{row['make_rate']:.4f} [{row['make_rate_ci_lo']:.4f}, {row['make_rate_ci_hi']:.4f}]"
    print(
        f"| {row['bidder']:<20} | {row['n_deals']:>7} | {row['n_bids']:>6} "
        f"| {br_ci} | {mr_ci} | {row['std_net_pts']:>12.3f} | {row['net_eppd']:>+8.4f} |"
    )

# %% [markdown]
# ### Source A/B bid_rate and make_rate agreement check

# %%
print(
    f"{'Bidder':<25} {'bid_rate_NB':>12} {'bid_rate_SA':>12} {'make_rate_NB':>13} {'make_rate_SA':>13}"
)
print("-" * 78)
for _, row in s5_df.iterrows():
    sa = source_a["bidders"][row["bidder"]]
    print(
        f"{row['bidder']:<25} {row['bid_rate']:>12.4f} {sa['bid_rate']:>12.4f} "
        f"{row['make_rate']:>13.4f} {sa['make_rate']:>13.4f}"
    )
    if MODE == "FULL":
        assert (
            abs(row["bid_rate"] - sa["bid_rate"]) < 0.001
        ), f"{row['bidder']}: bid_rate mismatch"
        assert (
            abs(row["make_rate"] - sa["make_rate"]) < 0.001
        ), f"{row['bidder']}: make_rate mismatch"

print("\nS5 cross-validation complete.")
