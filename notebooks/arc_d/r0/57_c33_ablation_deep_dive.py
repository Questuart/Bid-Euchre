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
# # C33 Ablation Deep Dive — Decision Replay Analysis
#
# **Goal:** Replay hands through both the OLSa (floor-based) and HybridOLSa
# (Gaussian EV wrapper) decision layers to produce evidence for the selective
# restraint mechanism described in the C33 ablation report.
#
# **Architecture:**
# - **Tier A (intrinsic):** All 4 seats, `current_high_bid=0`, prediction-only.
#   Compares what each bidder *would* do without auction interaction.
# - **Tier B (outcome-validated):** Auction winner only, includes actual outcomes.
#   Validates predictions against realized tricks and make/set.
#
# **Data source:** C33 ablation run JSONL logs (primary) or synthetic fallback
# for CI/SMOKE mode.
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
C33_RUN_DIR = "data/runs/arc_d_r0_c33_ablation_42_20260302_230400"
ARTIFACT_PATH = "data/artifacts/arc_d/r0/hybrid_r0.json"

# %% [markdown]
# # S1: Setup & Data Loading

# %%
import json
import math
import os
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

matplotlib.use("Agg")

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

# %%
from bid_euchre.core.cards import Card
from bid_euchre.features.hand_eval import get_hand_features

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
_max_deals = MODE_DEAL_COUNTS.get(MODE, 30)
if MODE not in MODE_DEAL_COUNTS:
    warnings.warn(f"Unknown MODE={MODE!r}, defaulting to 30 deals", stacklevel=2)

print(f"MODE={MODE}, max_deals={_max_deals}")

# %%
# --- Load model artifact ---
_artifact_path = Path(ARTIFACT_PATH)
_artifact_is_real = False
if _artifact_path.exists():
    with open(_artifact_path) as f:
        artifact = json.load(f)
    assert (
        artifact.get("artifact_type") == "hybrid_olsa_v1"
    ), f"Expected hybrid_olsa_v1, got {artifact.get('artifact_type')}"
    assert len(artifact["payoff_model"]) == 3, "Expected suit/high/low models"
    assert all(
        cf in artifact["residual_variance"] for cf in artifact["payoff_model"]
    ), "residual_variance missing contract families"

    risk_lambda = artifact.get("risk_lambda", 0.0)
    assert risk_lambda == 0.0, (
        f"risk_lambda={risk_lambda} != 0.0; Tier-B actual_ev must be replaced "
        f"with actual_utility = actual_ev - risk_penalty. See bidding.py:944-978."
    )
    _artifact_is_real = True
    print(f"Artifact loaded: {_artifact_path.name}")
    print(f"  risk_lambda = {risk_lambda}")
    print(f"  Contract families: {list(artifact['payoff_model'].keys())}")
else:
    # Synthetic artifact for CI/SMOKE when real artifact not available
    print(
        f"WARNING: Artifact not found at {ARTIFACT_PATH}, creating synthetic artifact"
    )
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "payoff_model": {
            cf: {
                "weights": [0.5, 0.3, 0.1],
                "bias": 3.0,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            }
            for cf in ["suit", "high", "low"]
        },
        "residual_variance": {"suit": 2.5, "high": 3.0, "low": 3.2},
        "risk_lambda": 0.0,
    }

# %% [markdown]
# ## S1b: Decision Replay Helpers
#
# These functions mirror the production code in `bidding.py` exactly.

# %%
# --- Replay helpers (mirror bidding.py line-for-line) ---

_Z_CAP = 6.0


def _detect_offdef(art: dict) -> bool:
    """Detect nested off/def vs flat artifact format. Mirrors bidding.py:814-817."""
    return any("offensive" in model_data for model_data in art["payoff_model"].values())


def _get_model(art: dict, contract_family: str) -> dict:
    """Get the offensive model dict. Mirrors bidding.py:884-888."""
    if _detect_offdef(art):
        return art["payoff_model"][contract_family]["offensive"]
    return art["payoff_model"][contract_family]


def predict_mu(art: dict, contract_family: str, features: dict) -> float:
    """Predict tricks via OLS. Mirrors bidding.py:873-890."""
    model = _get_model(art, contract_family)
    x = np.array([features[f] for f in model["feature_names"]], dtype=np.float64)
    return float(x @ np.array(model["weights"], dtype=np.float64) + model["bias"])


def get_sigma(art: dict, contract_family: str) -> float:
    """Get residual std dev. Mirrors bidding.py:892-908."""
    rv = art["residual_variance"][contract_family]
    if isinstance(rv, dict) and "offensive" in rv:
        var = float(rv["offensive"])
    else:
        var = float(rv)
    return math.sqrt(max(0.0, var))


def compute_p_make(mu: float, sigma: float, bid_n: int) -> float:
    """P(make) via Gaussian CDF. Mirrors bidding.py:929-930."""
    if sigma == 0.0:
        return 1.0 if mu >= bid_n else 0.0
    threshold = bid_n - 0.5
    z = (threshold - mu) / sigma
    z = max(-_Z_CAP, min(_Z_CAP, z))
    return float(1.0 - norm.cdf(z))


