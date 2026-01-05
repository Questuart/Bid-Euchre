#!/usr/bin/env python3
"""
Evaluate bidding performance: dummy baseline vs OLS models.

Win = actual tricks >= bid
Loss = actual tricks < bid
"""

import json
import numpy as np
import pickle
from collections import defaultdict

# Paths
GREEDY_TEST = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.test.jsonl"
MODEL_DIR = "data/models/baseline_regression"

class SimpleOLS:
    """Simple OLS regression using numpy (needed for unpickling)."""
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

def load_models():
    """Load OLS models (extract coefficients only)."""
    models = {}
    for contract in ['suit', 'high', 'low']:
        path = f"{MODEL_DIR}/baseline_regression_{contract}.pkl"
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
            # Extract coefficients and feature names
            models[contract] = {
                'features': model_data['features'],
                'intercept': model_data['model'].intercept_,
                'coef': model_data['model'].coef_
            }
    return models

def load_test_data():
    """Load test data with features."""
    data = defaultdict(list)

    with open(GREEDY_TEST) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)

            if rec.get("event") != "hand_end":
                continue

            contract_type = rec.get("contract")
            if contract_type not in ['suit', 'high', 'low']:
                continue

            features_list = rec.get("features", [])
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)

            for player_idx, player_features in enumerate(features_list):
                if not isinstance(player_features, dict):
                    continue

                team_tricks = t0 if player_idx in (0, 2) else t1

                data[contract_type].append({
                    'features': player_features,
                    'actual_tricks': team_tricks
                })

    return data

def evaluate_bidding_strategy(data, models, strategy='dummy'):
    """Evaluate a bidding strategy."""
    results = defaultdict(lambda: {
        'wins': 0,
        'losses': 0,
        'exact': 0,
        'win_margins': [],
        'loss_margins': [],
        'bids': [],
        'actuals': []
    })

    for contract_type, hands in data.items():
        model_data = models[contract_type]
        feature_names = model_data['features']
        intercept = model_data['intercept']
        coef = model_data['coef']

        for hand in hands:
            actual = hand['actual_tricks']

            # Determine bid
            if strategy == 'dummy':
                bid = 5  # Always bid 5
            elif strategy == 'ols':
                # Extract features
                feature_vals = []
                for fname in feature_names:
                    if fname in hand['features']:
                        feature_vals.append(hand['features'][fname])
                    else:
                        feature_vals.append(0)

                # Predict manually: y = intercept + sum(coef * features)
                predicted = intercept + np.dot(coef, feature_vals)
                bid = int(round(predicted))

                # Clamp to valid range [0, 10]
                bid = max(0, min(10, bid))

            # Evaluate bid
            results[contract_type]['bids'].append(bid)
            results[contract_type]['actuals'].append(actual)

            if actual >= bid:
                # Win: made the bid
                results[contract_type]['wins'] += 1
                margin = actual - bid
                results[contract_type]['win_margins'].append(margin)

                if actual == bid:
                    results[contract_type]['exact'] += 1
            else:
                # Loss: failed the bid
                results[contract_type]['losses'] += 1
                margin = bid - actual
                results[contract_type]['loss_margins'].append(margin)

            # Also track "all" category
            results['all']['bids'].append(bid)
            results['all']['actuals'].append(actual)

            if actual >= bid:
                results['all']['wins'] += 1
                results['all']['win_margins'].append(actual - bid)
                if actual == bid:
                    results['all']['exact'] += 1
            else:
                results['all']['losses'] += 1
                results['all']['loss_margins'].append(bid - actual)

    return results

