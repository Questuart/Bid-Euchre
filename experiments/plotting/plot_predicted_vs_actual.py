#!/usr/bin/env python3
"""Plot predicted vs actual tricks, faceted by contract.

Creates scatter plots of predicted trick count (x) vs actual team tricks (y).
- SUIT contracts: faceted by trump suit (H/S/D/C if present)
- No-trump: faceted by contract type (HIGH vs LOW)

Uses the *current baseline models* in:
  data/models/baseline_regression/

Usage:
  PYTHONPATH=src python experiments/plot_predicted_vs_actual.py \
    --split test \
    --run-dir data/runs/hand_eval_test_greedy_42_20251217_200200 \
    --out-dir data/runs/hand_eval_test_greedy_42_20251217_200200/reports/train_only/bidding_strategy/pred_vs_actual
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt


# Needed for unpickling baseline models
class SimpleOLS:
    def __init__(self):
        self.coef_ = None
        self.intercept_ = None

    def predict(self, X):
        return X @ self.coef_ + self.intercept_


@dataclass
class ModelSpec:
    features: List[str]
    intercept: float
    coef: np.ndarray

    def predict_one(self, feats: Dict[str, float]) -> float:
        x = np.array([float(feats.get(k, 0.0)) for k in self.features], dtype=float)
        return float(self.intercept + np.dot(self.coef, x))


def load_baseline_models(model_dir: str) -> Dict[str, ModelSpec]:
    models: Dict[str, ModelSpec] = {}
    for contract in ("suit", "high", "low"):
        path = os.path.join(model_dir, f"baseline_regression_{contract}.pkl")
        with open(path, "rb") as f:
            d = pickle.load(f)
        model = d["model"]
        models[contract] = ModelSpec(
            features=list(d["features"]),
            intercept=float(model.intercept_),
            coef=np.array(model.coef_, dtype=float),
        )
    return models


def iter_hand_end_rows(jsonl_path: str) -> Iterable[Tuple[str, Optional[str], Dict[str, float], int]]:
    """Yield (contract_type, trump_suit, player_features, team_tricks)."""
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("event") != "hand_end":
                continue

            contract = rec.get("contract")
            if contract not in ("suit", "high", "low"):
                continue

            trump = rec.get("trump")
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)

            for pidx, feats in enumerate(rec.get("features", [])):
                if not isinstance(feats, dict):
                    continue
                actual = t0 if pidx in (0, 2) else t1
                yield contract, trump, feats, int(actual)


def jitter(y: np.ndarray, scale: float = 0.10, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return y + rng.normal(0.0, scale, size=len(y))


def scatter_panel(ax, x, y, title: str, n_show: int = 8000, seed: int = 0):
    rng = np.random.default_rng(seed)
    if len(x) > n_show:
        idx = rng.choice(len(x), size=n_show, replace=False)
        x = x[idx]
        y = y[idx]

    yj = jitter(y, scale=0.12, seed=seed)

    ax.scatter(x, yj, s=10, alpha=0.25, color="#2c7fb8", edgecolors="none")

    # Reference y=x line
    ax.plot([0, 10], [0, 10], color="#444", linewidth=1.5, linestyle="--", alpha=0.8)

    # Binned mean trend (by predicted)
    bins = np.linspace(0, 10, 21)
    digit = np.digitize(x, bins) - 1
    xs, ys = [], []
    for b in range(len(bins) - 1):
        m = digit == b
        if np.sum(m) < 50:
            continue
        xs.append(float(np.mean(x[m])))
        ys.append(float(np.mean(y[m])))
    if len(xs) >= 2:
        ax.plot(xs, ys, color="#d95f02", linewidth=2.0, label="binned mean")
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, 10.5)
    ax.set_xticks(range(0, 11))
    ax.set_yticks(range(0, 11))
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.6)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("Predicted tricks")
    ax.set_ylabel("Actual team tricks")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-dir",
        required=True,
        help="Run directory containing splits/*.jsonl",
    )
    ap.add_argument(
        "--split",
        default="test",
        choices=["train", "val", "test"],
        help="Which split to plot",
    )
    ap.add_argument(
        "--out-dir",
        required=True,
        help="Where to write PNGs",
    )
    ap.add_argument(
        "--model-dir",
        default="data/models/baseline_regression",
        help="Directory containing baseline_regression_*.pkl",
    )
    ap.add_argument(
        "--max-points",
        type=int,
        default=8000,
        help="Max points plotted per facet",
    )

    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # Find split JSONL
    splits_dir = os.path.join(args.run_dir, "splits")
    candidates = [
        os.path.join(splits_dir, fn)
        for fn in os.listdir(splits_dir)
        if fn.endswith(f".{args.split}.jsonl")
    ]
    if not candidates:
        raise SystemExit(f"No *.{args.split}.jsonl found in {splits_dir}")
    if len(candidates) > 1:
        # pick deterministic: shortest filename then lexicographic
        candidates = sorted(candidates, key=lambda p: (len(os.path.basename(p)), os.path.basename(p)))
    jsonl_path = candidates[0]

    models = load_baseline_models(args.model_dir)

    # Collect predictions
    suit_by_trump: Dict[str, List[Tuple[float, int]]] = {}
    hl_by_contract: Dict[str, List[Tuple[float, int]]] = {"high": [], "low": []}

    for contract, trump, feats, actual in iter_hand_end_rows(jsonl_path):
        pred = models[contract].predict_one(feats)
        pred = float(np.clip(pred, 0.0, 10.0))

        if contract == "suit":
            key = (trump or "?")
            suit_by_trump.setdefault(key, []).append((pred, actual))
        else:
            hl_by_contract[contract].append((pred, actual))

    # ---- Plot suit facets by trump
    trump_order = ["H", "S", "D", "C"]
    trump_present = [t for t in trump_order if t in suit_by_trump] + [t for t in sorted(suit_by_trump) if t not in trump_order]

    if trump_present:
        n = len(trump_present)
        ncols = 2
        nrows = int(np.ceil(n / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(12, 5.5 * nrows), squeeze=False)
        fig.suptitle(f"SUIT contracts: predicted vs actual ({args.split} split)", fontsize=14, fontweight="bold")

        for i, t in enumerate(trump_present):
            ax = axes[i // ncols][i % ncols]
            arr = suit_by_trump[t]
            x = np.array([p for p, _ in arr], dtype=float)
            y = np.array([a for _, a in arr], dtype=float)
            scatter_panel(ax, x, y, title=f"Trump = {t} (n={len(arr):,})", n_show=args.max_points, seed=10 + i)

        # hide unused
        for j in range(n, nrows * ncols):
            axes[j // ncols][j % ncols].axis("off")

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        out_path = os.path.join(args.out_dir, f"pred_vs_actual_suit_by_trump_{args.split}.png")
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    # ---- Plot high/low facets
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), squeeze=False)
    fig.suptitle(f"No-trump: predicted vs actual ({args.split} split)", fontsize=14, fontweight="bold")

    for i, c in enumerate(["high", "low"]):
        ax = axes[0][i]
        arr = hl_by_contract[c]
        x = np.array([p for p, _ in arr], dtype=float)
        y = np.array([a for _, a in arr], dtype=float)
        scatter_panel(ax, x, y, title=f"{c.upper()} (n={len(arr):,})", n_show=args.max_points, seed=30 + i)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = os.path.join(args.out_dir, f"pred_vs_actual_high_low_{args.split}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print("Wrote:")
    if trump_present:
        print(f"  {os.path.join(args.out_dir, f'pred_vs_actual_suit_by_trump_{args.split}.png')}")
    print(f"  {os.path.join(args.out_dir, f'pred_vs_actual_high_low_{args.split}.png')}")


if __name__ == "__main__":
    main()