def compute_ev(mu: float, sigma: float, bid_n: int) -> float:
    """Expected value via truncated normal. Mirrors bidding.py:910-952."""
    if sigma == 0.0:
        if mu >= bid_n:
            return 2.0 * mu - 10.0
        else:
            return mu - bid_n - 10.0

    threshold = bid_n - 0.5
    z = (threshold - mu) / sigma
    z = max(-_Z_CAP, min(_Z_CAP, z))

    p_make = 1.0 - norm.cdf(z)
    p_set = 1.0 - p_make
    pdf_z = norm.pdf(z)

    if p_make > 1e-12:
        e_tricks_make = mu + sigma * pdf_z / p_make
    else:
        e_tricks_make = mu

    if p_set > 1e-12:
        e_tricks_set = mu - sigma * pdf_z / p_set
    else:
        e_tricks_set = mu

    make_ev = 2.0 * e_tricks_make - 10.0
    set_ev = e_tricks_set - bid_n - 10.0

    return p_make * make_ev + p_set * set_ev


# %%
def replay_bidding_decision(
    hand_cards: list,
    art: dict,
    current_high_bid: int = 0,
) -> dict:
    """Replay a hand through both decision layers.

    Returns dict with keys for OLSa and Hybrid decisions, plus per-contract detail.
    """
    contract_map = {
        "suit": ["C", "D", "H", "S"],
        "high": [None],
        "low": [None],
    }

    olsa_candidates = []
    hybrid_candidates = []
    all_contracts = []

    for contract_family, trumps in contract_map.items():
        if contract_family not in art["payoff_model"]:
            continue

        sigma = get_sigma(art, contract_family)

        for trump in trumps:
            features = get_hand_features(hand_cards, contract_family, trump)
            mu = predict_mu(art, contract_family, features)
            bid_n = max(1, min(10, math.floor(mu)))

            p_make = compute_p_make(mu, sigma, bid_n)
            ev = compute_ev(mu, sigma, bid_n)

            contract_label = (
                trump if contract_family == "suit" else contract_family.upper()
            )

            info = {
                "contract_family": contract_family,
                "trump": trump,
                "contract_label": contract_label,
                "mu": mu,
                "sigma": sigma,
                "bid_n": bid_n,
                "p_make": p_make,
                "ev": ev,
            }
            all_contracts.append(info)

            # OLSa candidate: floor(mu) >= 1 and > current_high_bid
            if bid_n >= 1 and bid_n > current_high_bid:
                olsa_candidates.append(info)

            # Hybrid candidate: same bid constraint + EV > 0
            if bid_n >= 1 and bid_n > current_high_bid and ev > 0:
                hybrid_candidates.append(info)

    # OLSa picks best by (mu, bid_n, contract_label) descending
    olsa_best = None
    if olsa_candidates:
        olsa_best = max(
            olsa_candidates,
            key=lambda c: (c["mu"], c["bid_n"], c["contract_label"]),
        )

    # Hybrid picks best by EV descending
    hybrid_best = None
    if hybrid_candidates:
        hybrid_best = max(hybrid_candidates, key=lambda c: c["ev"])

    result = {
        "olsa_bids": olsa_best is not None,
        "olsa_bid_n": olsa_best["bid_n"] if olsa_best else None,
        "olsa_contract": olsa_best["contract_label"] if olsa_best else None,
        "olsa_mu": olsa_best["mu"] if olsa_best else None,
        "hybrid_bids": hybrid_best is not None,
        "hybrid_bid_n": hybrid_best["bid_n"] if hybrid_best else None,
        "hybrid_contract": hybrid_best["contract_label"] if hybrid_best else None,
        "hybrid_mu": hybrid_best["mu"] if hybrid_best else None,
        "hybrid_ev": hybrid_best["ev"] if hybrid_best else None,
        "hybrid_p_make": hybrid_best["p_make"] if hybrid_best else None,
        "hybrid_sigma": hybrid_best["sigma"] if hybrid_best else None,
        # Best EV across all contracts (for restraint zone analysis)
        "best_ev": max((c["ev"] for c in all_contracts), default=None),
        "best_mu": max((c["mu"] for c in all_contracts), default=None),
        "best_p_make": (
            max(all_contracts, key=lambda c: c["ev"])["p_make"]
            if all_contracts
            else None
        ),
        "all_contracts": all_contracts,
    }
    return result


# %%
# --- Parse hand from JSONL format ---
def parse_hand(raw_hand: list) -> list:
    """Parse hand from JSONL [suit, rank] pairs to Card objects."""
    return [Card(suit=c[0], rank=c[1]) for c in raw_hand]


def get_matchup_id(record: dict) -> str:
    """Extract matchup ID using dual-field fallback."""
    return record.get("matchup_id") or record.get("strategy_id", "")


def is_cross_matchup(record: dict) -> bool:
    """Identify cross-matchups by participant names, not position."""
    mid = get_matchup_id(record)
    return "_vs_" in mid and "self_play" not in mid


# %% [markdown]
# ## S1c: Load Data (JSONL or Synthetic Fallback)

# %%
_data_loaded = False
records = []

