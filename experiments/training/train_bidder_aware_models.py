#!/usr/bin/env python3
"""
Train Bidder-Aware Models (OLSa_v2 and OLSa_SR_v2).

This script trains two families of models, each with the is_bidder feature:

1. OLSa_v2: Baseline OLS features + is_bidder
   - Suit: trump_count, trump_rb_count, trump_lb_count, offsuit_aces, is_bidder
   - High: offsuit_aces, offsuit_length_3plus_count, is_bidder
   - Low: offsuit_length_3plus_count, is_bidder

2. OLSa_SR_v2: Hand Value features + is_bidder
   - All contracts: hand_value, is_bidder

Compares both model families to their baselines (without is_bidder) to
measure the impact of the bidder/defender dynamic.

Usage:
    PYTHONPATH=src python experiments/train_bidder_aware_models.py

Output:
    data/models/current/olsa_v2/olsa_v2_{suit,high,low}.pkl
    data/models/current/olsa_sr_v2/olsa_sr_v2_{suit,high,low}.pkl
    data/reports/bidder_models_comparison.txt
"""

import os
import sys
import csv
import pickle

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.analysis.models import SimpleOLS


def calc_r2(y_true, y_pred):
    """Calculate R² score."""
    ss_res = sum((yt - yp)**2 for yt, yp in zip(y_true, y_pred))
    ss_tot = sum((yt - sum(y_true)/len(y_true))**2 for yt in y_true)
    return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0


def calc_mae(y_true, y_pred):
    """Calculate mean absolute error."""
    return sum(abs(yt - yp) for yt, yp in zip(y_true, y_pred)) / len(y_true)


def load_csv_data(csv_path: str, contract_type: str):
    """Load and filter data for a specific contract type."""
    X = []
    y = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['contract_type'] != contract_type:
                continue

            # Extract features and target
            features = {}
            for key, value in row.items():
                if key not in ['deal_id', 'player_idx', 'contract_type', 'trump_suit',
                              'actual_tricks', 'dealer_position', 'bidder_position']:
                    try:
                        features[key] = float(value)
                    except (ValueError, TypeError):
                        features[key] = 0.0

            X.append(features)
            y.append(float(row['actual_tricks']))

    return X, y


def extract_features(X, feature_names):
    """Extract specific features as matrix."""
    X_mat = []
    for sample in X:
        row = [sample.get(fname, 0.0) for fname in feature_names]
        X_mat.append(row)
    return X_mat


def train_olsa_v2_models():
    """Train OLSa_v2 models (baseline features + is_bidder)."""
    print("\n" + "="*80)
    print("🎓 Training OLSa_v2 Models (Baseline + is_bidder)")
    print("="*80)

    # Feature sets for each contract (baseline + is_bidder)
    features = {
        'suit': ['trump_count', 'trump_rb_count', 'trump_lb_count', 'offsuit_aces', 'is_bidder'],
        'high': ['offsuit_aces', 'offsuit_length_3plus_count', 'is_bidder'],
        'low': ['offsuit_length_3plus_count', 'is_bidder'],
    }

    models = {}
    metrics = {}

    for contract in ['suit', 'high', 'low']:
        print(f"\n{contract.upper()} Contract:")
        print("-" * 80)

        # Load data
        print("  Loading data...")
        X_train, y_train = load_csv_data('data/training/bidder_aware_train.csv', contract)
        X_val, y_val = load_csv_data('data/training/bidder_aware_val.csv', contract)
        X_test, y_test = load_csv_data('data/training/bidder_aware_test.csv', contract)

        print(f"  Train: {len(X_train):,} samples")
        print(f"  Val:   {len(X_val):,} samples")
        print(f"  Test:  {len(X_test):,} samples")

        # Extract features
        X_train_mat = extract_features(X_train, features[contract])
        X_val_mat = extract_features(X_val, features[contract])
        X_test_mat = extract_features(X_test, features[contract])

        # Train model
        print(f"  Features: {', '.join(features[contract])}")
        model = SimpleOLS()
        model.fit(X_train_mat, y_train)

        # Evaluate
        y_train_pred = model.predict(X_train_mat)
        y_val_pred = model.predict(X_val_mat)
        y_test_pred = model.predict(X_test_mat)

        train_r2 = calc_r2(y_train, y_train_pred)
        val_r2 = calc_r2(y_val, y_val_pred)
        test_r2 = calc_r2(y_test, y_test_pred)

        train_mae = calc_mae(y_train, y_train_pred)
        val_mae = calc_mae(y_val, y_val_pred)
        test_mae = calc_mae(y_test, y_test_pred)

        print(f"  Train R²: {train_r2:.4f}  MAE: {train_mae:.3f}")
        print(f"  Val R²:   {val_r2:.4f}  MAE: {val_mae:.3f}")
        print(f"  Test R²:  {test_r2:.4f}  MAE: {test_mae:.3f}")

        # Print coefficients
        print("\n  Coefficients:")
        for fname, coef in zip(features[contract], model.coef_):
            print(f"    {fname:<30} {coef:>8.3f}")
        print(f"    {'intercept':<30} {model.intercept_:>8.3f}")

        # Save model (in dict format for RegressionBidder compatibility)
        os.makedirs('data/models/olsa_v2', exist_ok=True)
        model_path = f'data/models/current/olsa_v2/olsa_v2_{contract}.pkl'
        model_dict = {
            'model': model,
            'features': features[contract],
            'contract_type': contract
        }
        with open(model_path, 'wb') as f:
            pickle.dump(model_dict, f)
        print(f"  ✅ Saved to: {model_path}")

        models[contract] = model
        metrics[contract] = {
            'train_r2': train_r2,
            'val_r2': val_r2,
            'test_r2': test_r2,
            'train_mae': train_mae,
            'val_mae': val_mae,
            'test_mae': test_mae,
            'features': features[contract],
        }

    return models, metrics


