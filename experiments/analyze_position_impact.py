#!/usr/bin/env python3
"""
Analyze the impact of bidder position (seat) on hand outcomes.

This script:
1. Parses logged hands with schema v5 (dealer_position, bidder_position)
2. Analyzes how tricks won correlate with:
   - Being the bidder (vs defending)
   - Bidder's position relative to dealer (LOD, Partner, ROD, Dealer)
   - Dealer position itself
3. Generates visualizations showing positional advantage

Usage:
    PYTHONPATH=src python experiments/analyze_position_impact.py
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import Dict, List, Tuple

def parse_hand_logs(log_path: str) -> List[Dict]:
    """Parse JSONL logs and extract hand_end records."""
    hands = []
    
    with open(log_path, 'r') as f:
        for line in f:
            record = json.loads(line)
            if record.get('event') == 'hand_end':
                hands.append(record)
    
    return hands

def get_bidding_position_name(dealer_pos: int, bidder_pos: int) -> str:
    """Convert positions to bidding order name."""
    if bidder_pos == dealer_pos:
        return "Dealer"
    
    # Bidding order: LOD, Partner, ROD, Dealer
    # LOD = (dealer + 1) % 4
    # Partner = (dealer + 2) % 4
    # ROD = (dealer + 3) % 4
    
    lod = (dealer_pos + 1) % 4
    partner = (dealer_pos + 2) % 4
    rod = (dealer_pos + 3) % 4
    
    if bidder_pos == lod:
        return "LOD"
    elif bidder_pos == partner:
        return "Partner"
    elif bidder_pos == rod:
        return "ROD"
    else:
        return "Unknown"

def analyze_position_impact(hands: List[Dict]) -> Dict:
    """Analyze how position affects trick-taking."""
    
    # Track tricks won by position
    position_stats = defaultdict(lambda: {"tricks": [], "bids": [], "made_bid": []})
    
    # Track tricks won when bidding vs defending
    bidder_tricks = []
    defender_tricks = []
    
    # Track by seat (absolute position 0-3)
    seat_stats = defaultdict(lambda: {"tricks_as_bidder": [], "tricks_as_defender": []})
    
    for hand in hands:
        dealer_pos = hand.get('dealer_position')
        bidder_pos = hand.get('bidder_position')
        bid_amount = hand.get('winning_bid')
        t0 = hand['t0']
        t1 = hand['t1']
        
        # Skip misdeals
        if dealer_pos is None or bidder_pos is None:
            continue
        
        # Determine bidding position name
        pos_name = get_bidding_position_name(dealer_pos, bidder_pos)
        
        # Bidder's team
        bidder_team = 0 if bidder_pos in (0, 2) else 1
        tricks_won = t0 if bidder_team == 0 else t1
        
        # Record statistics
        position_stats[pos_name]["tricks"].append(tricks_won)
        position_stats[pos_name]["bids"].append(bid_amount)
        position_stats[pos_name]["made_bid"].append(1 if tricks_won >= bid_amount else 0)
        
        bidder_tricks.append(tricks_won)
        
        # Defenders (all 4 players, so average defender gets 1/2 of opposing team tricks)
        defender_team = 1 - bidder_team
        defender_team_tricks = t1 if defender_team == 1 else t0
        defender_tricks.append(defender_team_tricks)
        
        # Track by absolute seat
        seat_stats[bidder_pos]["tricks_as_bidder"].append(tricks_won)
        
        # Defenders' seats
        for seat in range(4):
            if (seat in (0, 2) and bidder_team == 1) or (seat in (1, 3) and bidder_team == 0):
                seat_stats[seat]["tricks_as_defender"].append(tricks_won)
    
    return {
        "position_stats": position_stats,
        "bidder_tricks": bidder_tricks,
        "defender_tricks": defender_tricks,
        "seat_stats": seat_stats,
    }

def generate_position_report(results: Dict, output_dir: str):
    """Generate visualizations and summary statistics."""
    os.makedirs(output_dir, exist_ok=True)
    
    position_stats = results["position_stats"]
    bidder_tricks = results["bidder_tricks"]
    defender_tricks = results["defender_tricks"]
    
    # ========================================================================
    # Figure 1: Bidder vs Defender Advantage
    # ========================================================================
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Positional Impact Analysis: Bidder Position and Trick-Taking", 
                 fontsize=16, fontweight='bold')
    
    # Subplot 1: Average tricks by bidding position
    ax = axes[0, 0]
    positions = ["LOD", "Partner", "ROD", "Dealer"]
    avg_tricks = [np.mean(position_stats[p]["tricks"]) if position_stats[p]["tricks"] else 0 
                  for p in positions]
    colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    bars = ax.bar(positions, avg_tricks, color=colors, alpha=0.7, edgecolor='black')
    ax.axhline(y=5.0, color='gray', linestyle='--', linewidth=1, label='Expected (5.0)')
    ax.set_ylabel("Average Tricks Won", fontsize=12, fontweight='bold')
    ax.set_title("Average Tricks Won by Bidding Position", fontsize=13, fontweight='bold')
    ax.set_ylim(0, 8)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar, val in zip(bars, avg_tricks):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold')
    
    # Subplot 2: Make-bid rate by position
    ax = axes[0, 1]
    make_rates = [np.mean(position_stats[p]["made_bid"]) * 100 if position_stats[p]["made_bid"] else 0 
                  for p in positions]
    
    bars = ax.bar(positions, make_rates, color=colors, alpha=0.7, edgecolor='black')
    ax.axhline(y=50, color='gray', linestyle='--', linewidth=1, label='Expected (50%)')
    ax.set_ylabel("Make-Bid Rate (%)", fontsize=12, fontweight='bold')
    ax.set_title("Make-Bid Rate by Bidding Position", fontsize=13, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, make_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # Subplot 3: Trick distribution (bidder vs defender)
    ax = axes[1, 0]
    
    bins = np.arange(0, 11, 1)
    ax.hist(bidder_tricks, bins=bins, alpha=0.6, label='Bidder Team', color='#2ca02c', edgecolor='black')
    ax.hist(defender_tricks, bins=bins, alpha=0.6, label='Defender Team', color='#d62728', edgecolor='black')
    
    ax.axvline(x=np.mean(bidder_tricks), color='#2ca02c', linestyle='--', linewidth=2, 
               label=f'Bidder Avg: {np.mean(bidder_tricks):.2f}')
    ax.axvline(x=np.mean(defender_tricks), color='#d62728', linestyle='--', linewidth=2, 
               label=f'Defender Avg: {np.mean(defender_tricks):.2f}')
    
    ax.set_xlabel("Tricks Won", fontsize=12, fontweight='bold')
    ax.set_ylabel("Frequency", fontsize=12, fontweight='bold')
    ax.set_title("Trick Distribution: Bidder vs Defender", fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # Subplot 4: Average bid by position
    ax = axes[1, 1]
    avg_bids = [np.mean(position_stats[p]["bids"]) if position_stats[p]["bids"] else 0 
                for p in positions]
    
    bars = ax.bar(positions, avg_bids, color=colors, alpha=0.7, edgecolor='black')
    ax.set_ylabel("Average Bid Amount", fontsize=12, fontweight='bold')
    ax.set_title("Average Bid Amount by Position", fontsize=13, fontweight='bold')
    ax.set_ylim(0, 8)
    ax.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, avg_bids):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "position_impact_analysis.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved visualization: {output_path}")
    
    # ========================================================================
    # Print Summary Statistics
    # ========================================================================
    
    print("\n" + "="*80)
    print("POSITIONAL IMPACT ANALYSIS SUMMARY")
    print("="*80)
    
    print("\n1. AVERAGE TRICKS WON BY BIDDING POSITION:")
    print("-" * 80)
    print(f"{'Position':<12} {'Avg Tricks':<12} {'Make Rate':<12} {'Avg Bid':<12} {'N':<10}")
    print("-" * 80)
    
    for pos in positions:
        stats = position_stats[pos]
        if stats["tricks"]:
            avg_t = np.mean(stats["tricks"])
            make_r = np.mean(stats["made_bid"]) * 100
            avg_b = np.mean(stats["bids"])
            n = len(stats["tricks"])
            print(f"{pos:<12} {avg_t:<12.2f} {make_r:<11.1f}% {avg_b:<12.2f} {n:<10,}")
    
    print("\n2. BIDDER VS DEFENDER ADVANTAGE:")
    print("-" * 80)
    print(f"Bidder Team Avg Tricks:   {np.mean(bidder_tricks):.3f}")
    print(f"Defender Team Avg Tricks: {np.mean(defender_tricks):.3f}")
    print(f"Bidder Advantage:         +{np.mean(bidder_tricks) - np.mean(defender_tricks):.3f} tricks")
    print(f"(Expected: 0.0 if no positional advantage)")
    
    print("\n3. KEY INSIGHTS:")
    print("-" * 80)
    
    # Find best and worst positions
    avg_by_pos = {p: np.mean(position_stats[p]["tricks"]) for p in positions if position_stats[p]["tricks"]}
    if avg_by_pos:
        best_pos = max(avg_by_pos, key=avg_by_pos.get)
        worst_pos = min(avg_by_pos, key=avg_by_pos.get)
        
        print(f"• Best Position:  {best_pos} ({avg_by_pos[best_pos]:.2f} tricks)")
        print(f"• Worst Position: {worst_pos} ({avg_by_pos[worst_pos]:.2f} tricks)")
        print(f"• Position Spread: {avg_by_pos[best_pos] - avg_by_pos[worst_pos]:.2f} tricks")
    
    # Bidder advantage
    bidder_adv = np.mean(bidder_tricks) - 5.0
    print(f"\n• Bidder Team wins {bidder_adv:+.2f} more tricks than expected (5.0)")
    
    if bidder_adv > 0.5:
        print("  → SIGNIFICANT lead advantage! Being the bidder matters.")
    elif bidder_adv > 0.2:
        print("  → Moderate lead advantage. Bidder has slight edge.")
    else:
        print("  → Minimal lead advantage. Position doesn't matter much.")
    
    print("="*80)

def main():
    # Check for existing logs with position data
    log_dir = "data/hand_logs"
    
    # Look for any recent logs with schema v5
    if not os.path.exists(log_dir):
        print(f"❌ Log directory not found: {log_dir}")
        print("Please run an experiment first with the updated logger.")
        return
    
    # Find most recent log file
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.jsonl')]
    if not log_files:
        print(f"❌ No log files found in {log_dir}")
        print("Please run an experiment first with the updated logger.")
        return
    
    # Sort by modification time (most recent first)
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
    
    # Check the most recent log for schema v5
    for log_file in log_files:
        log_path = os.path.join(log_dir, log_file)
        print(f"\n📂 Checking log file: {log_file}")
        
        # Check if it has position data
        with open(log_path, 'r') as f:
            first_hand = None
            for line in f:
                record = json.loads(line)
                if record.get('event') == 'hand_end':
                    first_hand = record
                    break
            
            if first_hand and 'dealer_position' in first_hand:
                print(f"✅ Found log with position data (schema v{first_hand.get('schema_version', '?')})")
                print(f"   Parsing hands from: {log_path}")
                
                hands = parse_hand_logs(log_path)
                print(f"   Loaded {len(hands):,} hands")
                
                # Analyze
                results = analyze_position_impact(hands)
                
                # Generate report
                generate_position_report(results, output_dir="data/reports")
                
                return
            else:
                print(f"   ⚠️  No position data in this log (schema v{first_hand.get('schema_version', '?') if first_hand else '?'})")
    
    print("\n❌ No logs with position data found!")
    print("Please run a new experiment to generate logs with schema v5.")

if __name__ == "__main__":
    main()
