# Bid Euchre Tests

**Last updated:** 2026-01-04
**Organization:** Tests organized by type (unit/integration/performance)

This directory contains comprehensive tests for the Bid Euchre simulation project.

---

## 📂 Directory Structure

```
tests/
├── unit/                  # Fast, isolated tests (9 files)
├── integration/           # Multi-component tests (4 files)
├── performance/           # Speed/memory tests (1 file)
└── README.md             # This file
```

**Total:** 14 test files with 19+ test functions

---

## 🚀 Running Tests

### All tests
```bash
PYTHONPATH=src python -m pytest tests/
```

### Unit tests only (fast - recommended for quick validation)
```bash
PYTHONPATH=src python -m pytest tests/unit/
```

### Integration tests only
```bash
PYTHONPATH=src python -m pytest tests/integration/
```

### Performance tests
```bash
PYTHONPATH=src python -m pytest tests/performance/
```

### Specific test file
```bash
PYTHONPATH=src python tests/unit/test_bidder_models.py
```

### With verbose output
```bash
PYTHONPATH=src python -m pytest tests/ -v
```

---

## 📋 Test Categories

### Unit Tests (`unit/`)

**Purpose:** Test individual components in isolation

**Characteristics:**
- Test single functions/classes
- Minimal or no file I/O
- No network access
- Fast (< 1 second each)
- No dependencies on other components

**Files:**
- `test_cards.py` - Card representation and ordering
- `test_rules.py` - Game rules (trick winners, legal plays)
- `test_hand_eval.py` - Hand feature extraction
- `test_bidder_models.py` - Model predictions ⭐ NEW
- `test_strategy.py` - Strategy interface
- `test_null_strategies.py` - Baseline strategies
- `test_improved_greedy.py` - Greedy variants
- `test_strategy_correctness.py` - Strategy validation
- `test_leading_fix.py` - Lead mechanics

**Running:** ~9 test files, < 5 seconds total

### Integration Tests (`integration/`)

**Purpose:** Test multiple components working together

**Characteristics:**
- Test full workflows
- May involve file I/O
- Run small simulations (10-100 hands)
- Slower (1-30 seconds each)
- Test component interactions

**Files:**
- `test_integration.py` - Full game simulation end-to-end
- `test_model_integration.py` - Models in gameplay ⭐ NEW
- `test_simulation_validation.py` - Simulation correctness
- `test_bidding_logic.py` - Bidding engine

**Running:** ~4 test files, 10-30 seconds total

### Performance Tests (`performance/`)

**Purpose:** Measure speed, memory, scalability

**Characteristics:**
- Run large simulations
- Benchmark comparisons
- Track regression
- Can be slow (30+ seconds)

**Files:**
- `test_performance.py` - Throughput benchmarks

**Running:** ~1 test file, 30+ seconds

---

## ✅ Current Status

**All tests passing:** 19/19 ✅

**Recent additions (2026-01-04):**
- `unit/test_bidder_models.py` (11 tests) - Model predictions and coefficients
- `integration/test_model_integration.py` (8 tests) - Models in simulation

**Test results:**
- OLSa_v2 vs Random: 92% win rate
- Make-bid rate: 53%
- No crashes on 50 edge case seeds

---

## 📝 Writing New Tests

### 1. Choose Test Type

| Test Type | When to Use |
|-----------|-------------|
| **Unit** | Testing single function/class |
| **Integration** | Testing workflows, multiple components |
| **Performance** | Measuring speed/memory |

### 2. Follow Naming Convention

```python
# tests/unit/test_my_feature.py
"""Tests for my_feature module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from bid_euchre.my_module import my_function

def test_specific_behavior():
    """Test that X does Y when Z."""
    # Arrange
    input_data = ...

    # Act
    result = my_function(input_data)

    # Assert
    assert result == expected, f"Expected {expected}, got {result}"

if __name__ == "__main__":
    test_specific_behavior()
    print("✅ All tests passed")
```

### 3. Keep Tests Fast

**Guidelines:**
- Unit tests: < 1 second each
- Integration tests: < 30 seconds each
- Use minimal datasets (10-100 hands)
- Mock expensive operations when possible

### 4. Make Tests Deterministic

```python
# ✅ Good - fixed seed
result = play_single_hand(deal_seed=42)

# ❌ Bad - random results
result = play_single_hand()  # Random seed = flaky test
```

---

## 🎯 Test Standards

### Before Committing
- [ ] All existing tests pass
- [ ] New features have unit tests (in `unit/`)
- [ ] New workflows have integration tests (in `integration/`)
- [ ] Tests are deterministic (use seeds)
- [ ] Tests have descriptive docstrings

### For New Models
- [ ] Unit tests for predictions (`test_<model_name>_predictions()`)
- [ ] Unit tests for coefficients (`test_<model_name>_coefficients()`)
- [ ] Integration test in simulation (`test_<model_name>_plays_hands()`)
- [ ] Integration test for make-bid rate
- [ ] No crashes on edge cases (test 50+ random seeds)

### For New Strategies
- [ ] Unit test for decide_bid() method
- [ ] Unit test for decide_play() method
- [ ] Integration test: complete 10 hands
- [ ] Integration test vs baseline strategy

---

## 🐛 Debugging Failed Tests

### Test fails locally
```bash
# Run with verbose output
PYTHONPATH=src python -m pytest tests/unit/test_my_feature.py -v

# Run specific test function
PYTHONPATH=src python -m pytest tests/unit/test_my_feature.py::test_specific_case -v
```

### Test passes locally but fails in CI
- Check for hardcoded paths (use relative paths)
- Check for missing dependencies
- Check for non-deterministic behavior (seeds!)

---

## 📊 Test Coverage Goals

**Current coverage:** ~19 tests across 14 files

**Target coverage:**
- Core modules (cards, rules): ✅ Good
- Strategies: ✅ Good
- Models: ✅ Good (after 2026-01-04 addition)
- Simulation: ✅ Good
- Logging: ⚠️ Could improve
- Reporting: ⚠️ Could improve

**Priority for expansion:**
- [ ] Tests for `logging/game_logger.py`
- [ ] Tests for `reporting/` modules
- [ ] Tests for `features/hand_eval.py` edge cases

---

## 🔧 Utility Functions

### Running All Tests with Summary
```bash
# Use scripts/run_tests.py
python scripts/run_tests.py
```

### Running Specific Category
```bash
# Just unit tests
PYTHONPATH=src python -m pytest tests/unit/

# Just integration
PYTHONPATH=src python -m pytest tests/integration/
```

---

## Questions?

- Test standards: See `docs/CONTRIBUTING.md`
- Adding new experiments: See `experiments/README.md`
- Anti-patterns: See `docs/ANTI_PATTERNS.md`