def train_olsa_sr_v2_models():
    """Train OLSa_SR_v2 models (hand value + is_bidder)."""
    print("\n" + "="*80)
    print("🎓 Training OLSa_SR_v2 Models (Hand Value + is_bidder)")
    print("="*80)

    # Feature set: hand_value + is_bidder for all contracts
    features = {
        'suit': ['hand_value', 'is_bidder'],
        'high': ['hand_value', 'is_bidder'],
        'low': ['hand_value', 'is_bidder'],
    }

    models = {}
    metrics = {}

    for contract in ['suit', 'high', 'low']:
        print(f"\n{contract.upper()} Contract:")
        print("-" * 80)

        # Load data
        print("  Loading data...")
        X_train, y_train = load_csv_data('data/training/bidder_aware_train.csv', contract)
        X_val, y_val = load_csv_data('data/training/bidder_aware_val.csv', contract)
        X_test, y_test = load_csv_data('data/training/bidder_aware_test.csv', contract)

        print(f"  Train: {len(X_train):,} samples")
        print(f"  Val:   {len(X_val):,} samples")
        print(f"  Test:  {len(X_test):,} samples")

        # Extract features
        X_train_mat = extract_features(X_train, features[contract])
        X_val_mat = extract_features(X_val, features[contract])
        X_test_mat = extract_features(X_test, features[contract])

        # Train model
        print(f"  Features: {', '.join(features[contract])}")
        model = SimpleOLS()
        model.fit(X_train_mat, y_train)

        # Evaluate
        y_train_pred = model.predict(X_train_mat)
        y_val_pred = model.predict(X_val_mat)
        y_test_pred = model.predict(X_test_mat)

        train_r2 = calc_r2(y_train, y_train_pred)
        val_r2 = calc_r2(y_val, y_val_pred)
        test_r2 = calc_r2(y_test, y_test_pred)

        train_mae = calc_mae(y_train, y_train_pred)
        val_mae = calc_mae(y_val, y_val_pred)
        test_mae = calc_mae(y_test, y_test_pred)

        print(f"  Train R²: {train_r2:.4f}  MAE: {train_mae:.3f}")
        print(f"  Val R²:   {val_r2:.4f}  MAE: {val_mae:.3f}")
        print(f"  Test R²:  {test_r2:.4f}  MAE: {test_mae:.3f}")

        # Print coefficients
        print("\n  Coefficients:")
        for fname, coef in zip(features[contract], model.coef_):
            print(f"    {fname:<30} {coef:>8.3f}")
        print(f"    {'intercept':<30} {model.intercept_:>8.3f}")

        # Save model (in dict format for RegressionBidder compatibility)
        os.makedirs('data/models/olsa_sr_v2', exist_ok=True)
        model_path = f'data/models/current/olsa_sr_v2/olsa_sr_v2_{contract}.pkl'
        model_dict = {
            'model': model,
            'features': features[contract],
            'contract_type': contract
        }
        with open(model_path, 'wb') as f:
            pickle.dump(model_dict, f)
        print(f"  ✅ Saved to: {model_path}")

        models[contract] = model
        metrics[contract] = {
            'train_r2': train_r2,
            'val_r2': val_r2,
            'test_r2': test_r2,
            'train_mae': train_mae,
            'val_mae': val_mae,
            'test_mae': test_mae,
            'features': features[contract],
        }

    return models, metrics


