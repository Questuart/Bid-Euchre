#!/usr/bin/env python3
"""
Train Ridge regression models with hyperparameter tuning.

Ridge handles multicollinearity by adding L2 penalty: (X'X + αI)^-1 X'y
"""

import json
import numpy as np
import pickle
import os

# Paths
GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
GREEDY_VAL = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.val.jsonl"
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"

OUTPUT_DIR = "data/models/ridge_regression"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Use same expanded features as before
FEATURES = {
    'suit': [
        'bowers',
        'trump_count',
        'offsuit_aces',
        'trump_power_sum',
        'trump_count_x_offsuit_ace',
        'void_count'
    ],
    'high': [
        'offsuit_aces',
        'offsuit_suits_with_ace',
        'rank_sum',
        'high_card_count',
        'offsuit_suits_with_double_ace'
    ],
    'low': [
        'offsuit_tens_count',
        'rank_sum',
        'low_card_count',
        'offsuit_secondbest_rank_sum',
        'double_ten_jack_count'
    ]
}

# Hyperparameter grid for alpha (regularization strength)
ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]

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

class SimpleRidge:
    """Ridge regression using closed-form solution."""
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.coef_ = None
        self.intercept_ = None
    
    def fit(self, X, y):
        """Fit Ridge: beta = (X'X + αI)^-1 X'y"""
        # Standardize features (important for Ridge!)
        self.X_mean_ = np.mean(X, axis=0)
        self.X_std_ = np.std(X, axis=0)
        self.X_std_[self.X_std_ == 0] = 1  # Avoid division by zero
        
        X_scaled = (X - self.X_mean_) / self.X_std_
        
        # Add intercept column
        X_with_intercept = np.column_stack([np.ones(len(X_scaled)), X_scaled])
        
        # Ridge solution: (X'X + αI)^-1 X'y
        XtX = X_with_intercept.T @ X_with_intercept
        
        # Regularization matrix (don't penalize intercept)
        I = np.eye(XtX.shape[0])
        I[0, 0] = 0  # Don't regularize intercept
        
        XtX_reg = XtX + self.alpha * I
        Xty = X_with_intercept.T @ y
        
        beta = np.linalg.solve(XtX_reg, Xty)
        
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        
        return self
    
    def predict(self, X):
        """Make predictions."""
        X_scaled = (X - self.X_mean_) / self.X_std_
        return X_scaled @ self.coef_ + self.intercept_

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

def tune_alpha(X_train, y_train, X_val, y_val, alphas):
    """Find best alpha using validation set."""
    best_alpha = None
    best_val_r2 = -np.inf
    results = []
    
    for alpha in alphas:
        model = SimpleRidge(alpha=alpha)
        model.fit(X_train, y_train)
        
        train_r2 = r2_score(y_train, model.predict(X_train))
        val_r2 = r2_score(y_val, model.predict(X_val))
        
        results.append({
            'alpha': alpha,
            'train_r2': train_r2,
            'val_r2': val_r2
        })
        
        if val_r2 > best_val_r2:
            best_val_r2 = val_r2
            best_alpha = alpha
    
    return best_alpha, results

def train_and_evaluate(contract_type, feature_names):
    """Train Ridge model with hyperparameter tuning."""
    print(f"\n{'='*100}")
    print(f"Training: ridge_regression_{contract_type}")
    print(f"Features ({len(feature_names)}): {', '.join(feature_names)}")
    print('='*100)
    
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
    
    # Hyperparameter tuning
    print("\n" + "-"*100)
    print("HYPERPARAMETER TUNING (Alpha Selection)")
    print("-"*100)
    print(f"Testing alphas: {ALPHAS}")
    print()
    
    best_alpha, tuning_results = tune_alpha(X_train, y_train, X_val, y_val, ALPHAS)
    
    print(f"{'Alpha':<12} {'Train R²':<12} {'Val R²':<12} {'Gap':<12} {'Status':<10}")
    print("-"*100)
    
    for r in tuning_results:
        gap = r['train_r2'] - r['val_r2']
        status = "✅ BEST" if r['alpha'] == best_alpha else ""
        print(f"{r['alpha']:<12.2f} {r['train_r2']:<12.4f} {r['val_r2']:<12.4f} {gap:+.4f}       {status}")
    
    print()
    print(f"Selected alpha: {best_alpha} ✅")
    
    # Train final model with best alpha
    print("\n" + "-"*100)
    print("Training final Ridge model...")
    print("-"*100)
    
    model = SimpleRidge(alpha=best_alpha)
    model.fit(X_train, y_train)
    
    # Predictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)
    
    # Metrics
    print("\nRESULTS:")
    print("-"*100)
    
    train_r2 = r2_score(y_train, y_train_pred)
    train_mae = mean_absolute_error(y_train, y_train_pred)
    
    val_r2 = r2_score(y_val, y_val_pred)
    val_mae = mean_absolute_error(y_val, y_val_pred)
    
    test_r2 = r2_score(y_test, y_test_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    
    print(f"\nTRAIN:  R² = {train_r2:.4f}, MAE = {train_mae:.4f}")
    print(f"VAL:    R² = {val_r2:.4f}, MAE = {val_mae:.4f}")
    print(f"TEST:   R² = {test_r2:.4f}, MAE = {test_mae:.4f}")
    
    # Coefficients
    print("\n" + "-"*100)
    print("RIDGE COEFFICIENTS:")
    print("-"*100)
    print(f"Intercept: {model.intercept_:.4f}")
    print(f"Alpha: {best_alpha}")
    print()
    for fname, coef in zip(feature_names, model.coef_):
        print(f"  {fname:<35} {coef:+.4f}")
    
    # Save model
    model_path = os.path.join(OUTPUT_DIR, f"ridge_regression_{contract_type}.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'features': feature_names,
            'contract_type': contract_type,
            'alpha': best_alpha
        }, f)
    print(f"\n✅ Model saved: {model_path}")
    
    return {
        'contract_type': contract_type,
        'features': feature_names,
        'n_features': len(feature_names),
        'alpha': best_alpha,
        'train_r2': train_r2,
        'val_r2': val_r2,
        'test_r2': test_r2,
        'train_mae': train_mae,
        'val_mae': val_mae,
        'test_mae': test_mae,
        'intercept': model.intercept_,
        'coefficients': dict(zip(feature_names, model.coef_))
    }

