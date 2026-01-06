# Strategy Comparison Framework

## Overview

This document describes the strategy comparison framework for evaluating Bid Euchre AI strategies on common deals.

## Implemented Strategies

### 1. GreedyStrategy (Baseline)
- **Algorithm**: 1-trick lookahead
- **Behavior**: For each legal card, simulates playing that card and winning/losing the current trick, then chooses the card that maximizes immediate trick-winning probability
- **Purpose**: Current "best" strategy, serves as the baseline for comparison

### 2. RandomLegalStrategy
- **Algorithm**: Uniform random selection among legal moves
- **Behavior**: Chooses uniformly at random from all legal cards
- **Purpose**:
  - Sets a floor (greedy should beat it)
  - Catches bugs (if random wins too often, something is wrong)
  - Validates suit-following enforcement

### 3. AlwaysLowestLegalStrategy
- **Algorithm**: Play the lowest-ranked legal card
- **Behavior**: Among legal cards, plays the weakest card available
- **Card Ranking**: Bowers > Trump (A>K>Q>J>T) > Offsuit (A>K>Q>J>T)
- **Purpose**:
  - Extreme conservatism baseline
  - Tests "never spend power unless forced" strategy
  - Deterministic and interpretable
  - Often does okay at not wasting trump, but loses because it never takes initiative

### 4. AlwaysHighestLegalStrategy
- **Algorithm**: Play the highest-ranked legal card
- **Behavior**: Among legal cards, plays the strongest card available
- **Card Ranking**: Same as AlwaysLowest
- **Purpose**:
  - Extreme aggression baseline
  - Stresses trick resolution logic
  - Shows how bad "myopic max strength" is
  - Exposes waste patterns (burning bowers/trump early, overkilling cheap tricks, setting up partner poorly)

## Common Deals

All strategies play **identical card deals** using a deterministic deal generator (`src/bid_euchre/sim/deals.py`). This ensures:
- Fair comparison (no strategy gets "lucky" with better cards)
- Statistical power (differences are due to strategy, not variance)
- Reproducibility (same seed = same results)

### Deal Generation
```python
def generate_deal(seed: int, deal_id: int) -> List[Card]:
    """
    Generates a deterministic deck for a specific (seed, deal_id) pair.
    """
    deal_specific_seed = seed * 1000000 + deal_id
    rng = random.Random(deal_specific_seed)
    deck = create_deck()
    rng.shuffle(deck)
    return deck
```

## Running Comparisons

### 1. Run Multi-Strategy Simulation
```bash
# Run all 4 strategies on 50,000 hands per scenario
PYTHONPATH=src python experiments/run_strategy_comparison.py \
    --n_per 50000 \
    --seed 42 \
    --log-level hand
```

**Output Structure:**
```
data/runs/strategy_comparison_42_<timestamp>/
├── meta.json                    # Run metadata
├── results/
│   ├── greedy/
│   │   ├── suit_C.json
│   │   ├── suit_D.json
│   │   ├── suit_H.json
│   │   ├── suit_S.json
│   │   ├── high.json
│   │   └── low.json
│   ├── random_legal/
│   │   └── ... (same structure)
│   ├── always_lowest/
│   │   └── ... (same structure)
│   └── always_highest/
│       └── ... (same structure)
└── logs/
    ├── strategy_comparison_42_<timestamp>_greedy.jsonl
    ├── strategy_comparison_42_<timestamp>_random_legal.jsonl
    ├── strategy_comparison_42_<timestamp>_always_lowest.jsonl
    └── strategy_comparison_42_<timestamp>_always_highest.jsonl
```

### 2. Generate Comparison Report
```bash
PYTHONPATH=src python experiments/generate_strategy_comparison.py \
    --run-dir data/runs/strategy_comparison_42_<timestamp> \
    --seed 42 \
    --baseline random_legal
```

**Output:**
- `data/runs/<run_id>/dashboard/comparison_<timestamp>/strategy_comparison.png`

**Report Contents:**
1. **Mean Tricks Comparison**: Bar chart of aggregate mean tricks per strategy
2. **Win Rate Comparison**: Bar chart of win rates (≥6 tricks) per strategy
3. **Δ Tricks Distribution**: Violin plot showing distribution of trick deltas vs baseline
4. **Scenario Heatmap**: Mean tricks for all strategies across all scenarios
5. **Summary Table**: Comprehensive statistics (mean, stddev, win rate, delta)

### 3. Generate Individual Strategy Dashboards
```bash
# For each strategy
PYTHONPATH=src python experiments/generate_dashboard.py \
    --run-dir data/runs/strategy_comparison_42_<timestamp> \
    --strategy <strategy_name> \
    --seed 42
```

## Expected Results

### Random Legal
- **Expected Win Rate**: ~40% (pure chance + symmetry)
- **Expected Mean Tricks**: ~5.0 (symmetric)
- **Key Insight**: If greedy doesn't beat random by a significant margin, there's a bug

### Always Lowest
- **Expected Win Rate**: 30-35% (very conservative)
- **Expected Mean Tricks**: 4.5-4.8 (gives away tricks)
- **Key Insight**: Shows cost of never taking initiative

### Always Highest
- **Expected Win Rate**: 35-40% (wastes power)
- **Expected Mean Tricks**: 4.7-5.0 (overkills)
- **Key Insight**: Shows cost of myopic aggression

### Greedy (Baseline)
- **Expected Win Rate**: 38-42% (best among these 4)
- **Expected Mean Tricks**: 5.0-5.1 (slightly above random)
- **Key Insight**: 1-trick lookahead provides modest advantage

## Statistical Analysis

### Confidence Intervals
For win rates, 95% confidence interval:
```
CI = p ± 1.96 * sqrt(p * (1-p) / n)
```
With n=50,000 per scenario:
- For p=0.40: CI = ±0.0043 (±0.43%)
- Very tight intervals ensure differences are statistically significant

### Effect Size (Cohen's d)
```
d = (mean_A - mean_B) / pooled_stddev
```
- |d| < 0.2: negligible
- 0.2 ≤ |d| < 0.5: small
- 0.5 ≤ |d| < 0.8: medium
- |d| ≥ 0.8: large

## Testing

### Unit Tests
```bash
# Run tests for new strategies
PYTHONPATH=src pytest tests/test_null_strategies.py -v
```

### Integration Test
```bash
# Validate all strategies complete a full game
PYTHONPATH=src python scripts/validate_tests.py
```

## Future Extensions

### Additional Baseline Strategies
- **AlwaysTrumpStrategy**: Always play trump if possible
- **MimicPartnerStrategy**: Try to match partner's suit
- **CountCardsStrategy**: Track played cards for better decisions

### Advanced Comparisons
- **Per-Feature Slices**: How does each strategy perform when trump_count is high?
- **Position Analysis**: Does strategy performance vary by seat?
- **Contract-Specific**: Which strategies excel at specific contract types?

## Implementation Files

- `src/bid_euchre/strategy/strategy.py`: Strategy implementations
- `experiments/run_strategy_comparison.py`: Multi-strategy simulation runner
- `experiments/generate_strategy_comparison.py`: Comparison report generator
- `tests/test_null_strategies.py`: Unit tests for null strategies
- `src/bid_euchre/sim/deals.py`: Deterministic deal generator

## References

- Trick-Taking Game AI: [Wikipedia](https://en.wikipedia.org/wiki/Trick-taking_game)
- Monte Carlo Evaluation: Silver et al. (2016)
- Common Random Numbers: Law & Kelton (2000)
