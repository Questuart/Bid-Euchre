"""
B0 Value Model Training Pipeline.

Trains a regression model to predict expected hand value from hand features.
This is the first stage of the Arc B curriculum: learning to evaluate hands
without auction awareness.

B0 Model: (hand_features, contract_type) → expected_value

Usage:
    PYTHONPATH=src python -m bid_euchre.models.train_b0 \\
        --dataset data/bidless_dataset.jsonl \\
        --output data/models/b0_v1.json \\
        --seed 42
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class B0TrainingConfig:
    """Configuration for B0 model training."""

    dataset_path: str
    output_path: str
    seed: int = 42
    model_type: str = "ridge"  # "ols" or "ridge"
    alpha: float = 1.0  # Ridge regularization parameter
    test_split: float = 0.2  # Fraction of data for validation


@dataclass
class B0Model:
    """
    B0 Value Regression Model.

    Predicts expected hand value from hand features.
    """

    weights: np.ndarray
    bias: float
    feature_names: List[str]
    model_type: str
    alpha: float

    def predict(self, features: Dict[str, float]) -> float:
        """
        Predict hand value from features.

        Args:
            features: Dict mapping feature name to value

        Returns:
            Predicted hand value
        """
        x = np.array([features.get(name, 0.0) for name in self.feature_names])
        return float(np.dot(self.weights, x) + self.bias)

    def predict_batch(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Predict hand values for a batch of features.

        Args:
            feature_matrix: (n_samples, n_features) array

        Returns:
            (n_samples,) array of predictions
        """
        return np.dot(feature_matrix, self.weights) + self.bias

    def to_artifact_dict(self, seed: int = 42) -> Dict[str, Any]:
        """
        Convert model to artifact format for serialization.

        Args:
            seed: Training seed for reproducibility metadata

        Returns:
            Artifact dictionary conforming to B0 model schema
        """
        created_at = datetime.now(timezone.utc).isoformat()

        return {
            "schema_version": "1",
            "model_type": f"b0_{self.model_type}_v1",
            "model_params": {
                "weights": self.weights.tolist(),
                "bias": self.bias,
                "feature_names": self.feature_names,
                "alpha": self.alpha,
            },
            "metadata": {
                "created_at": created_at,
                "description": "B0 hand value regression model (Arc B Stage 0)",
                "training_seed": seed,
                "n_features": len(self.feature_names),
            },
        }


