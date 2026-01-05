#!/usr/bin/env python3
"""
Simple test validation script that runs without pytest.

This script validates the key fixes made to the test suite.
"""

import sys
import os

# Add src to path (scripts directory is at root level)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def test_card_valuation():
    """Test that card valuation works correctly."""
    print("🃏 Testing card valuation...")

    from bid_euchre.strategy.strategy import _card_value_for_dump
    from bid_euchre.core.cards import Card

    # Test the bower hierarchy
    regular_trump = _card_value_for_dump(Card("S", "A"), "suit", "S")  # 14
    left_bower = _card_value_for_dump(Card("D", "J"), "suit", "H")    # 15
    right_bower = _card_value_for_dump(Card("H", "J"), "suit", "H")   # 16

    assert right_bower > left_bower > regular_trump, \
        f"Bower hierarchy failed: {right_bower} > {left_bower} > {regular_trump}"

    print(f"  ✅ Regular trump: {regular_trump}")
    print(f"  ✅ Left bower: {left_bower}")
    print(f"  ✅ Right bower: {right_bower}")
    return True

def test_feature_buckets():
    """Test that feature buckets are correct."""
    print("📊 Testing feature buckets...")

    from bid_euchre.sim import simulation

    result = simulation.simulate_many_hands(500, "suit", "H")
    features = set(result["feature_buckets_player0"].keys())
    expected = {"bowers", "trump_count", "offsuit_aces", "high_offsuit", "rank_sum"}

    assert features == expected, f"Feature mismatch: {features} != {expected}"

    print(f"  ✅ Features: {sorted(features)}")
    return True

def test_contract_differences():
    """Test that different contracts produce different results."""
    print("🎲 Testing contract differences...")

    from bid_euchre.sim import simulation

    suit_result = simulation.simulate_many_hands(500, "suit", "H")
    high_result = simulation.simulate_many_hands(500, "high", None)

    suit_avg = suit_result["avg_team0"]
    high_avg = high_result["avg_team0"]
    difference = abs(suit_avg - high_avg)

    assert difference > 0.01, f"Contract difference too small: {difference:.3f}"

    print(f"  ✅ Suit contract avg: {suit_avg:.3f}")
    print(f"  ✅ High contract avg: {high_avg:.3f}")
    return True

def test_strategy_framework():
    """Test that the strategy framework works."""
    print("🤖 Testing strategy framework...")

    from bid_euchre.strategy import BasicStrategy, GreedyStrategy
    from bid_euchre.sim import simulation

    # Test strategy creation
    basic = BasicStrategy("test_basic")
    greedy = GreedyStrategy("test_greedy")

    assert str(basic) == "BasicStrategy(test_basic)"
    assert str(greedy) == "GreedyStrategy(test_greedy)"

    # Test strategy in simulation
    result = simulation.simulate_many_hands(100, "suit", "H", strategy=greedy)
    assert result["hands"] == 100
    assert "avg_team0" in result

    print(f"  ✅ Basic strategy: {basic}")
    print(f"  ✅ Greedy strategy: {greedy}")
    print(f"  ✅ Simulation result: {result['hands']} hands, avg_team0={result['avg_team0']:.2f}")
    return True

def test_cli_interface():
    """Test that CLI interface works."""
    print("💻 Testing CLI interface...")

    import subprocess
    import tempfile

    # Test run_baseline_greedy.py
    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = [
            sys.executable,
            "experiments/run_baseline_greedy.py",
            "--n_per", "50",
            "--seed", "42",
            "--run-dir", temp_dir,
            "--log-level", "hand",
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Check that a run folder was created and contains expected artifacts
        import glob
        run_folders = [p for p in glob.glob(os.path.join(temp_dir, "baseline_greedy_*")) if os.path.isdir(p)]
        assert len(run_folders) >= 1, "Expected at least one run folder in run-dir"

        run_folder = sorted(run_folders)[-1]
        results_dir = os.path.join(run_folder, "results", "greedy")
        json_files = glob.glob(os.path.join(results_dir, "*.json"))
        assert len(json_files) == 6, f"Expected 6 scenario JSON files, got {len(json_files)}"

        logs_dir = os.path.join(run_folder, "logs")
        jsonl_files = glob.glob(os.path.join(logs_dir, "*.jsonl"))
        assert len(jsonl_files) >= 1, "Expected at least one JSONL log file"

        print("  ✅ CLI executed successfully")
        print(f"  ✅ Generated {len(json_files)} scenario files")
        print(f"  ✅ Generated {len(jsonl_files)} log files")

    return True

def main():
    """Run all validation tests."""
    print("🧪 Bid Euchre Test Validation")
    print("=" * 50)

    tests = [
        ("Card Valuation", test_card_valuation),
        ("Feature Buckets", test_feature_buckets),
        ("Contract Differences", test_contract_differences),
        ("Strategy Framework", test_strategy_framework),
        ("CLI Interface", test_cli_interface),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED\n")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED\n")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}\n")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests PASSED! The fixes are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
