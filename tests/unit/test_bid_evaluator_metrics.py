import math

from bid_euchre.reporting.evaluator import compute_cvar, compute_downside_variance


def test_compute_cvar_worst_percentile():
    values = [10, 5, 0, -5, -10, 20]
    # len=6 -> tail_size = ceil(6*0.05)=1, so CVaR is worst value.
    assert compute_cvar(values) == -10


def test_compute_cvar_multiple_tail_items():
    values = list(range(-10, 30))  # 40 values
    tail_size = math.ceil(len(values) * 0.05)
    assert tail_size == 2
    expected = sum(sorted(values)[:tail_size]) / tail_size
    assert math.isclose(compute_cvar(values), expected)


def test_downside_variance_definition():
    values = [5, -1, -3, -5, 2]
    expected = ((-1 + 3) ** 2 + (-3 + 3) ** 2 + (-5 + 3) ** 2) / 3
    assert math.isclose(compute_downside_variance(values), expected)


def test_downside_variance_no_negatives():
    assert compute_downside_variance([1, 2, 3]) is None