def load_bidless_dataset(path: str) -> List[Dict[str, Any]]:
    """
    Load bidless dataset from JSONL file.

    Args:
        path: Path to JSONL dataset file

    Returns:
        List of dataset rows
    """
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_feature_matrix(
    rows: List[Dict[str, Any]],
    feature_keys: Optional[List[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Extract feature matrix and target values from dataset rows.

    Args:
        rows: List of dataset rows (from load_bidless_dataset)
        feature_keys: Specific features to use (default: auto-detect numeric)

    Returns:
        (X, y, feature_names) tuple where:
        - X is (n_samples, n_features) feature matrix
        - y is (n_samples,) target array (hand_value)
        - feature_names is list of feature column names
    """
    if not rows:
        raise ValueError("Empty dataset")

    # Auto-detect feature keys from first row
    if feature_keys is None:
        sample_features = rows[0].get("hand_features", {})
        feature_keys = [
            k
            for k, v in sample_features.items()
            if isinstance(v, (int, float))
            and not isinstance(v, bool)
            and k != "hand_value"  # Don't include target in features
        ]

    n_samples = len(rows)
    n_features = len(feature_keys)

    X = np.zeros((n_samples, n_features))
    y = np.zeros(n_samples)

    for i, row in enumerate(rows):
        features = row.get("hand_features", {})
        for j, key in enumerate(feature_keys):
            X[i, j] = features.get(key, 0.0)
        y[i] = features.get("hand_value", 0.0)

    return X, y, feature_keys


def train_ols(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Train OLS regression using normal equations.

    Args:
        X: (n_samples, n_features) feature matrix
        y: (n_samples,) target array

    Returns:
        (weights, bias) tuple
    """
    # Add bias column
    X_bias = np.column_stack([np.ones(X.shape[0]), X])

    # Solve normal equations: (X'X)^-1 X'y
    XtX = X_bias.T @ X_bias
    Xty = X_bias.T @ y
    params = np.linalg.solve(XtX, Xty)

    bias = params[0]
    weights = params[1:]

    return weights, bias


def train_ridge(
    X: np.ndarray, y: np.ndarray, alpha: float = 1.0
) -> Tuple[np.ndarray, float]:
    """
    Train Ridge regression.

    Args:
        X: (n_samples, n_features) feature matrix
        y: (n_samples,) target array
        alpha: Regularization parameter

    Returns:
        (weights, bias) tuple
    """
    # Add bias column
    X_bias = np.column_stack([np.ones(X.shape[0]), X])

    # Ridge: (X'X + alpha*I)^-1 X'y
    # Note: Don't regularize bias term
    n_features = X_bias.shape[1]
    I = np.eye(n_features)
    I[0, 0] = 0  # Don't regularize bias

    XtX = X_bias.T @ X_bias + alpha * I
    Xty = X_bias.T @ y
    params = np.linalg.solve(XtX, Xty)

    bias = params[0]
    weights = params[1:]

    return weights, bias


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Compute regression metrics.

    Args:
        y_true: True target values
        y_pred: Predicted values

    Returns:
        Dict with MSE, MAE, and R^2
    """
    mse = np.mean((y_true - y_pred) ** 2)
    mae = np.mean(np.abs(y_true - y_pred))

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {"mse": float(mse), "mae": float(mae), "r2": float(r2)}


def train_b0_model(config: B0TrainingConfig) -> Tuple[B0Model, Dict[str, Any]]:
    """
    Train B0 value model from bidless dataset.

    Args:
        config: Training configuration

    Returns:
        (model, metrics) tuple
    """
    # Set random seed
    np.random.seed(config.seed)

    # Load dataset
    rows = load_bidless_dataset(config.dataset_path)
    if not rows:
        raise ValueError(f"Empty dataset: {config.dataset_path}")

    # Extract features
    X, y, feature_names = extract_feature_matrix(rows)

    # Shuffle and split
    n_samples = len(rows)
    indices = np.random.permutation(n_samples)
    n_test = int(n_samples * config.test_split)
    test_indices = indices[:n_test]
    train_indices = indices[n_test:]

    X_train, y_train = X[train_indices], y[train_indices]
    X_test, y_test = X[test_indices], y[test_indices]

    # Train model
    if config.model_type == "ridge":
        weights, bias = train_ridge(X_train, y_train, config.alpha)
    else:  # ols
        weights, bias = train_ols(X_train, y_train)

    # Create model
    model = B0Model(
        weights=weights,
        bias=bias,
        feature_names=feature_names,
        model_type=config.model_type,
        alpha=config.alpha,
    )

    # Compute metrics
    y_train_pred = model.predict_batch(X_train)
    y_test_pred = model.predict_batch(X_test)

    metrics = {
        "train": compute_metrics(y_train, y_train_pred),
        "test": compute_metrics(y_test, y_test_pred),
        "n_train": len(train_indices),
        "n_test": len(test_indices),
    }

    return model, metrics


def save_b0_model(model: B0Model, path: str, seed: int = 42) -> None:
    """
    Save B0 model to JSON file.

    Args:
        model: Trained B0Model
        path: Output path
        seed: Training seed for metadata
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    artifact = model.to_artifact_dict(seed)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)


def load_b0_model(path: str) -> B0Model:
    """
    Load B0 model from JSON file.

    Args:
        path: Path to model JSON

    Returns:
        Loaded B0Model
    """
    with open(path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    params = artifact["model_params"]

    return B0Model(
        weights=np.array(params["weights"]),
        bias=params["bias"],
        feature_names=params["feature_names"],
        model_type=artifact.get("model_type", "ridge").replace("b0_", "").replace("_v1", ""),
        alpha=params.get("alpha", 1.0),
    )


def main() -> None:
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Train B0 hand value regression model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to bidless dataset JSONL file",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for trained model JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--model-type",
        choices=["ols", "ridge"],
        default="ridge",
        help="Model type (default: ridge)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Ridge regularization parameter (default: 1.0)",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.2,
        help="Test set fraction (default: 0.2)",
    )

    args = parser.parse_args()

    config = B0TrainingConfig(
        dataset_path=args.dataset,
        output_path=args.output,
        seed=args.seed,
        model_type=args.model_type,
        alpha=args.alpha,
        test_split=args.test_split,
    )

    print(f"Training B0 model from {config.dataset_path}...")
    model, metrics = train_b0_model(config)

    print(f"Train metrics: MSE={metrics['train']['mse']:.4f}, R²={metrics['train']['r2']:.4f}")
    print(f"Test metrics:  MSE={metrics['test']['mse']:.4f}, R²={metrics['test']['r2']:.4f}")

    save_b0_model(model, config.output_path, config.seed)
    print(f"Model saved to {config.output_path}")


if __name__ == "__main__":
    main()
