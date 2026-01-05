#!/usr/bin/env python3
"""
Generate comparison dashboard for OLSa_v2 vs OLSa_SR_v2 models.
"""

import sys
import csv
import pickle
import matplotlib.pyplot as plt

sys.path.insert(0, 'src')


def load_data(csv_path, contract_type, features):
    """Load data for specific contract and features."""
    X, y = [], []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['contract_type'] != contract_type:
                continue
            X.append([float(row.get(f, 0)) for f in features])
            y.append(float(row['actual_tricks']))
    return X, y


def calc_r2(y_true, y_pred):
    """Calculate R² score."""
    ss_res = sum((yt - yp)**2 for yt, yp in zip(y_true, y_pred))
    ss_tot = sum((yt - sum(y_true)/len(y_true))**2 for yt in y_true)
    return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0


def calc_mae(y_true, y_pred):
    """Calculate MAE."""
    return sum(abs(yt - yp) for yt, yp in zip(y_true, y_pred)) / len(y_true)


def main():
    print("Loading models...")
    
    # Load all models
    models = {}
    for family in ['olsa_v2', 'olsa_sr_v2']:
        models[family] = {}
        for contract in ['suit', 'high', 'low']:
            path = f'data/models/{family}/{family}_{contract}.pkl'
            with open(path, 'rb') as f:
                models[family][contract] = pickle.load(f)
    
    # Feature sets
    features_olsa = {
        'suit': ['trump_count', 'trump_rb_count', 'trump_lb_count', 'offsuit_aces', 'is_bidder'],
        'high': ['offsuit_aces', 'offsuit_length_3plus_count', 'is_bidder'],
        'low': ['offsuit_length_3plus_count', 'is_bidder'],
    }
    
    features_sr = {
        'suit': ['hand_value', 'is_bidder'],
        'high': ['hand_value', 'is_bidder'],
        'low': ['hand_value', 'is_bidder'],
    }
    
    # Load test data and evaluate
    print("Evaluating models on test set...")
    results = {'olsa_v2': {}, 'olsa_sr_v2': {}}
    
    for contract in ['suit', 'high', 'low']:
        # OLSa_v2
        X_test, y_test = load_data('data/training/bidder_aware_test.csv', contract, features_olsa[contract])
        y_pred = models['olsa_v2'][contract].predict(X_test)
        results['olsa_v2'][contract] = {
            'r2': calc_r2(y_test, y_pred),
            'mae': calc_mae(y_test, y_pred),
            'y_test': y_test,
            'y_pred': y_pred,
            'coefs': list(models['olsa_v2'][contract].coef_),
            'features': features_olsa[contract],
        }
        
        # OLSa_SR_v2
        X_test, y_test = load_data('data/training/bidder_aware_test.csv', contract, features_sr[contract])
        y_pred = models['olsa_sr_v2'][contract].predict(X_test)
        results['olsa_sr_v2'][contract] = {
            'r2': calc_r2(y_test, y_pred),
            'mae': calc_mae(y_test, y_pred),
            'y_test': y_test,
            'y_pred': y_pred,
            'coefs': list(models['olsa_sr_v2'][contract].coef_),
            'features': features_sr[contract],
        }
    
    # Create dashboard
    print("Creating dashboard...")
    fig = plt.figure(figsize=(20, 12))
    
    # Color scheme
    color_olsa = '#2E86AB'  # Blue
    color_sr = '#A23B72'    # Purple
    
    contracts = ['suit', 'high', 'low']
    contract_labels = ['SUIT', 'HIGH', 'LOW']
    
    # 1. R² Comparison
    ax1 = plt.subplot(2, 3, 1)
    x_pos = range(len(contracts))
    r2_olsa = [results['olsa_v2'][c]['r2'] for c in contracts]
    r2_sr = [results['olsa_sr_v2'][c]['r2'] for c in contracts]
    
    width = 0.35
    ax1.bar([p - width/2 for p in x_pos], r2_olsa, width, label='OLSa_v2', color=color_olsa, alpha=0.8)
    ax1.bar([p + width/2 for p in x_pos], r2_sr, width, label='OLSa_SR_v2', color=color_sr, alpha=0.8)
    
    ax1.set_ylabel('R² Score', fontweight='bold', fontsize=11)
    ax1.set_title('Test Set R² by Contract', fontweight='bold', fontsize=13)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(contract_labels)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    ax1.set_ylim(0, max(r2_olsa + r2_sr) * 1.2)
    
    # Add value labels
    for i, (v1, v2) in enumerate(zip(r2_olsa, r2_sr)):
        ax1.text(i - width/2, v1 + 0.01, f'{v1:.3f}', ha='center', va='bottom', fontsize=9)
        ax1.text(i + width/2, v2 + 0.01, f'{v2:.3f}', ha='center', va='bottom', fontsize=9)
    
    # 2. MAE Comparison
    ax2 = plt.subplot(2, 3, 2)
    mae_olsa = [results['olsa_v2'][c]['mae'] for c in contracts]
    mae_sr = [results['olsa_sr_v2'][c]['mae'] for c in contracts]
    
    ax2.bar([p - width/2 for p in x_pos], mae_olsa, width, label='OLSa_v2', color=color_olsa, alpha=0.8)
    ax2.bar([p + width/2 for p in x_pos], mae_sr, width, label='OLSa_SR_v2', color=color_sr, alpha=0.8)
    
    ax2.set_ylabel('Mean Absolute Error (tricks)', fontweight='bold', fontsize=11)
    ax2.set_title('Test Set MAE by Contract', fontweight='bold', fontsize=13)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(contract_labels)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for i, (v1, v2) in enumerate(zip(mae_olsa, mae_sr)):
        ax2.text(i - width/2, v1 + 0.03, f'{v1:.2f}', ha='center', va='bottom', fontsize=9)
        ax2.text(i + width/2, v2 + 0.03, f'{v2:.2f}', ha='center', va='bottom', fontsize=9)
    
    # 3. Winner Summary
    ax3 = plt.subplot(2, 3, 3)
    ax3.axis('off')
    
    summary_text = "MODEL COMPARISON SUMMARY\n\n"
    summary_text += "Winner by Contract:\n"
    for i, contract in enumerate(contracts):
        r2_diff = results['olsa_v2'][contract]['r2'] - results['olsa_sr_v2'][contract]['r2']
        winner = "OLSa_v2" if r2_diff > 0 else "OLSa_SR_v2"
        winner_color = color_olsa if r2_diff > 0 else color_sr
        summary_text += f"  {contract_labels[i]}: "
        ax3.text(0.35, 0.68 - i*0.08, winner, ha='left', va='center', 
                fontweight='bold', fontsize=12, color=winner_color,
                transform=ax3.transAxes)
        summary_text_line = f"(R² {'+' if r2_diff > 0 else ''}{r2_diff:.4f})"
        ax3.text(0.55, 0.68 - i*0.08, summary_text_line, ha='left', va='center',
                fontsize=10, color='gray', transform=ax3.transAxes)
    
    ax3.text(0.5, 0.9, 'WINNER BY CONTRACT', ha='center', va='top',
            fontweight='bold', fontsize=14, transform=ax3.transAxes)
    ax3.text(0.5, 0.82, '(Higher R² = Better)', ha='center', va='top',
            fontsize=10, color='gray', transform=ax3.transAxes)
    
    # Overall winner
    olsa_wins = sum(1 for c in contracts if results['olsa_v2'][c]['r2'] > results['olsa_sr_v2'][c]['r2'])
    overall_winner = "OLSa_v2" if olsa_wins >= 2 else "OLSa_SR_v2"
    overall_color = color_olsa if olsa_wins >= 2 else color_sr
    
    ax3.text(0.5, 0.30, 'OVERALL WINNER', ha='center', va='top',
            fontweight='bold', fontsize=14, transform=ax3.transAxes)
    ax3.text(0.5, 0.20, overall_winner, ha='center', va='top',
            fontweight='bold', fontsize=16, color=overall_color, transform=ax3.transAxes)
    ax3.text(0.5, 0.10, f'({olsa_wins} / 3 contracts)', ha='center', va='top',
            fontsize=11, color='gray', transform=ax3.transAxes)
    
    # 4-6. Predicted vs Actual for each contract
    for idx, contract in enumerate(contracts):
        ax = plt.subplot(2, 3, 4 + idx)
        
        # Plot both models
        y_test_olsa = results['olsa_v2'][contract]['y_test']
        y_pred_olsa = results['olsa_v2'][contract]['y_pred']
        y_test_sr = results['olsa_sr_v2'][contract]['y_test']
        y_pred_sr = results['olsa_sr_v2'][contract]['y_pred']
        
        # Scatter plots with transparency
        ax.scatter(y_test_olsa, y_pred_olsa, alpha=0.3, s=10, color=color_olsa, label='OLSa_v2')
        ax.scatter(y_test_sr, y_pred_sr, alpha=0.3, s=10, color=color_sr, label='OLSa_SR_v2')
        
        # Perfect prediction line
        max_val = max(max(y_test_olsa), max(y_test_sr), max(y_pred_olsa), max(y_pred_sr))
        ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, linewidth=1, label='Perfect')
        
        ax.set_xlabel('Actual Tricks', fontweight='bold', fontsize=10)
        ax.set_ylabel('Predicted Tricks', fontweight='bold', fontsize=10)
        ax.set_title(f'{contract_labels[idx]} Contract\n(Predicted vs Actual)', 
                    fontweight='bold', fontsize=12)
        ax.legend(fontsize=9, loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add R² annotations
        r2_olsa = results['olsa_v2'][contract]['r2']
        r2_sr = results['olsa_sr_v2'][contract]['r2']
        ax.text(0.98, 0.15, f'OLSa_v2 R²={r2_olsa:.3f}', 
               transform=ax.transAxes, ha='right', va='top',
               fontsize=9, color=color_olsa, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=color_olsa))
        ax.text(0.98, 0.05, f'OLSa_SR_v2 R²={r2_sr:.3f}', 
               transform=ax.transAxes, ha='right', va='top',
               fontsize=9, color=color_sr, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=color_sr))
    
    plt.suptitle('Bidder-Aware Models Comparison: OLSa_v2 vs OLSa_SR_v2',
                fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save
    output_path = 'data/reports/bidder_models_dashboard.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ Dashboard saved to: {output_path}")
    plt.close()


if __name__ == "__main__":
    main()
