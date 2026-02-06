"""Test _check_hands_differ handles numpy arrays from PyArrow deserialization."""

import numpy as np
import pandas as pd

from bid_euchre.diagnostics.health_checks import _check_hands_differ


def test_check_hands_differ_with_numpy_arrays():
    """_check_hands_differ must handle numpy arrays (from PyArrow), not just lists."""
    df = pd.DataFrame({
        "hand_id": [1, 1, 1, 1],
        "seat": [0, 1, 2, 3],
        "hand_cards": [
            np.array(["10H", "JH", "QH", "KH", "AH", "10S", "JS", "QS", "KS", "AS"]),
            np.array(["10D", "JD", "QD", "KD", "AD", "10C", "JC", "QC", "KC", "AC"]),
            np.array(["10H", "JH", "QH", "KH", "AH", "10D", "JD", "QD", "KD", "AD"]),
            np.array(["10S", "JS", "QS", "KS", "AS", "10C", "JC", "QC", "KC", "AC"]),
        ],
    })
    result = _check_hands_differ(df)
    assert result.status == "PASS"
    assert result.name == "hands_differ"


def test_check_hands_differ_with_python_lists():
    """_check_hands_differ also works with plain Python lists."""
    df = pd.DataFrame({
        "hand_id": [1, 1],
        "seat": [0, 1],
        "hand_cards": [
            ["10H", "JH", "QH"],
            ["10D", "JD", "QD"],
        ],
    })
    result = _check_hands_differ(df)
    assert result.status == "PASS"


def test_check_hands_differ_detects_identical():
    """Identical hand_cards across seats should FAIL."""
    same_hand = np.array(["10H", "JH", "QH", "KH", "AH"])
    df = pd.DataFrame({
        "hand_id": [1, 1],
        "seat": [0, 1],
        "hand_cards": [same_hand, same_hand.copy()],
    })
    result = _check_hands_differ(df)
    assert result.status == "FAIL"