if C33_RUN_DIR and artifact is not None:
    logs_dir = Path(C33_RUN_DIR) / "logs"
    if logs_dir.is_dir():
        log_files = sorted(logs_dir.glob("*.jsonl"))
        for lf in log_files:
            with open(lf) as f:
                for line in f:
                    rec = json.loads(line)
                    if rec.get("event") == "hand_end" and "hands" in rec:
                        mid = get_matchup_id(rec)
                        rec["_matchup_id"] = mid
                        records.append(rec)

        # Filter to cross-matchups only
        records = [r for r in records if is_cross_matchup(r)]

        # Apply deal limit with stratified sampling to preserve seat-direction
        # balance. JSONL files are sequential per matchup, so global truncation
        # would only keep one direction (e.g., hybrid_olsa_vs_olsa).
        if len(records) > _max_deals:
            from collections import defaultdict

            by_matchup = defaultdict(list)
            for r in records:
                by_matchup[r["_matchup_id"]].append(r)
            n_matchups = len(by_matchup)
            per_matchup = _max_deals // max(n_matchups, 1)
            records = []
            for mid_key in sorted(by_matchup):
                records.extend(by_matchup[mid_key][:per_matchup])
            print(
                f"Stratified sampling: {n_matchups} matchups, "
                f"{per_matchup} deals each → {len(records)} total"
            )

        if records:
            _data_loaded = True
            print(f"Loaded {len(records)} cross-matchup hand_end records from JSONL")
    else:
        print(f"Logs directory not found: {logs_dir}")

if not _data_loaded:
    print("Using synthetic fallback for SMOKE/CI mode")

# %%
# --- Synthetic fallback ---
if not _data_loaded:
    from bid_euchre.core.cards import create_deck

    rng_synth = np.random.RandomState(SEED)
    deck_cards = create_deck()
    n_synth = _max_deals

    for deal_id in range(n_synth):
        rng_synth.shuffle(deck_cards)
        hands = [deck_cards[i * 10 : (i + 1) * 10] for i in range(4)]
        # Pick a random winner seat and contract
        winner_seat = int(rng_synth.randint(0, 4))
        contract = str(rng_synth.choice(["suit", "high", "low"]))
        trump = (
            str(rng_synth.choice(["C", "D", "H", "S"])) if contract == "suit" else None
        )
        winning_bid = int(rng_synth.randint(3, 8))
        t0 = int(rng_synth.randint(2, 9))
        t1 = 10 - t0
        made = t0 >= winning_bid if winner_seat in (0, 2) else t1 >= winning_bid

        records.append(
            {
                "event": "hand_end",
                "deal_id": f"synth_{deal_id}",
                "hands": [[[c.suit, c.rank] for c in h] for h in hands],
                "bidder_position": winner_seat,
                "contract": contract,
                "trump": trump,
                "winning_bid": winning_bid,
                "t0": t0,
                "t1": t1,
                "made_bid": made,
                "_matchup_id": "hybrid_olsa_vs_olsa",
                "matchup_id": "hybrid_olsa_vs_olsa",
            }
        )
    _data_loaded = True
    print(f"Generated {n_synth} synthetic deals")

# %%
# --- Fail-fast gates ---
n_deals = len(records)
assert n_deals >= 1, f"No records loaded (n_deals={n_deals})"
if MODE in ("QUICK", "FULL"):
    assert n_deals >= 100, f"Insufficient deals for {MODE}: {n_deals}"

print(f"\n{'=' * 60}")
print("DATA SUMMARY")
print(f"{'=' * 60}")
print(f"  Records:    {n_deals}")
print(f"  Mode:       {MODE}")
print(f"  Data type:  {'JSONL' if C33_RUN_DIR else 'synthetic'}")

# %% [markdown]
# # S2: Decision Replay Engine
#
# **Tier A:** Intrinsic replay — all 4 seats, `current_high_bid=0`, prediction-only.
# **Tier B:** Outcome-validated — auction winner only, includes actual outcomes.

# %%
# --- Tier A: Intrinsic replay (all seats, predicted metrics only) ---
tier_a_rows = []
for record in records:
    mid = record.get("_matchup_id", get_matchup_id(record))
    deal_id = record.get("deal_id", "")
    for seat in range(4):
        hand_cards = parse_hand(record["hands"][seat])
        result = replay_bidding_decision(hand_cards, artifact)
        # Strip all_contracts to save memory
        result.pop("all_contracts", None)
        result["deal_id"] = deal_id
        result["seat"] = seat
        result["matchup_id"] = mid
        tier_a_rows.append(result)

df_intrinsic = pd.DataFrame(tier_a_rows)
print(f"Tier A: {len(df_intrinsic)} rows ({n_deals} deals x 4 seats)")

# %%
# --- Tier A fail-fast gates ---
hybrid_bids = df_intrinsic["hybrid_bids"].sum()
olsa_bids = df_intrinsic["olsa_bids"].sum()
assert (
    hybrid_bids <= olsa_bids
), f"Hybrid bids more than OLSa: {hybrid_bids} vs {olsa_bids}"
print(f"OLSa bids: {olsa_bids} ({olsa_bids / len(df_intrinsic) * 100:.1f}%)")
print(f"Hybrid bids: {hybrid_bids} ({hybrid_bids / len(df_intrinsic) * 100:.1f}%)")
print(f"Restraint zone (OLSa-only): {olsa_bids - hybrid_bids}")