def print_results(results, strategy_name):
    """Print bidding performance results."""
    print(f"\n{'='*100}")
    print(f"{strategy_name.upper()} BIDDING STRATEGY")
    print('='*100)

    for contract in ['all', 'suit', 'high', 'low']:
        if contract not in results:
            continue

        r = results[contract]
        total = r['wins'] + r['losses']

        if total == 0:
            continue

        win_rate = r['wins'] / total * 100
        loss_rate = r['losses'] / total * 100
        exact_rate = r['exact'] / total * 100

        avg_win_margin = np.mean(r['win_margins']) if r['win_margins'] else 0
        avg_loss_margin = np.mean(r['loss_margins']) if r['loss_margins'] else 0

        avg_bid = np.mean(r['bids'])
        avg_actual = np.mean(r['actuals'])

        print(f"\n{contract.upper()}:")
        print(f"  Sample size:       {total:,} hands")
        print(f"  Average bid:       {avg_bid:.2f} tricks")
        print(f"  Average actual:    {avg_actual:.2f} tricks")
        print()
        print(f"  Wins (made bid):   {r['wins']:,} ({win_rate:.2f}%)")
        print(f"  Losses (failed):   {r['losses']:,} ({loss_rate:.2f}%)")
        print(f"  Exact bids:        {r['exact']:,} ({exact_rate:.2f}%)")
        print()
        print(f"  Avg win margin:    {avg_win_margin:.2f} tricks (overbid safety)")
        print(f"  Avg loss margin:   {avg_loss_margin:.2f} tricks (underbid penalty)")
        print()
        print("  Risk metrics:")
        print(f"    Max overbid:     {max(r['win_margins']) if r['win_margins'] else 0} tricks")
        print(f"    Max underbid:    {max(r['loss_margins']) if r['loss_margins'] else 0} tricks")

def compare_strategies(dummy_results, ols_results):
    """Compare two strategies side-by-side."""
    print(f"\n{'='*100}")
    print("STRATEGY COMPARISON")
    print('='*100)
    print()
    print(f"{'Contract':<12} {'Strategy':<12} {'Win Rate':<12} {'Loss Rate':<12} {'Avg Bid':<12} {'Avg Win Margin':<15} {'Avg Loss Margin':<15}")
    print('-'*100)

    for contract in ['all', 'suit', 'high', 'low']:
        if contract not in dummy_results:
            continue

        # Dummy
        d = dummy_results[contract]
        d_total = d['wins'] + d['losses']
        d_win_rate = d['wins'] / d_total * 100
        d_loss_rate = d['losses'] / d_total * 100
        d_avg_bid = np.mean(d['bids'])
        d_avg_win_margin = np.mean(d['win_margins']) if d['win_margins'] else 0
        d_avg_loss_margin = np.mean(d['loss_margins']) if d['loss_margins'] else 0

        # OLS
        o = ols_results[contract]
        o_total = o['wins'] + o['losses']
        o_win_rate = o['wins'] / o_total * 100
        o_loss_rate = o['losses'] / o_total * 100
        o_avg_bid = np.mean(o['bids'])
        o_avg_win_margin = np.mean(o['win_margins']) if o['win_margins'] else 0
        o_avg_loss_margin = np.mean(o['loss_margins']) if o['loss_margins'] else 0

        print(f"{contract:<12} {'Dummy (5)':<12} {d_win_rate:>10.2f}% {d_loss_rate:>10.2f}% {d_avg_bid:>10.2f}  {d_avg_win_margin:>13.2f}  {d_avg_loss_margin:>13.2f}")
        print(f"{contract:<12} {'OLS Model':<12} {o_win_rate:>10.2f}% {o_loss_rate:>10.2f}% {o_avg_bid:>10.2f}  {o_avg_win_margin:>13.2f}  {o_avg_loss_margin:>13.2f}")

        # Delta
        win_rate_delta = o_win_rate - d_win_rate
        symbol = "✅" if win_rate_delta > 0 else "⚠️" if win_rate_delta < 0 else "➖"
        print(f"{'':<12} {'Δ (OLS-Dum)':<12} {win_rate_delta:>+10.2f}% {o_loss_rate-d_loss_rate:>+10.2f}% {o_avg_bid-d_avg_bid:>+10.2f}  {o_avg_win_margin-d_avg_win_margin:>+13.2f}  {o_avg_loss_margin-d_avg_loss_margin:>+13.2f}  {symbol}")
        print()

