#!/usr/bin/env python3
"""
Train "Hand Value" OLS regression models (OLSa HV).
This script calculates hand values based on specific weighting definitions:
- Suit: uses bower (120/110) and trump (100-60) vs offsuit (50-10) logic.
- High/Low: uses fixed weights (A=50, K=40, Q=30, J=20, T=10).

Usage:
    python experiments/train_hand_value_ols.py
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

OUTPUT_DIR = "data/models/hand_value_ols"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Bower logic helpers
SAME_COLOR_SUIT = {"S": "C", "C": "S", "H": "D", "D": "H"}

def calculate_hand_value(hand_cards, contract_type, trump_suit):
    """
    Calculate hand value based on user-requested definitions.
    hand_cards: list of [rank, suit] or [suit, rank] (based on log format)
    """
    score = 0
    if contract_type == "suit":
        weights_trump = {"A": 100, "K": 90, "Q": 80, "J": 70, "T": 60}
        weights_offsuit = {"A": 50, "K": 40, "Q": 30, "J": 20, "T": 10}
        
        for rank, suit in hand_cards:
            # Check for bowers
            if rank == "J" and suit == trump_suit:
                score += 120
            elif rank == "J" and suit == SAME_COLOR_SUIT.get(trump_suit):
                score += 110
            elif suit == trump_suit:
                score += weights_trump.get(rank, 0)
            else:
                score += weights_offsuit.get(rank, 0)
    else:
        # Fixed weights for both High and Low as requested
        weights = {"A": 50, "K": 40, "Q": 30, "J": 20, "T": 10}
        for rank, suit in hand_cards:
            score += weights.get(rank, 0)
    return score

def load_data(jsonl_path, contract_type):
    """Load hand values and targets for a specific contract type."""
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
            
            hands_list = rec.get("hands", []) # List of 4 hands
            trump_suit = rec.get("trump")
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)
            
            for player_idx, hand_cards in enumerate(hands_list):
                # hand_cards is list of [rank, suit] or [suit, rank]
                # In our logs it is [rank, suit] e.g. ["S", "K"]
                # Wait, looking at the pretty print: "hands": [[["S", "K"], ["S", "Q"], ...]]
                # So it is [suit, rank]. Let's adjust calculate_hand_value
                
                # Correcting hand_cards parsing: [suit, rank]
                normalized_hand = [[card[1], card[0]] for card in hand_cards]
                
                h_val = calculate_hand_value(normalized_hand, contract_type, trump_suit)
                
                # Target: team tricks
                team_tricks = t0 if player_idx in (0, 2) else t1
                
                X_list.append([h_val])
                y_list.append(team_tricks)
    
    return np.array(X_list), np.array(y_list)

def r2_score(y_true, y_pred):
    """Calculate R² score."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0: return 0.0
    return 1 - (ss_res / ss_tot)

def mean_absolute_error(y_true, y_pred):
    """Calculate MAE."""
    return np.mean(np.abs(y_true - y_pred))

def mean_squared_error(y_true, y_pred):
    """Calculate MSE."""
    return np.mean((y_true - y_pred) ** 2)

def train_and_evaluate(contract_type):
    """Train OLS model for a contract type."""
    print(f"\n{'='*80}")
    print(f"Training: hand_value_ols_{contract_type}")
    print('='*80)
    
    # Load data
    print("Loading data and calculating hand values...")
    X_train, y_train = load_data(GREEDY_TRAIN, contract_type)
    X_val, y_val = load_data(GREEDY_VAL, contract_type)
    X_test, y_test = load_data(GREEDY_TEST, contract_type)
    
    print(f"  Train: {len(X_train):,} hands")
    print(f"  Val:   {len(X_val):,} hands")
    print(f"  Test:  {len(X_test):,} hands")
    
    # Print sample to verify logic
    if len(X_train) > 0:
        print(f"  Sample Hand Value: {X_train[0][0]}, Tricks: {y_train[0]}")
    
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
        
        print(f"\n{split_name}:")
        print(f"  R² score:  {r2:.4f}")
        print(f"  MAE:       {mae:.4f} tricks")
    
    # Coefficients
    print("\n" + "-"*80)
    print("MODEL COEFFICIENTS:")
    print("-"*80)
    print(f"Intercept: {model.intercept_:.4f}")
    print(f"  hand_value                     {model.coef_[0]:+.4f}")
    
    # Save model
    model_path = os.path.join(OUTPUT_DIR, f"hand_value_ols_{contract_type}.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'features': ['hand_value'],
            'contract_type': contract_type
        }, f)
    print(f"\n✅ Model saved: {model_path}")
    
    return {
        'contract_type': contract_type,
        'train_r2': r2_score(y_train, y_train_pred),
        'test_r2': r2_score(y_test, y_test_pred),
        'test_mae': mean_absolute_error(y_test, y_test_pred),
    }

def main():
    print("=" * 80)
    print("HAND VALUE OLS REGRESSION MODELS")
    print("=" * 80)
    
    results = []
    for contract_type in ['suit', 'high', 'low']:
        result = train_and_evaluate(contract_type)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY - ALL HAND VALUE MODELS")
    print("=" * 80)
    print(f"\n{'Model':<25} {'Train R²':<12} {'Test R²':<12} {'Test MAE':<12}")
    print("-" * 80)
    
    for r in results:
        model_name = f"olsa_hv_{r['contract_type']}"
        print(f"{model_name:<25} {r['train_r2']:<12.4f} {r['test_r2']:<12.4f} {r['test_mae']:<12.4f}")
    
    print("\n" + "=" * 80)
    print("✅ All hand value models trained!")
    print("=" * 80)

if __name__ == "__main__":
    main()