# %%
# --- Tier B: Outcome-validated replay (auction winner only) ---
tier_b_rows = []
for record in records:
    winner_seat = record.get("bidder_position")
    if winner_seat is None:
        continue  # all-pass redeal

    hand_cards = parse_hand(record["hands"][winner_seat])
    result = replay_bidding_decision(hand_cards, artifact)
    result.pop("all_contracts", None)

    # Compute P(make) and EV for the ACTUAL contract played
    actual_cf = record["contract"]
    actual_trump = record.get("trump")
    actual_bid = record["winning_bid"]
    if actual_cf in ("high", "low"):
        actual_features = get_hand_features(hand_cards, actual_cf, None)
    else:
        actual_features = get_hand_features(hand_cards, "suit", actual_trump)

    actual_mu = predict_mu(artifact, actual_cf, actual_features)
    actual_sigma = get_sigma(artifact, actual_cf)
    actual_p_make = compute_p_make(actual_mu, actual_sigma, actual_bid)
    actual_ev = compute_ev(actual_mu, actual_sigma, actual_bid)

    deal_id = record.get("deal_id", "")
    mid = record.get("_matchup_id", get_matchup_id(record))

    result["deal_id"] = deal_id
    result["winner_seat"] = winner_seat
    result["matchup_id"] = mid
    result["actual_contract"] = record["contract"]
    result["actual_trump"] = record.get("trump")
    result["actual_bid"] = actual_bid
    result["actual_made"] = record.get("made_bid")
    result["actual_mu"] = actual_mu
    result["actual_p_make"] = actual_p_make
    result["actual_ev"] = actual_ev

    # Contract match flags for calibration stratification
    hybrid_contract = result.get("hybrid_contract")
    olsa_contract = result.get("olsa_contract")
    # Map actual contract to label format for comparison
    if actual_cf == "suit":
        actual_label = actual_trump
    else:
        actual_label = actual_cf.upper()
    result["contract_match_hybrid"] = hybrid_contract == actual_label
    result["contract_match_olsa"] = olsa_contract == actual_label

    # Declaring team's tricks
    winner_team = 0 if winner_seat in (0, 2) else 1
    result["actual_tricks"] = record["t0"] if winner_team == 0 else record["t1"]

    # Net differential for declaring team
    if result["actual_made"]:
        result["actual_net"] = 2 * result["actual_tricks"] - 10
    else:
        result["actual_net"] = result["actual_tricks"] - actual_bid - 10

    tier_b_rows.append(result)

df_outcome = pd.DataFrame(tier_b_rows)
print(f"Tier B: {len(df_outcome)} rows (deals with auction winner)")

# %%
# --- Tier B fail-fast gates ---
if not df_outcome.empty:
    assert df_outcome["winner_seat"].notna().all(), "Missing winner_seat in Tier B"
    assert df_outcome["actual_made"].notna().all(), "Missing actual_made in Tier B"
    print(f"Tier B validation passed ({len(df_outcome)} rows)")

# %%
# --- Assign divergence categories ---
df_intrinsic["category"] = "both_pass"
df_intrinsic.loc[
    df_intrinsic["olsa_bids"] & df_intrinsic["hybrid_bids"], "category"
] = "both_bid"
df_intrinsic.loc[
    df_intrinsic["olsa_bids"] & ~df_intrinsic["hybrid_bids"], "category"
] = "olsa_only_bid"
df_intrinsic.loc[
    ~df_intrinsic["olsa_bids"] & df_intrinsic["hybrid_bids"], "category"
] = "hybrid_only_bid"

if not df_outcome.empty:
    df_outcome["category"] = "both_pass"
    df_outcome.loc[df_outcome["olsa_bids"] & df_outcome["hybrid_bids"], "category"] = (
        "both_bid"
    )
    df_outcome.loc[df_outcome["olsa_bids"] & ~df_outcome["hybrid_bids"], "category"] = (
        "olsa_only_bid"
    )
    df_outcome.loc[~df_outcome["olsa_bids"] & df_outcome["hybrid_bids"], "category"] = (
        "hybrid_only_bid"
    )

print("\nTier A divergence categories:")
print(df_intrinsic["category"].value_counts().to_string())

# %% [markdown]
# # S3: Aggregate EV Distribution
#
# Intrinsic analysis (`current_high_bid=0`, no auction interaction).
# Charts use `df_intrinsic` (Tier A, all seats).

# %%
# --- Chart 3a: Overlaid EV histograms faceted by contract_type ---
# Use the best EV per hand for OLSa-eligible hands
olsa_eligible = df_intrinsic[df_intrinsic["olsa_bids"]].copy()
if not olsa_eligible.empty:
    # Determine contract_type from olsa's chosen contract
    def _contract_family(label):
        if label in ("C", "D", "H", "S"):
            return "suit"
        elif label == "HIGH":
            return "high"
        elif label == "LOW":
            return "low"
        return "unknown"

    olsa_eligible["contract_type"] = olsa_eligible["olsa_contract"].apply(
        _contract_family
    )

    ctypes = sorted(olsa_eligible["contract_type"].unique())
    n_panels = max(1, len(ctypes))
    fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 5), sharey=False)
    if not hasattr(axes, "__len__"):
        axes = [axes]

    for ax, ctype in zip(axes, ctypes):
        ct_data = olsa_eligible[olsa_eligible["contract_type"] == ctype]
        hybrid_also = ct_data[ct_data["hybrid_bids"]]
        restraint = ct_data[~ct_data["hybrid_bids"]]

        bins = np.linspace(
            ct_data["best_ev"].min() - 0.5, ct_data["best_ev"].max() + 0.5, 40
        )
        ax.hist(
            hybrid_also["best_ev"],
            bins=bins,
            alpha=0.6,
            color="steelblue",
            label=f"Both bid (n={len(hybrid_also)})",
        )
        ax.hist(
            restraint["best_ev"],
            bins=bins,
            alpha=0.6,
            color="indianred",
            label=f"Restraint zone (n={len(restraint)})",
        )
        ax.axvline(0, color="black", linewidth=1, linestyle="--", label="EV=0")
        ax.set_xlabel("Best EV")
        ax.set_ylabel("Count")
        ax.set_title(f"EV Distribution: {ctype}\n(Intrinsic, current_high_bid=0)")
        ax.legend(fontsize=8)

    plt.tight_layout()
    plt.show()