def generate_comparison_report(olsa_v2_metrics, olsa_sr_v2_metrics):
    """Generate comparison report."""
    print("\n" + "="*80)
    print("📊 Model Comparison Report")
    print("="*80)

    # Create report
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("BIDDER-AWARE MODELS COMPARISON")
    report_lines.append("="*80)
    report_lines.append("")
    report_lines.append("Trained: 2026-01-03")
    report_lines.append("Dataset: 200k records (50k hands × 4 players)")
    report_lines.append("Train/Val/Test: 140k / 30k / 30k (70/15/15)")
    report_lines.append("")
    report_lines.append("="*80)
    report_lines.append("RESULTS BY CONTRACT TYPE")
    report_lines.append("="*80)

    for contract in ['suit', 'high', 'low']:
        olsa_v2 = olsa_v2_metrics[contract]
        olsa_sr_v2 = olsa_sr_v2_metrics[contract]

        report_lines.append("")
        report_lines.append(f"{contract.upper()} CONTRACT")
        report_lines.append("-"*80)
        report_lines.append("")

        report_lines.append("OLSa_v2 (Baseline + is_bidder):")
        report_lines.append(f"  Features: {', '.join(olsa_v2['features'])}")
        report_lines.append(f"  Train R²: {olsa_v2['train_r2']:.4f}  MAE: {olsa_v2['train_mae']:.3f}")
        report_lines.append(f"  Val R²:   {olsa_v2['val_r2']:.4f}  MAE: {olsa_v2['val_mae']:.3f}")
        report_lines.append(f"  Test R²:  {olsa_v2['test_r2']:.4f}  MAE: {olsa_v2['test_mae']:.3f}")
        report_lines.append("")

        report_lines.append("OLSa_SR_v2 (Hand Value + is_bidder):")
        report_lines.append(f"  Features: {', '.join(olsa_sr_v2['features'])}")
        report_lines.append(f"  Train R²: {olsa_sr_v2['train_r2']:.4f}  MAE: {olsa_sr_v2['train_mae']:.3f}")
        report_lines.append(f"  Val R²:   {olsa_sr_v2['val_r2']:.4f}  MAE: {olsa_sr_v2['val_mae']:.3f}")
        report_lines.append(f"  Test R²:  {olsa_sr_v2['test_r2']:.4f}  MAE: {olsa_sr_v2['test_mae']:.3f}")
        report_lines.append("")

        # Comparison
        r2_diff = olsa_sr_v2['test_r2'] - olsa_v2['test_r2']
        mae_diff = olsa_v2['test_mae'] - olsa_sr_v2['test_mae']
        winner = "OLSa_SR_v2" if r2_diff > 0 else "OLSa_v2"

        report_lines.append(f"Winner: {winner}")
        report_lines.append(f"  R² difference: {r2_diff:+.4f} ({abs(r2_diff)/olsa_v2['test_r2']*100:+.1f}%)")
        report_lines.append(f"  MAE improvement: {mae_diff:+.3f} tricks")

    # Summary table
    report_lines.append("")
    report_lines.append("="*80)
    report_lines.append("SUMMARY TABLE (Test Set)")
    report_lines.append("="*80)
    report_lines.append("")

    header = f"{'Contract':<10} {'Model':<15} {'R²':<10} {'MAE':<10} {'Features':<15}"
    report_lines.append(header)
    report_lines.append("-"*80)

    for contract in ['suit', 'high', 'low']:
        olsa_v2 = olsa_v2_metrics[contract]
        olsa_sr_v2 = olsa_sr_v2_metrics[contract]

        row1 = f"{contract.upper():<10} {'OLSa_v2':<15} {olsa_v2['test_r2']:<10.4f} {olsa_v2['test_mae']:<10.3f} {len(olsa_v2['features']):<15}"
        row2 = f"{'':10} {'OLSa_SR_v2':<15} {olsa_sr_v2['test_r2']:<10.4f} {olsa_sr_v2['test_mae']:<10.3f} {len(olsa_sr_v2['features']):<15}"
        report_lines.append(row1)
        report_lines.append(row2)
        report_lines.append("")

    # Print and save
    report_text = "\n".join(report_lines)
    print(report_text)

    os.makedirs('data/reports', exist_ok=True)
    report_path = 'data/reports/bidder_models_comparison.txt'
    with open(report_path, 'w') as f:
        f.write(report_text)

    print(f"\n✅ Report saved to: {report_path}")


def main():
    print("\n" + "="*80)
    print("🚀 Bidder-Aware Model Training")
    print("="*80)
    print("\nTraining two model families:")
    print("  1. OLSa_v2: Baseline features + is_bidder")
    print("  2. OLSa_SR_v2: Hand Value + is_bidder")
    print("\nDataset: data/training/bidder_aware_{train,val,test}.csv")
    print("="*80)

    # Train both model families
    olsa_v2_models, olsa_v2_metrics = train_olsa_v2_models()
    olsa_sr_v2_models, olsa_sr_v2_metrics = train_olsa_sr_v2_models()

    # Generate comparison report
    generate_comparison_report(olsa_v2_metrics, olsa_sr_v2_metrics)

    print("\n" + "="*80)
    print("✅ Training Complete!")
    print("="*80)
    print("\nModels saved:")
    print("  data/models/current/olsa_v2/olsa_v2_{suit,high,low}.pkl")
    print("  data/models/current/olsa_sr_v2/olsa_sr_v2_{suit,high,low}.pkl")
    print("\nReport:")
    print("  data/reports/bidder_models_comparison.txt")
    print("\n🎯 Next step: Test models in head-to-head simulation")
    print("="*80)


if __name__ == "__main__":
    main()
