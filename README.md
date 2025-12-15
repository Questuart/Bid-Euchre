# Bid Euchre AI Research Framework

A comprehensive framework for simulating and analyzing the card game Bid Euchre with various AI strategies and experimental configurations.

## 🎯 Overview

Bid Euchre is a trick-taking card game similar to standard Euchre but with some key differences:
- **40-card deck** (4 suits × 5 ranks, no 9s)
- **4 players** in teams of 2
- **Special mechanics**: Left/right bowers (Jack of opposite suit)
- **Contract types**: Suit, High, Low

This framework provides a complete research platform for developing and testing AI strategies for Bid Euchre.

## 🚀 Quick Start

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd bid-euchre

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage
```python
from bid_euchre.sim import simulation
from bid_euchre.strategy import GreedyStrategy

# Run a simulation with Greedy strategy
result = simulation.simulate_many_hands(1000, "suit", "H", strategy=GreedyStrategy())
print(f"Team 0 average tricks: {result['avg_team0']:.2f}")
```

### Run Experiments
```bash
# Run comprehensive baseline analysis
PYTHONPATH=src python experiments/run_baseline_greedy.py --n_per 50000 --seed 42

# Generate analysis reports
PYTHONPATH=src python experiments/make_phase1.5_report.py
```

## 🏗️ Architecture

```
bid-euchre/
├── src/bid_euchre/           # Core package
│   ├── core/                  # Game mechanics (cards, rules)
│   ├── strategy/              # AI strategy implementations
│   ├── features/              # Hand evaluation features
│   ├── sim/                   # Simulation engines
│   └── experiments/           # Configuration system
├── experiments/               # Research scripts & configs
├── tests/                     # Comprehensive test suite
└── data/                      # Simulation results & reports
```

## 🤖 Available Strategies

- **BasicStrategy**: Simple rule-based strategy
- **GreedyStrategy**: One-trick lookahead optimization

### Custom Strategies
```python
from bid_euchre.strategy import Strategy

class MyStrategy(Strategy):
    def choose_card(self, hand, plays_so_far, contract_type, trump_suit, player_index):
        # Your AI logic here
        return card_index
```

## 📊 Experiment Configuration

Experiments can be configured via YAML:

```yaml
experiment_name: "strategy_comparison"
strategies:
  - name: "greedy"
    class_name: "GreedyStrategy"
scenarios:
  - contract_type: "suit"
    trump_suit: "C,D,H,S"
  - contract_type: "high"
parameters:
  n_per: 50000
  seed: 42
```

## 🧪 Testing

### Quick Validation (Recommended)
```bash
python scripts/validate_tests.py
```
Fast validation of all core functionality (no pytest required).

### Full Test Suite (Requires pytest)
```bash
# Install pytest first
pip install pytest pytest-cov

# Then run tests
python scripts/run_tests.py --unit        # Core functionality
python scripts/run_tests.py --integration # End-to-end workflows
python scripts/run_tests.py --performance # Speed & scalability
```

### Direct pytest Usage
```bash
PYTHONPATH=src pytest tests/ -v --cov=src/bid_euchre
```

## 📈 Analysis Features

- **Statistical validation**: Monte Carlo analysis with confidence intervals
- **Strategy comparison**: Automated performance metrics
- **Feature correlation**: Hand strength analysis (79+ visualization plots)
- **Data export**: JSON results with comprehensive metadata

## 🎯 Research Applications

- **Strategy development**: Build and test AI players
- **Game analysis**: Understand optimal play patterns
- **Statistical modeling**: Trick probability distributions
- **Feature engineering**: Hand strength evaluation

## 📚 Documentation

- `tests/README.md`: Test suite documentation
- Inline code documentation with comprehensive docstrings
- Example usage in experiment scripts

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the full test suite
5. Submit a pull request

## 📄 License

[Add license information here]

## 🙏 Acknowledgments

Built for AI research in trick-taking card games. Special thanks to the Euchre community for the inspiration.