else:
    print("No OLSa-eligible hands for EV histogram")

# %%
# --- Chart 3b: Decision scatterplot (mu vs P(make)) faceted by contract_type ---
if not olsa_eligible.empty:
    ctypes = sorted(olsa_eligible["contract_type"].unique())
    n_panels = max(1, len(ctypes))
    fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 5), sharey=True)
    if not hasattr(axes, "__len__"):
        axes = [axes]

    # Color by category
    cat_colors = {
        "both_bid": "#4CAF50",
        "both_pass": "#999999",
        "olsa_only_bid": "#F44336",
        "hybrid_only_bid": "#2196F3",
    }
    for ax, ctype in zip(axes, ctypes):
        ct_data = df_intrinsic[
            df_intrinsic["olsa_contract"].apply(_contract_family) == ctype
        ].copy()
        # Only show hands where olsa has a bid (otherwise mu/p_make not meaningful)
        ct_data = ct_data[ct_data["olsa_bids"] | ct_data["hybrid_bids"]]
        if ct_data.empty:
            continue

        for cat, color in cat_colors.items():
            mask = ct_data["category"] == cat
            if mask.sum() == 0:
                continue
            ax.scatter(
                ct_data.loc[mask, "best_mu"],
                ct_data.loc[mask, "best_p_make"],
                c=color,
                label=f"{cat} (n={mask.sum()})",
                alpha=0.4,
                s=10,
                rasterized=True,
            )

        ax.set_xlabel("mu (predicted tricks)")
        ax.set_ylabel("P(make)")
        ax.set_title(f"Decision Boundary: {ctype}\n(Intrinsic, current_high_bid=0)")
        ax.legend(fontsize=7, markerscale=2)

    plt.tight_layout()
    plt.show()
else:
    print("No data for decision scatterplot")

# %%
# --- Assert gate: restraint zone non-empty ---
restraint_count = ((df_intrinsic["olsa_bids"]) & (~df_intrinsic["hybrid_bids"])).sum()
assert restraint_count > 0, "No restraint zone hands found"
print(
    f"Restraint zone: {restraint_count} hands "
    f"({restraint_count / len(df_intrinsic) * 100:.1f}%)"
)

# %% [markdown]
# # S3.5: P(make) Calibration Check
#
# Tests whether the Gaussian P(make) estimates are directionally correct
# against actual make rates. Uses Tier B data (auction winner only).

# %%
if not df_outcome.empty and "actual_p_make" in df_outcome.columns:
    # Bin hands by predicted P(make)
    df_cal = df_outcome[["actual_p_make", "actual_made", "actual_contract"]].copy()
    df_cal["p_make_bin"] = pd.cut(
        df_cal["actual_p_make"],
        bins=np.linspace(0, 1, 11),
        labels=[f"{i * 10}-{(i + 1) * 10}%" for i in range(10)],
        include_lowest=True,
    )
    df_cal["contract_type"] = df_cal["actual_contract"].apply(
        lambda c: "suit" if c not in ("high", "low") else c
    )

    # Compute calibration per bin (pooled)
    cal_agg = (
        df_cal.groupby("p_make_bin", observed=True)
        .agg(
            count=("actual_made", "size"),
            actual_make_rate=("actual_made", "mean"),
            predicted_p_make=("actual_p_make", "mean"),
        )
        .reset_index()
    )

    # Wilson binomial CIs
    def _wilson_ci(p, n, z=1.96):
        if n == 0:
            return 0.0, 1.0
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
        return max(0, center - spread), min(1, center + spread)

    cal_agg["ci_lo"] = cal_agg.apply(
        lambda r: _wilson_ci(r["actual_make_rate"], r["count"])[0], axis=1
    )
    cal_agg["ci_hi"] = cal_agg.apply(
        lambda r: _wilson_ci(r["actual_make_rate"], r["count"])[1], axis=1
    )

    # --- Pooled calibration plot ---
    fig, ax = plt.subplots(figsize=(7, 6))
    valid = cal_agg[cal_agg["count"] >= 5]
    if not valid.empty:
        ax.errorbar(
            valid["predicted_p_make"],
            valid["actual_make_rate"],
            yerr=[
                valid["actual_make_rate"] - valid["ci_lo"],
                valid["ci_hi"] - valid["actual_make_rate"],
            ],
            fmt="o-",
            capsize=3,
            label="Pooled",
        )
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect calibration")
    ax.set_xlabel("Predicted P(make)")
    ax.set_ylabel("Actual make rate")
    ax.set_title("P(make) Calibration (Outcome-validated, auction winner only)")
    ax.legend()
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    plt.tight_layout()
    plt.show()

    # --- Faceted calibration by contract_type ---
    ctypes = sorted(df_cal["contract_type"].unique())
    if len(ctypes) > 1:
        n_panels = len(ctypes)
        fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 5), sharey=True)
        if not hasattr(axes, "__len__"):
            axes = [axes]
        for ax, ctype in zip(axes, ctypes):
            ct_cal = df_cal[df_cal["contract_type"] == ctype]
            ct_agg = (
                ct_cal.groupby("p_make_bin", observed=True)
                .agg(
                    count=("actual_made", "size"),
                    actual_make_rate=("actual_made", "mean"),
                    predicted_p_make=("actual_p_make", "mean"),
                )
                .reset_index()
            )
            ct_valid = ct_agg[ct_agg["count"] >= 5]
            if not ct_valid.empty:
                ct_valid = ct_valid.copy()
                ct_valid["ci_lo"] = ct_valid.apply(
                    lambda r: _wilson_ci(r["actual_make_rate"], r["count"])[0],
                    axis=1,
                )
                ct_valid["ci_hi"] = ct_valid.apply(
                    lambda r: _wilson_ci(r["actual_make_rate"], r["count"])[1],
                    axis=1,
                )
                ax.errorbar(
                    ct_valid["predicted_p_make"],
                    ct_valid["actual_make_rate"],
                    yerr=[
                        ct_valid["actual_make_rate"] - ct_valid["ci_lo"],
                        ct_valid["ci_hi"] - ct_valid["actual_make_rate"],
                    ],
                    fmt="o-",
                    capsize=3,
                )
            ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
            ax.set_xlabel("Predicted P(make)")
            ax.set_ylabel("Actual make rate")
            ax.set_title(f"Calibration: {ctype}")
            ax.set_xlim(-0.05, 1.05)
            ax.set_ylim(-0.05, 1.05)
        plt.tight_layout()
        plt.show()

    # --- Assert gate: positive calibration correlation ---
    bin_df = cal_agg[cal_agg["count"] >= 10]
    if len(bin_df) >= 3:
        corr = bin_df["predicted_p_make"].corr(bin_df["actual_make_rate"])
        if MODE in ("QUICK", "FULL"):
            assert corr > 0, f"P(make) calibration has negative correlation: {corr:.3f}"
        elif corr <= 0:
            warnings.warn(
                f"P(make) calibration has non-positive correlation: {corr:.3f} "
                f"(SMOKE mode, may be due to small sample size)",
                stacklevel=2,
            )
        print(f"P(make) calibration correlation: {corr:.3f}")
    else:
        warnings.warn(
            f"Only {len(bin_df)} bins with >=10 samples — insufficient for "
            f"calibration correlation (need >= 3)",
            stacklevel=2,
        )