def main():
    print("=" * 100)
    print("RIDGE REGRESSION WITH HYPERPARAMETER TUNING")
    print("=" * 100)
    print("\nGoal: Handle multicollinearity using L2 regularization")
    print("Method: Cross-validation on validation set to select alpha")
    
    results = []
    for contract_type, feature_names in FEATURES.items():
        result = train_and_evaluate(contract_type, feature_names)
        if result:
            results.append(result)
    
    # Load OLS results for comparison
    print("\n" + "=" * 100)
    print("COMPARISON: RIDGE vs EXPANDED OLS vs BASELINE OLS")
    print("=" * 100)
    
    baseline_results = {
        'suit': {'features': 3, 'test_r2': 0.2123, 'test_mae': 1.4642},
        'high': {'features': 1, 'test_r2': 0.1936, 'test_mae': 1.3491},
        'low': {'features': 1, 'test_r2': 0.2056, 'test_mae': 1.3517}
    }
    
    expanded_ols_results = {
        'suit': {'features': 6, 'test_r2': 0.2180, 'test_mae': 1.4572},
        'high': {'features': 5, 'test_r2': 0.1969, 'test_mae': 1.3501},
        'low': {'features': 5, 'test_r2': 0.2098, 'test_mae': 1.3522}
    }
    
    print(f"\n{'Contract':<12} {'Model':<20} {'Features':<10} {'Test R²':<12} {'Test MAE':<12} {'Alpha':<10}")
    print("-" * 100)
    
    for r in results:
        contract = r['contract_type']
        baseline = baseline_results[contract]
        expanded = expanded_ols_results[contract]
        
        print(f"{contract:<12} {'Baseline OLS':<20} {baseline['features']:<10} {baseline['test_r2']:<12.4f} {baseline['test_mae']:<12.4f} {'N/A':<10}")
        print(f"{contract:<12} {'Expanded OLS':<20} {expanded['features']:<10} {expanded['test_r2']:<12.4f} {expanded['test_mae']:<12.4f} {'N/A':<10}")
        print(f"{contract:<12} {'Ridge':<20} {r['n_features']:<10} {r['test_r2']:<12.4f} {r['test_mae']:<12.4f} {r['alpha']:<10.2f}")
        
        # Compare Ridge to Expanded OLS
        delta_r2 = r['test_r2'] - expanded['test_r2']
        delta_mae = r['test_mae'] - expanded['test_mae']
        
        print(f"{'':<12} {'Δ (Ridge-Exp)':<20} {'':<10} {delta_r2:+.4f}       {delta_mae:+.4f}")
        print()
    
    # Analysis
    print("=" * 100)
    print("💡 ANALYSIS")
    print("=" * 100)
    print()
    
    print("1. REGULARIZATION STRENGTH:")
    for r in results:
        print(f"   • {r['contract_type'].upper()}: alpha = {r['alpha']}")
    print()
    
    any_improvement = any((r['test_r2'] - expanded_ols_results[r['contract_type']]['test_r2']) > 0.001 
                          for r in results)
    
    if any_improvement:
        print("2. ✅ Ridge IMPROVED over Expanded OLS")
        print("   • Regularization helped handle multicollinearity")
        print("   • More stable coefficients (less sensitive to correlated features)")
    else:
        print("2. ➖ Ridge similar to Expanded OLS")
        print("   • Regularization didn't hurt, but didn't help much")
        print("   • Features were already nearly orthogonal OR")
        print("   • Multicollinearity wasn't hurting predictions")
    
    print()
    print("3. RECOMMENDATION:")
    
    best_overall_r2 = max(r['test_r2'] for r in results)
    baseline_avg_r2 = np.mean([baseline_results[c]['test_r2'] for c in ['suit', 'high', 'low']])
    
    if best_overall_r2 - baseline_avg_r2 < 0.01:
        print("   ⭐ Stick with BASELINE OLS")
        print("   • Simpler (1-3 features)")
        print("   • Similar performance")
        print("   • More interpretable")
    else:
        print("   ⭐ Use RIDGE if you want 5-7 features")
        print("   • Handles multicollinearity")
        print("   • Slightly better R²")
        print("   • Good for production systems")
    
    print()

if __name__ == "__main__":
    main()

