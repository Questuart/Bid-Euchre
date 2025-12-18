#!/usr/bin/env python3
"""Train improved linear (OLS) trick prediction models.

Linear v2 goals:
- Keep models linear and interpretable
- Capture key regime/interaction effects observed in heatmaps

Models:
- suit: split bowers into rb/lb + add ruffing interaction
- high: keep aces + add double-ace-stopper signal
- low: tens + penalty for high cards + ten/jack stopper signal

Outputs:
- data/models/linear_v2_regression/linear_v2_<contract>.pkl

Usage:
  PYTHONPATH=src python experiments/train_linear_v2_regression.py
"""

import json
import os
import pickle
from typing import Dict, List, Tuple

import numpy as np


GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
GREEDY_VAL = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.val.jsonl"
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"

OUTPUT_DIR = "data/models/linear_v2_regression"
os.makedirs(OUTPUT_DIR, exist_ok=True)


FEATURES_V2: Dict[str, List[str]] = {
    "suit": [
        "trump_count",
        "trump_rb_count",
        "trump_lb_count",
        "offsuit_aces",
        "void_count",
        "trump_count_x_void_count",
    ],
    "high": [
        "offsuit_aces",
        "offsuit_suits_with_double_ace",
    ],
    "low": [
        "offsuit_tens_count",
        "high_card_count",
        "double_ten_jack_count",
    ],
}


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot)


def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


class SimpleOLS:
    """OLS regression via normal equation."""

    def __init__(self):
        self.coef_: np.ndarray | None = None
        self.intercept_: float | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SimpleOLS":
        X_with_intercept = np.column_stack([np.ones(len(X)), X])
        XtX = X_with_intercept.T @ X_with_intercept
        Xty = X_with_intercept.T @ y
        beta = np.linalg.solve(XtX, Xty)
        self.intercept_ = float(beta[0])
        self.coef_ = beta[1:]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.coef_ is not None and self.intercept_ is not None
        return X @ self.coef_ + self.intercept_


def load_xy(jsonl_path: str, contract_type: str, feature_names: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    X_list: List[List[float]] = []
    y_list: List[int] = []

    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("event") != "hand_end":
                continue
            if rec.get("contract") != contract_type:
                continue

            feats_list = rec.get("features", [])
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)

            for player_idx, player_features in enumerate(feats_list):
                if not isinstance(player_features, dict):
                    continue

                row: List[float] = []
                ok = True
                for name in feature_names:
                    if name not in player_features:
                        ok = False
                        break
                    row.append(float(player_features[name]))

                if not ok:
                    continue

                team_tricks = t0 if player_idx in (0, 2) else t1
                X_list.append(row)
                y_list.append(int(team_tricks))

    return np.array(X_list, dtype=float), np.array(y_list, dtype=float)


def train_one(contract_type: str, feature_names: List[str]) -> Dict[str, object]:
    print("\n" + "=" * 90)
    print(f"Linear v2: {contract_type} | features ({len(feature_names)}): {', '.join(feature_names)}")
    print("=" * 90)

    X_tr, y_tr = load_xy(GREEDY_TRAIN, contract_type, feature_names)
    X_va, y_va = load_xy(GREEDY_VAL, contract_type, feature_names)
    X_te, y_te = load_xy(GREEDY_TEST, contract_type, feature_names)

    print(f"Train: {len(X_tr):,} rows | Val: {len(X_va):,} | Test: {len(X_te):,}")

    model = SimpleOLS().fit(X_tr, y_tr)

    pred_tr = model.predict(X_tr)
    pred_va = model.predict(X_va)
    pred_te = model.predict(X_te)

    metrics = {
        "train_r2": r2_score(y_tr, pred_tr),
        "val_r2": r2_score(y_va, pred_va),
        "test_r2": r2_score(y_te, pred_te),
        "train_mae": mean_absolute_error(y_tr, pred_tr),
        "val_mae": mean_absolute_error(y_va, pred_va),
        "test_mae": mean_absolute_error(y_te, pred_te),
        "train_rmse": float(np.sqrt(mean_squared_error(y_tr, pred_tr))),
        "val_rmse": float(np.sqrt(mean_squared_error(y_va, pred_va))),
        "test_rmse": float(np.sqrt(mean_squared_error(y_te, pred_te))),
    }

    print("\nMetrics:")
    for split in ("train", "val", "test"):
        print(
            f"  {split.upper():<5} R²={metrics[split + '_r2']:.4f}  MAE={metrics[split + '_mae']:.4f}  RMSE={metrics[split + '_rmse']:.4f}"
        )

    print("\nCoefficients:")
    print(f"  intercept: {model.intercept_:+.4f}")
    for name, coef in zip(feature_names, model.coef_):
        print(f"  {name:<28} {coef:+.4f}")

    out_path = os.path.join(OUTPUT_DIR, f"linear_v2_{contract_type}.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(
            {
                "model": model,
                "features": feature_names,
                "contract_type": contract_type,
                "version": "linear_v2",
            },
            f,
        )

    print(f"\nSaved: {out_path}")

    return {
        "contract": contract_type,
        "features": feature_names,
        "path": out_path,
        **metrics,
    }


def main() -> None:
    print("=" * 90)
    print("Training linear v2 OLS models")
    print("=" * 90)

    results: List[Dict[str, object]] = []
    for contract, feats in FEATURES_V2.items():
        results.append(train_one(contract, feats))

    print("\n" + "=" * 90)
    print("Summary (test):")
    print("=" * 90)
    print(f"{'contract':<8} {'n_feat':<6} {'test_r2':<10} {'test_mae':<10}")
    for r in results:
        print(
            f"{r['contract']:<8} {len(r['features']):<6} {r['test_r2']:<10.4f} {r['test_mae']:<10.4f}"
        )


if __name__ == "__main__":
    main()