else:
    print("No outcome data for P(make) calibration")

# %% [markdown]
# # S4: Decision Divergence Table
#
# Counts and predicted metrics from Tier A; outcome metrics from Tier B.

# %%
# --- Tier A divergence table ---
print("=" * 70)
print("DECISION DIVERGENCE — Tier A (intrinsic, all seats)")
print("=" * 70)

categories = ["both_bid", "both_pass", "olsa_only_bid", "hybrid_only_bid"]
div_rows = []
for cat in categories:
    mask = df_intrinsic["category"] == cat
    count = mask.sum()
    pct = count / len(df_intrinsic) * 100
    mean_ev = df_intrinsic.loc[mask, "best_ev"].mean() if count > 0 else float("nan")
    mean_mu = df_intrinsic.loc[mask, "best_mu"].mean() if count > 0 else float("nan")
    mean_p = df_intrinsic.loc[mask, "best_p_make"].mean() if count > 0 else float("nan")
    div_rows.append(
        {
            "category": cat,
            "count": count,
            "pct": pct,
            "mean_ev": mean_ev,
            "mean_mu": mean_mu,
            "mean_p_make": mean_p,
        }
    )

df_div_a = pd.DataFrame(div_rows)
print(df_div_a.to_string(index=False))

# %%
# --- Tier B divergence with outcomes ---
if not df_outcome.empty:
    print("\n" + "=" * 70)
    print("DECISION DIVERGENCE — Tier B (outcome-validated, auction winner only)")
    print("=" * 70)

    div_b_rows = []
    for cat in categories:
        mask = df_outcome["category"] == cat
        count = mask.sum()
        if count > 0:
            mean_tricks = df_outcome.loc[mask, "actual_tricks"].mean()
            mean_net = df_outcome.loc[mask, "actual_net"].mean()
            set_rate = (
                1 - df_outcome.loc[mask, "actual_made"].mean()
                if "actual_made" in df_outcome.columns
                else float("nan")
            )
        else:
            mean_tricks = float("nan")
            mean_net = float("nan")
            set_rate = float("nan")

        div_b_rows.append(
            {
                "category": cat,
                "count_tier_b": count,
                "mean_tricks": mean_tricks,
                "mean_net": mean_net,
                "set_rate": set_rate,
            }
        )

    df_div_b = pd.DataFrame(div_b_rows)
    print(df_div_b.to_string(index=False))

    # Assert: restraint zone has lower tricks than both-bid zone
    restraint_data = df_outcome[df_outcome["category"] == "olsa_only_bid"]
    both_bid_data = df_outcome[df_outcome["category"] == "both_bid"]
    if len(restraint_data) > 0 and len(both_bid_data) > 0:
        restraint_tricks = restraint_data["actual_tricks"].mean()
        both_bid_tricks = both_bid_data["actual_tricks"].mean()
        if MODE in ("QUICK", "FULL"):
            assert restraint_tricks < both_bid_tricks, (
                f"Restraint zone has higher tricks ({restraint_tricks:.2f}) "
                f"than both-bid zone ({both_bid_tricks:.2f})"
            )
        elif restraint_tricks >= both_bid_tricks:
            warnings.warn(
                f"Restraint zone tricks ({restraint_tricks:.2f}) >= "
                f"both-bid ({both_bid_tricks:.2f}) — may be SMOKE noise",
                stacklevel=2,
            )
        print(
            f"\nRestraint zone mean tricks: {restraint_tricks:.2f} "
            f"vs both-bid: {both_bid_tricks:.2f}"
        )

