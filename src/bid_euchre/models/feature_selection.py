"""
Forward feature selection with grouped cross-validation.

Provides stepwise forward selection using GroupKFold to prevent
hand_id leakage across CV folds.
"""

from __future__ import annotations

import logging

import numpy as np
from sklearn.model_selection import GroupKFold

logger = logging.getLogger(__name__)


def _ols_r2(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    alpha: float = 0.0,
) -> float:
    """Fit OLS (or Ridge) on train and return R² on test.

    Args:
        alpha: L2 regularization strength. When alpha > 0, applies Ridge
            penalty to feature weights only (intercept is not regularized).
    """
    X_with_intercept = np.column_stack([np.ones(len(X_train)), X_train])

    if alpha > 0:
        # Ridge: use normal equation with penalty
        XtX = X_with_intercept.T @ X_with_intercept
        XtX[1:, 1:] += alpha * np.eye(X_train.shape[1])
        Xty = X_with_intercept.T @ y_train
        try:
            beta = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            return -np.inf
    else:
        try:
            beta, _, _, _ = np.linalg.lstsq(X_with_intercept, y_train, rcond=None)
        except np.linalg.LinAlgError:
            return -np.inf

    X_test_with_intercept = np.column_stack([np.ones(len(X_test)), X_test])
    y_pred = X_test_with_intercept @ beta

    ss_res = np.sum((y_test - y_pred) ** 2)
    ss_tot = np.sum((y_test - y_test.mean()) ** 2)
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _grouped_cv_r2(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    cv_folds: int,
    alpha: float = 0.0,
) -> float:
    """Compute mean R² across grouped k-fold CV splits."""
    gkf = GroupKFold(n_splits=cv_folds)
    r2_scores = []

    for train_idx, test_idx in gkf.split(X, y, groups):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        r2 = _ols_r2(X_tr, y_tr, X_te, y_te, alpha=alpha)
        r2_scores.append(r2)

    return float(np.mean(r2_scores))


def forward_select(
    X_train: np.ndarray,
    y_train: np.ndarray,
    candidate_names: list[str],
    groups: np.ndarray,
    max_features: int | None = None,
    cv_folds: int = 5,
    min_improvement: float = 0.005,
    seed: int = 42,
    locked_base: list[int] | None = None,
    alpha: float = 0.0,
) -> tuple[list[str], dict]:
    """Stepwise forward feature selection with grouped cross-validation.

    At each step, tries adding each remaining candidate feature, picks the
    one with the best grouped k-fold CV R², and stops when improvement falls
    below ``min_improvement`` or the feature budget is exhausted.

    Args:
        X_train: Full feature matrix (n_samples, n_candidates).
        y_train: Target vector (n_samples,).
        candidate_names: Feature names corresponding to X_train columns.
        groups: Group labels (hand_id) for GroupKFold — prevents leakage.
        max_features: Maximum features to select (None = no limit).
        cv_folds: Number of folds for GroupKFold.
        min_improvement: Minimum R² improvement to continue adding features.
        seed: Random seed (for reproducibility in tie-breaking).
        locked_base: Column indices that are always included (for OLSa arm).
        alpha: L2 regularization strength for CV scoring (default 0.0 = OLS).

    Returns:
        (selected_names, selection_log) where selection_log has per-step R² trace.
    """
    n_candidates = len(candidate_names)
    if n_candidates == 0:
        return [], {"steps": [], "final_r2": None, "n_selected": 0, "locked_base": []}

    if max_features is None:
        max_features = n_candidates

    # Initialize with locked base features
    if locked_base is not None:
        selected_indices = list(locked_base)
    else:
        selected_indices = []

    remaining_indices = [i for i in range(n_candidates) if i not in selected_indices]

    # Compute baseline R² with locked features (if any)
    if selected_indices:
        X_sel = X_train[:, selected_indices]
        best_r2 = _grouped_cv_r2(X_sel, y_train, groups, cv_folds, alpha=alpha)
    else:
        best_r2 = -np.inf

    steps = []

    while remaining_indices and len(selected_indices) < max_features:
        best_candidate = None
        best_candidate_r2 = -np.inf

        for idx in remaining_indices:
            trial_indices = selected_indices + [idx]
            X_trial = X_train[:, trial_indices]
            r2 = _grouped_cv_r2(X_trial, y_train, groups, cv_folds, alpha=alpha)

            if r2 > best_candidate_r2 or (
                r2 == best_candidate_r2
                and best_candidate is not None
                and candidate_names[idx] < candidate_names[best_candidate]
            ):
                best_candidate_r2 = r2
                best_candidate = idx

        if best_candidate is None:
            break

        improvement = best_candidate_r2 - best_r2

        step = {
            "step": len(steps) + 1,
            "feature": candidate_names[best_candidate],
            "feature_index": best_candidate,
            "r2": round(best_candidate_r2, 6),
            "improvement": round(improvement, 6),
        }
        steps.append(step)

        logger.info(
            "  Step %d: +%s → R²=%.4f (Δ=%.4f)",
            step["step"],
            step["feature"],
            best_candidate_r2,
            improvement,
        )

        if improvement < min_improvement:
            logger.info(
                "  Stopping: improvement %.4f < threshold %.4f",
                improvement,
                min_improvement,
            )
            break

        selected_indices.append(best_candidate)
        remaining_indices.remove(best_candidate)
        best_r2 = best_candidate_r2

    selected_names = [candidate_names[i] for i in selected_indices]

    return selected_names, {
        "steps": steps,
        "final_r2": round(best_r2, 6) if best_r2 > -np.inf else None,
        "n_selected": len(selected_names),
        "locked_base": [candidate_names[i] for i in (locked_base or [])],
    }
