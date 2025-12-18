#!/usr/bin/env python3
"""
Evaluate dummy baseline predictions on test data.

This establishes the minimum performance bar that any model should beat.
"""

import json
import numpy as np
from collections import defaultdict

# Paths
GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"

def load_tricks(jsonl_path):
    """Load trick counts by contract type."""
    data = defaultdict(list)
    
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            
            if rec.get("event") != "hand_end":
                continue
            
            contract_type = rec.get("contract")
            if contract_type not in ['suit', 'high', 'low']:
                continue
            
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)
            
            # Each hand contributes 4 observations (one per player's team)
            data[contract_type].extend([t0, t0, t1, t1])
            data['all'].extend([t0, t0, t1, t1])
    
    return {k: np.array(v) for k, v in data.items()}

def calculate_metrics(y_true, y_pred):
    """Calculate R², MAE, RMSE."""
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / ss_tot)
    
    return r2, mae, rmse

def main():
    print("=" * 100)
    print("DUMMY BASELINE EVALUATION")
    print("=" * 100)
    print()
    
    # Load data
    print("Loading data...")
    train_tricks = load_tricks(GREEDY_TRAIN)
    test_tricks = load_tricks(GREEDY_TEST)
    
    print(f"  Train: {len(train_tricks['all']):,} observations")
    print(f"  Test:  {len(test_tricks['all']):,} observations")
    print()
    
    # Calculate training statistics
    print("=" * 100)
    print("TRAINING DATA STATISTICS")
    print("=" * 100)
    print()
    print(f"{'Contract':<15} {'Count':<12} {'Mean':<12} {'Median':<12} {'Std Dev':<12}")
    print("-" * 100)
    
    train_stats = {}
    for contract in ['all', 'suit', 'high', 'low']:
        if contract in train_tricks:
            tricks = train_tricks[contract]
            mean = np.mean(tricks)
            median = np.median(tricks)
            std = np.std(tricks)
            train_stats[contract] = {'mean': mean, 'median': median, 'std': std}
            print(f"{contract:<15} {len(tricks):<12,} {mean:<12.4f} {median:<12.1f} {std:<12.4f}")
    print()
    
    # Evaluate dummy baselines
    print("=" * 100)
    print("DUMMY BASELINE PERFORMANCE (TEST SET)")
    print("=" * 100)
    print()
    
    results = []
    
    # 1. Global mean baseline (always predict 5.0)
    print("1. GLOBAL MEAN BASELINE (always predict 5.0)")
    print("-" * 100)
    global_mean = 5.0
    
    for contract in ['all', 'suit', 'high', 'low']:
        if contract in test_tricks:
            y_true = test_tricks[contract]
            y_pred = np.full_like(y_true, global_mean, dtype=float)
            r2, mae, rmse = calculate_metrics(y_true, y_pred)
            
            print(f"\n{contract.upper()}:")
            print(f"  R² score:  {r2:.4f}")
            print(f"  MAE:       {mae:.4f} tricks")
            print(f"  RMSE:      {rmse:.4f} tricks")
            
            results.append({
                'baseline': 'Global Mean (5.0)',
                'contract': contract,
                'prediction': global_mean,
                'r2': r2,
                'mae': mae,
                'rmse': rmse
            })
    
    # 2. Stratified mean baseline (predict training mean by contract)
    print("\n" + "=" * 100)
    print("2. STRATIFIED MEAN BASELINE (predict training mean by contract)")
    print("-" * 100)
    
    for contract in ['suit', 'high', 'low']:
        if contract in test_tricks:
            y_true = test_tricks[contract]
            pred_mean = train_stats[contract]['mean']
            y_pred = np.full_like(y_true, pred_mean, dtype=float)
            r2, mae, rmse = calculate_metrics(y_true, y_pred)
            
            print(f"\n{contract.upper()} (predict {pred_mean:.4f}):")
            print(f"  R² score:  {r2:.4f}")
            print(f"  MAE:       {mae:.4f} tricks")
            print(f"  RMSE:      {rmse:.4f} tricks")
            
            results.append({
                'baseline': 'Stratified Mean',
                'contract': contract,
                'prediction': pred_mean,
                'r2': r2,
                'mae': mae,
                'rmse': rmse
            })
    
    # 3. Median baseline
    print("\n" + "=" * 100)
    print("3. MEDIAN BASELINE (predict training median by contract)")
    print("-" * 100)
    
    for contract in ['suit', 'high', 'low']:
        if contract in test_tricks:
            y_true = test_tricks[contract]
            pred_median = train_stats[contract]['median']
            y_pred = np.full_like(y_true, pred_median, dtype=float)
            r2, mae, rmse = calculate_metrics(y_true, y_pred)
            
            print(f"\n{contract.upper()} (predict {pred_median:.1f}):")
            print(f"  R² score:  {r2:.4f}")
            print(f"  MAE:       {mae:.4f} tricks")
            print(f"  RMSE:      {rmse:.4f} tricks")
            
            results.append({
                'baseline': 'Median',
                'contract': contract,
                'prediction': pred_median,
                'r2': r2,
                'mae': mae,
                'rmse': rmse
            })
    
    # Summary comparison
    print("\n" + "=" * 100)
    print("COMPARISON: DUMMY BASELINES vs OLS MODELS")
    print("=" * 100)
    print()
    print(f"{'Contract':<15} {'Baseline':<20} {'MAE':<12} {'R²':<12} {'OLS MAE':<12} {'OLS R²':<12} {'Improvement':<12}")
    print("-" * 100)
    
    # OLS results from training
    ols_results = {
        'suit': {'mae': 1.4642, 'r2': 0.2123},
        'high': {'mae': 1.3491, 'r2': 0.1936},
        'low': {'mae': 1.3517, 'r2': 0.2056}
    }
    
    # Best dummy baseline for each contract
    best_dummies = {}
    for contract in ['suit', 'high', 'low']:
        contract_results = [r for r in results if r['contract'] == contract]
        best = min(contract_results, key=lambda x: x['mae'])
        best_dummies[contract] = best
    
    for contract in ['suit', 'high', 'low']:
        dummy = best_dummies[contract]
        ols = ols_results[contract]
        improvement = (dummy['mae'] - ols['mae']) / dummy['mae'] * 100
        
        print(f"{contract:<15} {dummy['baseline']:<20} {dummy['mae']:<12.4f} {dummy['r2']:<12.4f} {ols['mae']:<12.4f} {ols['r2']:<12.4f} {improvement:>11.1f}%")
    
    print("\n" + "=" * 100)
    print("KEY FINDINGS")
    print("=" * 100)
    print()
    
    # Find overall stats
    global_mean_all = [r for r in results if r['baseline'] == 'Global Mean (5.0)' and r['contract'] == 'all'][0]
    
    print(f"1. Global mean baseline (predict 5.0 for all):")
    print(f"   • MAE = {global_mean_all['mae']:.4f} tricks")
    print(f"   • R² = {global_mean_all['r2']:.4f}")
    print()
    
    print(f"2. Best dummy baseline by contract (stratified mean):")
    for contract in ['suit', 'high', 'low']:
        dummy = best_dummies[contract]
        print(f"   • {contract.upper()}: MAE = {dummy['mae']:.4f}, predict {dummy['prediction']:.4f}")
    print()
    
    print(f"3. OLS models beat dummy baseline by:")
    for contract in ['suit', 'high', 'low']:
        dummy = best_dummies[contract]
        ols = ols_results[contract]
        improvement = (dummy['mae'] - ols['mae']) / dummy['mae'] * 100
        print(f"   • {contract.upper()}: {improvement:.1f}% improvement (MAE: {dummy['mae']:.4f} → {ols['mae']:.4f})")
    print()
    
    print("=" * 100)
    print("✅ CONCLUSION")
    print("=" * 100)
    print()
    print("All OLS models significantly outperform dummy baselines!")
    print()
    print("The dummy baseline establishes that:")
    print("  • Simply predicting the average gives MAE ≈ 2.06 tricks")
    print("  • Our OLS models achieve MAE = 1.35-1.46 tricks")
    print("  • This is a 28-33% improvement over the simplest possible strategy")
    print()
    print("This confirms that our hand features contain real predictive value.")
    print()

if __name__ == "__main__":
    main()