# %%
# --- Faceted by contract_type (Tier A) ---
if not olsa_eligible.empty:
    print("\n" + "=" * 70)
    print("DIVERGENCE BY CONTRACT TYPE — Tier A")
    print("=" * 70)

    for ctype in sorted(olsa_eligible["contract_type"].unique()):
        ct_data = olsa_eligible[olsa_eligible["contract_type"] == ctype]
        print(f"\n  {ctype}:")
        for cat in categories:
            mask = ct_data["category"] == cat
            count = mask.sum()
            if count > 0:
                print(f"    {cat}: {count} ({count / len(ct_data) * 100:.1f}%)")

# %%
# --- Per-bid-level breakdown (Tier A) ---
print("\n" + "=" * 70)
print("PER-BID-LEVEL RESTRAINT — Tier A")
print("=" * 70)

olsa_bidding = df_intrinsic[df_intrinsic["olsa_bids"]].copy()
if not olsa_bidding.empty:
    olsa_bidding["bid_level"] = olsa_bidding["olsa_bid_n"].apply(
        lambda n: str(int(n)) if n is not None and n <= 5 else "6+"
    )
    bid_levels = sorted(olsa_bidding["bid_level"].unique())

    bid_rows = []
    for bl in bid_levels:
        bl_data = olsa_bidding[olsa_bidding["bid_level"] == bl]
        olsa_count = len(bl_data)
        hybrid_count = bl_data["hybrid_bids"].sum()
        restraint_count_bl = olsa_count - hybrid_count
        restraint_pct = restraint_count_bl / olsa_count * 100 if olsa_count > 0 else 0
        restraint_ev = (
            bl_data[~bl_data["hybrid_bids"]]["best_ev"].mean()
            if restraint_count_bl > 0
            else float("nan")
        )
        bid_rows.append(
            {
                "bid_level": bl,
                "olsa_bids": olsa_count,
                "hybrid_bids": hybrid_count,
                "restraint": restraint_count_bl,
                "restraint_pct": restraint_pct,
                "mean_ev_restraint": restraint_ev,
            }
        )

    df_bid_level = pd.DataFrame(bid_rows)
    print(df_bid_level.to_string(index=False))

# %% [markdown]
# # S5: Worked Example Hand
#
# Selects a hand from the restraint zone where OLSa would bid and got set.

# %%
worked_example = None
if not df_outcome.empty:
    # Prefer: restraint zone + SET outcome + suit contract
    candidates = df_outcome[
        (df_outcome["category"] == "olsa_only_bid")
        & (df_outcome["actual_made"] == False)  # noqa: E712
    ]
    # Prefer suit contracts
    suit_cands = candidates[candidates["actual_contract"] == "suit"]
    if not suit_cands.empty:
        worked_example = suit_cands.iloc[0]
    elif not candidates.empty:
        worked_example = candidates.iloc[0]
    else:
        # Fallback: any restraint zone hand
        restraint_cands = df_outcome[df_outcome["category"] == "olsa_only_bid"]
        if not restraint_cands.empty:
            worked_example = restraint_cands.iloc[0]

