"""
Unit tests for forward feature selection with grouped cross-validation.
"""

import numpy as np

from bid_euchre.models.feature_selection import forward_select


def _make_data(n_samples=500, n_features=5, seed=42):
    """Generate synthetic data with known best feature."""
    rng = np.random.RandomState(seed)

    # Feature 0 strongly correlated with y, others are noise
    X = rng.randn(n_samples, n_features)
    y = 3.0 * X[:, 0] + 0.5 * X[:, 1] + rng.randn(n_samples) * 0.5

    # Groups: 4 rows per group (mimicking hand_id with 4 seats)
    n_groups = n_samples // 4
    groups = np.repeat(np.arange(n_groups), 4)[:n_samples]

    names = [f"feat_{i}" for i in range(n_features)]
    return X, y, groups, names


def test_forward_select_picks_best():
    """Most correlated feature should be selected first."""
    X, y, groups, names = _make_data()

    selected, log = forward_select(
        X,
        y,
        names,
        groups,
        max_features=2,
        cv_folds=3,
        seed=42,
    )

    assert len(selected) >= 1
    # feat_0 has coefficient 3.0 — should be first
    assert selected[0] == "feat_0"
    assert len(log["steps"]) >= 1


def test_stops_at_threshold():
    """Selection stops when improvement < min_improvement."""
    X, y, groups, names = _make_data(n_features=3)

    # Use a very high threshold so it stops after first feature
    selected, log = forward_select(
        X,
        y,
        names,
        groups,
        min_improvement=0.5,
        cv_folds=3,
        seed=42,
    )

    # Should select at most 2 features (feat_0 adds a lot, feat_1 adds some)
    # With threshold 0.5, likely stops after feat_0
    assert len(selected) <= 2


def test_stops_at_budget():
    """Respects max_features limit."""
    X, y, groups, names = _make_data(n_features=5)

    selected, log = forward_select(
        X,
        y,
        names,
        groups,
        max_features=1,
        cv_folds=3,
        seed=42,
    )

    assert len(selected) == 1
    assert log["n_selected"] == 1


def test_locked_base_kept():
    """Base features from locked_base are always in the result."""
    X, y, groups, names = _make_data(n_features=5)

    # Lock feat_3 and feat_4 as base (they're noise but must stay)
    selected, log = forward_select(
        X,
        y,
        names,
        groups,
        max_features=4,
        cv_folds=3,
        seed=42,
        locked_base=[3, 4],
    )

    assert "feat_3" in selected
    assert "feat_4" in selected
    assert log["locked_base"] == ["feat_3", "feat_4"]


def test_deterministic():
    """Same seed produces same result."""
    X, y, groups, names = _make_data()

    sel1, log1 = forward_select(
        X, y, names, groups, max_features=3, cv_folds=3, seed=42
    )
    sel2, log2 = forward_select(
        X, y, names, groups, max_features=3, cv_folds=3, seed=42
    )

    assert sel1 == sel2
    assert log1["steps"] == log2["steps"]


def test_empty_candidates():
    """Returns empty selection gracefully when no candidates."""
    X = np.empty((10, 0))
    y = np.ones(10)
    groups = np.repeat(np.arange(5), 2)

    selected, log = forward_select(X, y, [], groups, seed=42)

    assert selected == []
    assert log["n_selected"] == 0
    assert log["final_r2"] is None
