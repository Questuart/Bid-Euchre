#!/usr/bin/env python3
"""
Train baseline OLS regression models for trick prediction.

Usage:
    python experiments/train_baseline_regression.py
"""

import json
import numpy as np
import pickle
import os
from bid_euchre.analysis.models import SimpleOLS

# Paths
GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
GREEDY_VAL = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.val.jsonl"
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"

OUTPUT_DIR = "data/models/baseline_regression"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Feature specifications
FEATURES = {
    # Updated SUIT baseline: split bowers into RB/LB
    'suit': ['trump_count', 'trump_rb_count', 'trump_lb_count', 'offsuit_aces'],
    'high': ['offsuit_aces'],
    'low': ['offsuit_tens_count']
}

def load_data(jsonl_path, contract_type, feature_names):
    """Load features and targets for a specific contract type."""
    X_list = []
    y_list = []
    
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            
            if rec.get("event") != "hand_end":
                continue
            
            if rec.get("contract") != contract_type:
                continue
            
            features_list = rec.get("features", [])
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)
            
            for player_idx, player_features in enumerate(features_list):
                if not isinstance(player_features, dict):
                    continue
                
                # Extract features
                feature_vals = []
                all_present = True
                for fname in feature_names:
                    if fname in player_features:
                        feature_vals.append(player_features[fname])
                    else:
                        all_present = False
                        break
                
                if not all_present:
                    continue
                
                # Target: team tricks
                team_tricks = t0 if player_idx in (0, 2) else t1
                
                X_list.append(feature_vals)
                y_list.append(team_tricks)
    
    return np.array(X_list), np.array(y_list)

def r2_score(y_true, y_pred):
    """Calculate R² score."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot)

def mean_absolute_error(y_true, y_pred):
    """Calculate MAE."""
    return np.mean(np.abs(y_true - y_pred))

def mean_squared_error(y_true, y_pred):
    """Calculate MSE."""
    return np.mean((y_true - y_pred) ** 2)

def train_and_evaluate(contract_type, feature_names):
    """Train OLS model for a contract type."""
    print(f"\n{'='*80}")
    print(f"Training: baseline_regression_{contract_type}")
    print(f"Features: {', '.join(feature_names)}")
    print('='*80)
    
    # Load data
    print("Loading data...")
    X_train, y_train = load_data(GREEDY_TRAIN, contract_type, feature_names)
    X_val, y_val = load_data(GREEDY_VAL, contract_type, feature_names)
    X_test, y_test = load_data(GREEDY_TEST, contract_type, feature_names)
    
    print(f"  Train: {len(X_train):,} hands")
    print(f"  Val:   {len(X_val):,} hands")
    print(f"  Test:  {len(X_test):,} hands")
    
    if len(X_train) == 0:
        print(f"⚠️  No data found for {contract_type}!")
        return
    
    # Train OLS
    print("\nTraining OLS regression...")
    model = SimpleOLS()
    model.fit(X_train, y_train)
    
    # Predictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)
    
    # Metrics
    print("\n" + "-"*80)
    print("RESULTS:")
    print("-"*80)
    
    for split_name, y_true, y_pred in [
        ("TRAIN", y_train, y_train_pred),
        ("VAL", y_val, y_val_pred),
        ("TEST", y_test, y_test_pred)
    ]:
        r2 = r2_score(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        
        print(f"\n{split_name}:")
        print(f"  R² score:  {r2:.4f}")
        print(f"  MAE:       {mae:.4f} tricks")
        print(f"  RMSE:      {rmse:.4f} tricks")
    
    # Coefficients
    print("\n" + "-"*80)
    print("MODEL COEFFICIENTS:")
    print("-"*80)
    print(f"Intercept: {model.intercept_:.4f}")
    for fname, coef in zip(feature_names, model.coef_):
        print(f"  {fname:<30} {coef:+.4f}")
    
    # Save model
    model_path = os.path.join(OUTPUT_DIR, f"baseline_regression_{contract_type}.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'features': feature_names,
            'contract_type': contract_type
        }, f)
    print(f"\n✅ Model saved: {model_path}")
    
    return {
        'contract_type': contract_type,
        'features': feature_names,
        'n_features': len(feature_names),
        'train_r2': r2_score(y_train, y_train_pred),
        'val_r2': r2_score(y_val, y_val_pred),
        'test_r2': r2_score(y_test, y_test_pred),
        'train_mae': mean_absolute_error(y_train, y_train_pred),
        'val_mae': mean_absolute_error(y_val, y_val_pred),
        'test_mae': mean_absolute_error(y_test, y_test_pred),
        'intercept': model.intercept_,
        'coefficients': dict(zip(feature_names, model.coef_))
    }

def main():
    print("=" * 80)
    print("BASELINE OLS REGRESSION MODELS")
    print("=" * 80)
    print("\nTraining 3 models:")
    print("  • baseline_regression_suit (4 features)")
    print("  • baseline_regression_high (1 feature)")
    print("  • baseline_regression_low  (1 feature)")
    
    results = []
    for contract_type, feature_names in FEATURES.items():
        result = train_and_evaluate(contract_type, feature_names)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY - ALL MODELS")
    print("=" * 80)
    print(f"\n{'Model':<25} {'Features':<15} {'Train R²':<12} {'Val R²':<12} {'Test R²':<12} {'Test MAE':<12}")
    print("-" * 80)
    
    for r in results:
        model_name = f"baseline_{r['contract_type']}"
        n_feat = r['n_features']
        print(f"{model_name:<25} {n_feat:<15} {r['train_r2']:<12.4f} {r['val_r2']:<12.4f} {r['test_r2']:<12.4f} {r['test_mae']:<12.4f}")
    
    print("\n" + "=" * 80)
    print("✅ All baseline models trained!")
    print("=" * 80)
    print(f"\nModels saved to: {OUTPUT_DIR}/")
    print("\nNext steps:")
    print("  1. Compare these to dummy baseline (always predict 5.0)")
    print("  2. Try multi-feature models to see if R² improves")
    print("  3. Try Ridge regression if overfitting detected")

if __name__ == "__main__":
    main()

