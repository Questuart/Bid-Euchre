from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy


def _assert_dist_shape(dist: dict[int, int], n: int) -> None:
    assert set(dist.keys()) == set(range(0, 11)), f"Expected keys 0..10, got {sorted(dist.keys())}"
    assert sum(dist.values()) == n, f"Distribution counts must sum to n={n}, got {sum(dist.values())}"
    assert all(isinstance(v, int) for v in dist.values()), "Distribution values must be ints"
    assert all(v >= 0 for v in dist.values()), "Distribution values must be non-negative"


def test_golden_seeds_smoke():
    """
    Golden test: lock simulator behavior for fixed deal seeds.

    Uses AlwaysHighestLegalStrategy for determinism (no strategy RNG).
    Covers suit (H, D), high, low.

    If this fails, simulator behavior changed:
    - bug introduced (fix), OR
    - intentional change (update expected values with explanation in PR).
    """
    test_cases = [
        {
            "deal_seed": 42,
            "contract_type": "suit",
            "trump_suit": "H",
            "n_hands": 50,
            "expected_dist": {0: 4, 1: 3, 2: 3, 3: 9, 4: 4, 5: 4, 6: 6, 7: 4, 8: 5, 9: 7, 10: 1},
        },
        {
            "deal_seed": 100,
            "contract_type": "suit",
            "trump_suit": "D",
            "n_hands": 50,
            "expected_dist": {0: 6, 1: 2, 2: 4, 3: 2, 4: 9, 5: 5, 6: 6, 7: 6, 8: 3, 9: 4, 10: 3},
        },
        {
            "deal_seed": 200,
            "contract_type": "high",
            "trump_suit": None,
            "n_hands": 50,
            "expected_dist": {0: 6, 1: 0, 2: 4, 3: 3, 4: 8, 5: 10, 6: 7, 7: 3, 8: 4, 9: 4, 10: 1},
        },
        {
            "deal_seed": 300,
            "contract_type": "low",
            "trump_suit": None,
            "n_hands": 50,
            "expected_dist": {0: 4, 1: 4, 2: 4, 3: 3, 4: 8, 5: 8, 6: 5, 7: 4, 8: 1, 9: 3, 10: 6},
        },
    ]

    for tc in test_cases:
        # Avoid reusing a strategy instance across cases (prevents accidental state coupling)
        r1 = simulate_many_hands(
            n=tc["n_hands"],
            contract_type=tc["contract_type"],
            trump_suit=tc["trump_suit"],
            deal_seed=tc["deal_seed"],
            strategy=AlwaysHighestLegalStrategy(),
        )

        r2 = simulate_many_hands(
            n=tc["n_hands"],
            contract_type=tc["contract_type"],
            trump_suit=tc["trump_suit"],
            deal_seed=tc["deal_seed"],
            strategy=AlwaysHighestLegalStrategy(),
        )

        # Basic run sanity
        assert r1["hands"] == tc["n_hands"]
        assert r1["player_samples"] == 4 * tc["n_hands"]
        assert r1["contract_type"] == tc["contract_type"]
        assert r1["trump_suit"] == tc["trump_suit"]

        _assert_dist_shape(r1["distribution_team0"], tc["n_hands"])
        _assert_dist_shape(r2["distribution_team0"], tc["n_hands"])

        # Determinism check (run twice)
        assert r1["distribution_team0"] == r2["distribution_team0"]

        # Golden check
        assert r1["distribution_team0"] == tc["expected_dist"], (
            f"Golden test FAILED for deal_seed={tc['deal_seed']}, "
            f"{tc['contract_type']}/{tc['trump_suit']}\n"
            f"  Expected: {tc['expected_dist']}\n"
            f"  Actual:   {r1['distribution_team0']}\n"
            f"This means simulator behavior changed. Review and update if intentional."
        )