if worked_example is not None:
    # Find the original record to get the hand
    deal_id = worked_example["deal_id"]
    seat = worked_example["winner_seat"]
    rec = next((r for r in records if r.get("deal_id") == deal_id), None)

    print("=" * 60)
    print("WORKED EXAMPLE — Restraint Zone Hand")
    print("=" * 60)

    if rec is not None:
        hand_cards = parse_hand(rec["hands"][seat])
        actual_cf = worked_example["actual_contract"]
        actual_trump = worked_example["actual_trump"]
        actual_bid = worked_example["actual_bid"]

        print(f"Deal: {deal_id}, Seat: {seat}")
        print(
            f"Contract: {actual_cf}"
            + (f" (trump={actual_trump})" if actual_trump else "")
            + f", Bid: {actual_bid} tricks"
        )
        print(f"Hand: {', '.join(str(c) for c in hand_cards)}")

        # Get features for the actual contract
        if actual_cf in ("high", "low"):
            features = get_hand_features(hand_cards, actual_cf, None)
        else:
            features = get_hand_features(hand_cards, "suit", actual_trump)

        mu = predict_mu(artifact, actual_cf, features)
        sigma = get_sigma(artifact, actual_cf)
        bid_n = max(1, min(10, math.floor(mu)))

        print("\nFeatures (selected):")
        model = _get_model(artifact, actual_cf)
        for fname in model["feature_names"]:
            print(f"  {fname}: {features.get(fname, 'N/A')}")

        print("\nOLS Prediction:")
        print(f"  mu = {mu:.4f} tricks (floor -> bid {bid_n})")

        threshold = bid_n - 0.5
        z = (threshold - mu) / sigma if sigma > 0 else float("inf")
        z_capped = max(-_Z_CAP, min(_Z_CAP, z))
        p_make = compute_p_make(mu, sigma, bid_n)
        ev = compute_ev(mu, sigma, bid_n)

        # Truncated normal expectations for display
        pdf_z = norm.pdf(z_capped)
        if p_make > 1e-12:
            e_tricks_make = mu + sigma * pdf_z / p_make
        else:
            e_tricks_make = mu
        p_set = 1.0 - p_make
        if p_set > 1e-12:
            e_tricks_set = mu - sigma * pdf_z / p_set
        else:
            e_tricks_set = mu
        make_ev = 2.0 * e_tricks_make - 10.0
        set_ev = e_tricks_set - bid_n - 10.0

        print("\nGaussian EV Computation:")
        print(f"  sigma = {sigma:.4f} (residual std for {actual_cf})")
        print(f"  threshold = {bid_n} - 0.5 = {threshold}")
        print(f"  z = ({threshold} - {mu:.4f}) / {sigma:.4f} = {z:.4f}")
        print(
            f"  P(make) = 1 - Phi({z_capped:.4f}) = {p_make:.4f} ({p_make * 100:.1f}%)"
        )
        print(f"  E[tricks|make] = {e_tricks_make:.4f}")
        print(f"  E[tricks|set]  = {e_tricks_set:.4f}")
        print(f"  make_ev = 2*{e_tricks_make:.4f} - 10 = {make_ev:.4f}")
        print(f"  set_ev  = {e_tricks_set:.4f} - {bid_n} - 10 = {set_ev:.4f}")
        print(
            f"  EV = {p_make:.4f}*{make_ev:.4f} + {p_set:.4f}*{set_ev:.4f} = {ev:.4f}"
        )

        print("\nDecision:")
        print(f"  OLSa:   BID (floor(mu) = {bid_n} >= 1)    <- would bid")
        print(
            f"  Hybrid: {'BID' if ev > 0 else 'PASS'} (EV = {ev:.4f} {'>' if ev > 0 else '<='} 0)"
        )

        actual_tricks = worked_example["actual_tricks"]
        actual_made = worked_example["actual_made"]
        if actual_made:
            actual_net = 2 * actual_tricks - 10
        else:
            actual_net = actual_tricks - actual_bid - 10
        print("\nActual Outcome:")
        cmp_op = ">=" if actual_made else "<"
        print(
            f"  Won {actual_tricks} tricks -> {'MADE' if actual_made else 'SET'} "
            f"({actual_tricks} {cmp_op} {actual_bid})"
        )
        print(f"  Net differential: {actual_net}")
    else:
        print(f"  Could not find record for deal {deal_id}")
else:
    print("No suitable worked example found (may be SMOKE mode with small sample)")

# %% [markdown]
# # S6: Summary
#
# Key findings for report cross-reference.

# %%
print("=" * 60)
print("C33 ABLATION DEEP DIVE SUMMARY")
print("=" * 60)

print("\n--- Tier A: Intrinsic Decision Comparison (all seats, current_high_bid=0) ---")
print(f"Total hands replayed: {len(df_intrinsic)} ({n_deals} deals x 4 seats)")
print("Decision divergence:")
for _, row in df_div_a.iterrows():
    cat = row["category"]
    marker = " <- restraint zone" if cat == "olsa_only_bid" else ""
    print(f"  {cat:20s}: {int(row['count']):5d} ({row['pct']:.1f}%){marker}")

# Restraint zone predicted metrics
restraint_mask = df_intrinsic["category"] == "olsa_only_bid"
if restraint_mask.sum() > 0:
    rz = df_intrinsic[restraint_mask]
    print("\nRestraint zone (predicted metrics):")
    print(f"  Mean EV:      {rz['best_ev'].mean():.4f}")
    print(f"  Mean P(make): {rz['best_p_make'].mean():.4f}")
    print(f"  Mean mu:      {rz['best_mu'].mean():.4f}")

if not df_outcome.empty:
    print("\n--- Tier B: Outcome-Validated (auction winner only) ---")
    print(f"Total deals with winner: {len(df_outcome)}")

    restraint_b = df_outcome[df_outcome["category"] == "olsa_only_bid"]
    both_bid_b = df_outcome[df_outcome["category"] == "both_bid"]
    print(f"Restraint zone with outcomes: {len(restraint_b)} deals")

    if len(restraint_b) > 0:
        print("\nRestraint zone (actual outcomes):")
        print(f"  Mean tricks_won: {restraint_b['actual_tricks'].mean():.2f}")
        set_rate_rz = 1 - restraint_b["actual_made"].mean()
        print(f"  Set rate:        {set_rate_rz:.1%}", end="")
        if len(both_bid_b) > 0:
            set_rate_bb = 1 - both_bid_b["actual_made"].mean()
            print(f" (vs {set_rate_bb:.1%} in both-bid zone)")
        else:
            print()
        print(f"  Mean net:        {restraint_b['actual_net'].mean():.2f}")

# Per-bid-level summary
if not olsa_bidding.empty and "bid_level" in olsa_bidding.columns:
    print("\nPer-bid-level restraint (Tier A):")
    for _, row in df_bid_level.iterrows():
        print(
            f"  Bid {row['bid_level']}: {row['restraint_pct']:.1f}% restraint rate "
            f"({int(row['restraint'])} hands)"
        )

# Per-contract-type summary
if not olsa_eligible.empty:
    print("\nPer-contract-type wrapper effect:")
    for ctype in sorted(olsa_eligible["contract_type"].unique()):
        ct_data = olsa_eligible[olsa_eligible["contract_type"] == ctype]
        restraint_rate = (ct_data["category"] == "olsa_only_bid").mean()
        print(f"  {ctype}: restraint rate {restraint_rate:.1%} (n={len(ct_data)})")

print(f"\n{'=' * 60}")
