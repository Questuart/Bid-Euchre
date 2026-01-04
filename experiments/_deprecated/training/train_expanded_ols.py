#!/usr/bin/env python3
"""
Train expanded OLS regression models with 5-7 features per contract.

This establishes whether additional features improve R² before trying Ridge.
"""

import json
import numpy as np
import pickle
import os

# Paths
GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
GREEDY_VAL = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.val.jsonl"
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"

OUTPUT_DIR = "data/models/expanded_ols"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Expanded feature sets (5-7 features per contract)
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

def calculate_vif(X):
    """Calculate Variance Inflation Factor for each feature."""
    n_features = X.shape[1]
    vif = np.zeros(n_features)
    
    for i in range(n_features):
        # Regress feature i on all other features
        X_i = X[:, i]
        X_others = np.delete(X, i, axis=1)
        
        # Add intercept to X_others
        X_others_with_intercept = np.column_stack([np.ones(len(X_others)), X_others])
        
        # Fit OLS: X_i = X_others * beta
        try:
            XtX = X_others_with_intercept.T @ X_others_with_intercept
            Xty = X_others_with_intercept.T @ X_i
            beta = np.linalg.solve(XtX, Xty)
            
            # Predict and calculate R²
            X_i_pred = X_others_with_intercept @ beta
            r2 = r2_score(X_i, X_i_pred)
            
            # VIF = 1 / (1 - R²)
            if r2 < 0.9999:  # Avoid division by zero
                vif[i] = 1 / (1 - r2)
            else:
                vif[i] = np.inf
        except:
            vif[i] = np.inf
    
    return vif

class SimpleOLS:
    """Simple OLS regression using numpy."""
    def __init__(self):
        self.coef_ = None
        self.intercept_ = None
    
    def fit(self, X, y):
        """Fit OLS using normal equation."""
        X_with_intercept = np.column_stack([np.ones(len(X)), X])
        XtX = X_with_intercept.T @ X_with_intercept
        Xty = X_with_intercept.T @ y
        beta = np.linalg.solve(XtX, Xty)
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        return self
    
    def predict(self, X):
        """Make predictions."""
        return X @ self.coef_ + self.intercept_

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

def train_and_evaluate(contract_type, feature_names):
    """Train expanded OLS model for a contract type."""
    print(f"\n{'='*100}")
    print(f"Training: expanded_ols_{contract_type}")
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
    
    # Check for multicollinearity
    print("\n" + "-"*100)
    print("MULTICOLLINEARITY CHECK (VIF - Variance Inflation Factor)")
    print("-"*100)
    print("VIF < 5:  No multicollinearity")
    print("VIF 5-10: Moderate multicollinearity")
    print("VIF > 10: High multicollinearity (Ridge recommended)")
    print()
    
    vif = calculate_vif(X_train)
    max_vif = np.max(vif)
    
    for fname, vif_val in zip(feature_names, vif):
        status = "✅" if vif_val < 5 else "⚠️" if vif_val < 10 else "❌"
        print(f"  {fname:<35} VIF = {vif_val:>8.2f}  {status}")
    
    print()
    if max_vif < 5:
        print("✅ No multicollinearity detected - OLS is fine")
    elif max_vif < 10:
        print("⚠️  Moderate multicollinearity - OLS okay, Ridge might help slightly")
    else:
        print("❌ High multicollinearity detected - Ridge recommended!")
    
    # Train OLS
    print("\n" + "-"*100)
    print("Training OLS regression...")
    print("-"*100)
    model = SimpleOLS()
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
    train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
    
    val_r2 = r2_score(y_val, y_val_pred)
    val_mae = mean_absolute_error(y_val, y_val_pred)
    val_rmse = np.sqrt(mean_squared_error(y_val, y_val_pred))
    
    test_r2 = r2_score(y_test, y_test_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    
    print(f"\nTRAIN:")
    print(f"  R² score:  {train_r2:.4f}")
    print(f"  MAE:       {train_mae:.4f} tricks")
    print(f"  RMSE:      {train_rmse:.4f} tricks")
    
    print(f"\nVAL:")
    print(f"  R² score:  {val_r2:.4f}")
    print(f"  MAE:       {val_mae:.4f} tricks")
    print(f"  RMSE:      {val_rmse:.4f} tricks")
    
    print(f"\nTEST:")
    print(f"  R² score:  {test_r2:.4f}")
    print(f"  MAE:       {test_mae:.4f} tricks")
    print(f"  RMSE:      {test_rmse:.4f} tricks")
    
    # Check for overfitting
    train_test_gap = train_r2 - test_r2
    print()
    print(f"Train-Test R² gap: {train_test_gap:+.4f}")
    if abs(train_test_gap) < 0.02:
        print("✅ No overfitting detected")
    elif abs(train_test_gap) < 0.05:
        print("⚠️  Slight overfitting - monitor")
    else:
        print("❌ Significant overfitting - Ridge recommended!")
    
    # Coefficients
    print("\n" + "-"*100)
    print("MODEL COEFFICIENTS:")
    print("-"*100)
    print(f"Intercept: {model.intercept_:.4f}")
    for fname, coef in zip(feature_names, model.coef_):
        print(f"  {fname:<35} {coef:+.4f}")
    
    # Save model
    model_path = os.path.join(OUTPUT_DIR, f"expanded_ols_{contract_type}.pkl")
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
        'train_r2': train_r2,
        'val_r2': val_r2,
        'test_r2': test_r2,
        'train_mae': train_mae,
        'val_mae': val_mae,
        'test_mae': test_mae,
        'max_vif': max_vif,
        'train_test_gap': train_test_gap,
        'intercept': model.intercept_,
        'coefficients': dict(zip(feature_names, model.coef_))
    }