def main():
    print("=" * 100)
    print("BIDDING PERFORMANCE EVALUATION")
    print("=" * 100)
    print()
    print("Comparing two bidding strategies:")
    print("  1. DUMMY: Always bid 5 tricks")
    print("  2. OLS:   Bid = round(predicted_tricks)")
    print()

    # Load models and data
    print("Loading models and test data...")
    models = load_models()
    data = load_test_data()

    total_hands = sum(len(hands) for hands in data.values())
    print(f"  Test set: {total_hands:,} hands")
    print()

    # Evaluate strategies
    print("Evaluating strategies...")
    dummy_results = evaluate_bidding_strategy(data, models, strategy='dummy')
    ols_results = evaluate_bidding_strategy(data, models, strategy='ols')

    # Print detailed results
    print_results(dummy_results, "DUMMY (Always Bid 5)")
    print_results(ols_results, "OLS Model")

    # Compare
    compare_strategies(dummy_results, ols_results)

    # Key insights
    print("=" * 100)
    print("🔍 KEY INSIGHTS")
    print("=" * 100)
    print()

    # Overall stats
    d_all = dummy_results['all']
    o_all = ols_results['all']

    d_total = d_all['wins'] + d_all['losses']
    o_total = o_all['wins'] + o_all['losses']

    d_win_rate = d_all['wins'] / d_total * 100
    o_win_rate = o_all['wins'] / o_total * 100

    print("1. WIN RATE IMPROVEMENT:")
    print(f"   Dummy: {d_win_rate:.2f}% | OLS: {o_win_rate:.2f}% | Δ = {o_win_rate - d_win_rate:+.2f}%")
    print()

    # Bidding calibration
    d_avg_bid = np.mean(d_all['bids'])
    o_avg_bid = np.mean(o_all['bids'])
    avg_actual = np.mean(d_all['actuals'])  # Same for both

    print("2. BIDDING CALIBRATION:")
    print(f"   Actual avg:  {avg_actual:.2f} tricks")
    print(f"   Dummy bids:  {d_avg_bid:.2f} tricks (bias = {d_avg_bid - avg_actual:+.2f})")
    print(f"   OLS bids:    {o_avg_bid:.2f} tricks (bias = {o_avg_bid - avg_actual:+.2f})")
    print()

    # Risk analysis
    d_avg_win = np.mean(d_all['win_margins']) if d_all['win_margins'] else 0
    o_avg_win = np.mean(o_all['win_margins']) if o_all['win_margins'] else 0

    d_avg_loss = np.mean(d_all['loss_margins']) if d_all['loss_margins'] else 0
    o_avg_loss = np.mean(o_all['loss_margins']) if o_all['loss_margins'] else 0

    print("3. RISK PROFILE:")
    print("   When winning (safety margin):")
    print(f"     Dummy: {d_avg_win:.2f} tricks | OLS: {o_avg_win:.2f} tricks")
    print("   When losing (penalty):")
    print(f"     Dummy: {d_avg_loss:.2f} tricks | OLS: {o_avg_loss:.2f} tricks")
    print()

    # Recommendation
    print("=" * 100)
    print("💡 RECOMMENDATION")
    print("=" * 100)
    print()

    if o_win_rate > d_win_rate:
        improvement = o_win_rate - d_win_rate
        print(f"✅ OLS model OUTPERFORMS dummy baseline by {improvement:.2f} percentage points!")
        print()
        print("The OLS model:")
        print(f"  • Makes {o_win_rate:.1f}% of bids (vs {d_win_rate:.1f}% for dummy)")
        print(f"  • Better calibrated to actual trick-taking (bias = {o_avg_bid - avg_actual:+.2f} vs {d_avg_bid - avg_actual:+.2f})")
        print(f"  • More conservative wins (margin = {o_avg_win:.2f} vs {d_avg_win:.2f})")
    else:
        print("⚠️  OLS model does NOT outperform dummy baseline")
        print()
        print("Possible reasons:")
        print("  • Prediction error compounds when converted to integer bids")
        print("  • Need better features or more complex model")
        print("  • Bidding strategy may need risk adjustment (bid +/- 1)")

    print()

if __name__ == "__main__":
    main()
