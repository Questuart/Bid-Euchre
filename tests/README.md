# Bid Euchre Tests

This directory contains comprehensive tests for the Bid Euchre simulation project.

## Test Categories

### Unit Tests
- **test_cards.py**: Core card operations, deck creation, bower logic, rank strength
- **test_rules.py**: Trick winner determination, bower precedence, suit following
- **test_strategy.py**: AI strategy validation, card selection logic, valuation functions

### Validation Tests
- **test_simulation_validation.py**: Statistical properties, data format validation, edge cases
- **test_integration.py**: End-to-end workflows, experiment scripts, error handling
- **test_performance.py**: Performance regression tests, scalability validation

## Running Tests

### Quick Test Run
```bash
# Run all tests
python scripts/run_tests.py

# Run with coverage
python scripts/run_tests.py --coverage

# Run specific test categories
python scripts/run_tests.py --unit
python scripts/run_tests.py --integration
python scripts/run_tests.py --performance

# Quick validation (no pytest required)
python scripts/validate_tests.py
```

### Using pytest Directly
```bash
# Run all tests with coverage
PYTHONPATH=src pytest --cov=src/bid_euchre --cov-report=term-missing

# Run specific test file
PYTHONPATH=src pytest tests/test_cards.py -v

# Run tests matching pattern
PYTHONPATH=src pytest -k "test_trick_winner" -v
```

## Test Coverage Goals

- **Unit Tests**: 90%+ coverage of core functionality
- **Integration Tests**: End-to-end workflow validation
- **Performance Tests**: Regression detection and scalability validation

## Adding New Tests

1. Create test files following the naming pattern `test_*.py`
2. Use descriptive test method names: `test_[feature]_[condition]_[expected_result]`
3. Include docstrings explaining what each test validates
4. Add appropriate pytest markers for slow/statistical tests

## Continuous Integration

These tests are designed to run in CI environments and provide confidence that:
- Core game logic is correct
- Simulations produce statistically reasonable results
- Performance doesn't regress
- Code changes don't break existing functionality