def main():
    print("=" * 100)
    print("EXPANDED OLS REGRESSION MODELS (5-7 Features)")
    print("=" * 100)
    print("\nGoal: Improve R² by adding more predictive features")
    print("Then: Check if Ridge is needed (multicollinearity / overfitting)")
    
    results = []
    for contract_type, feature_names in FEATURES.items():
        result = train_and_evaluate(contract_type, feature_names)
        if result:
            results.append(result)
    
    # Summary comparison
    print("\n" + "=" * 100)
    print("SUMMARY - EXPANDED OLS vs BASELINE OLS")
    print("=" * 100)
    
    # Baseline results (from earlier)
    baseline_results = {
        'suit': {'features': 3, 'test_r2': 0.2123, 'test_mae': 1.4642},
        'high': {'features': 1, 'test_r2': 0.1936, 'test_mae': 1.3491},
        'low': {'features': 1, 'test_r2': 0.2056, 'test_mae': 1.3517}
    }
    
    print(f"\n{'Model':<25} {'Features':<12} {'Test R²':<12} {'Δ R²':<12} {'Test MAE':<12} {'Δ MAE':<12} {'Max VIF':<12}")
    print("-" * 100)
    
    for r in results:
        contract = r['contract_type']
        baseline = baseline_results[contract]
        
        delta_r2 = r['test_r2'] - baseline['test_r2']
        delta_mae = r['test_mae'] - baseline['test_mae']
        
        r2_symbol = "✅" if delta_r2 > 0.01 else "➖" if abs(delta_r2) < 0.01 else "⚠️"
        mae_symbol = "✅" if delta_mae < -0.01 else "➖" if abs(delta_mae) < 0.01 else "⚠️"
        vif_symbol = "✅" if r['max_vif'] < 5 else "⚠️" if r['max_vif'] < 10 else "❌"
        
        print(f"baseline_{contract:<17} {baseline['features']:<12} {baseline['test_r2']:<12.4f} {'baseline':<12} {baseline['test_mae']:<12.4f} {'baseline':<12}")
        print(f"expanded_{contract:<17} {r['n_features']:<12} {r['test_r2']:<12.4f} {delta_r2:+.4f} {r2_symbol:<5} {r['test_mae']:<12.4f} {delta_mae:+.4f} {mae_symbol:<5} {r['max_vif']:<8.2f} {vif_symbol}")
        print()
    
    # Recommendations
    print("=" * 100)
    print("💡 RECOMMENDATIONS")
    print("=" * 100)
    print()
    
    any_high_vif = any(r['max_vif'] > 10 for r in results)
    any_overfitting = any(abs(r['train_test_gap']) > 0.05 for r in results)
    any_improvement = any((r['test_r2'] - baseline_results[r['contract_type']]['test_r2']) > 0.01 for r in results)
    
    if not any_improvement:
        print("⚠️  Expanded features did NOT improve R² significantly")
        print()
        print("Possible reasons:")
        print("  • Features are redundant with existing ones")
        print("  • Need different features or interactions")
        print("  • R² ceiling reached (card play variance dominates)")
        print()
        print("Recommendation: Stick with baseline OLS models (simpler is better)")
    elif any_high_vif or any_overfitting:
        print("✅ Expanded features improve R², BUT multicollinearity/overfitting detected")
        print()
        print("Next step: Try Ridge regression")
        print("  • Ridge will handle multicollinearity")
        print("  • Ridge will reduce overfitting")
        print("  • Expected: Similar R² but better generalization")
    else:
        print("✅ Expanded features improve R² with no issues!")
        print()
        print("Recommendation: Use expanded OLS models")
        print("  • Better predictions than baseline")
        print("  • No multicollinearity")
        print("  • No overfitting")
        print("  • Ridge not needed")
    
    print()

if __name__ == "__main__":
    main()

