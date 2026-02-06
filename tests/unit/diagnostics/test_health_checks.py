"""Unit tests for health check computations.

Covers edge cases in compute_health_scorecard, particularly the
_check_hands_differ check with numpy array hand_cards values
(as produced by PyArrow's to_pandas()).
"""

import numpy as np
import pandas as pd

from bid_euchre.diagnostics.health_checks import compute_health_scorecard


def _make_bidless_df(hand_cards_values):
    """Build a minimal bidless DataFrame with the given hand_cards per seat.

    Creates one hand (hand_id=0) with 4 seats. Each seat gets one
    feat_hand_value and the provided hand_cards value.
    """
    rows = []
    for seat in range(4):
        rows.append({
            "hand_id": 0,
            "seat": seat,
            "hand_cards": hand_cards_values[seat],
            "feat_hand_value": float(seat + 1),
        })
    return pd.DataFrame(rows)


class TestCheckHandsDifferNumpyArrays:
    """Regression tests for _check_hands_differ with numpy array values."""

    def test_numpy_array_hand_cards_does_not_raise(self):
        """compute_health_scorecard should not raise when hand_cards are numpy arrays.

        PyArrow's to_pandas() converts pa.list_(pa.string()) to numpy arrays,
        not Python lists. The isinstance(x, list) guard would skip conversion,
        leaving unhashable arrays that crash nunique().
        """
        cards = [
            np.array(["AH", "KH", "QH", "JH", "10H", "AS", "KS", "QS", "JS", "10S"]),
            np.array(["AD", "KD", "QD", "JD", "10D", "AC", "KC", "QC", "JC", "10C"]),
            np.array(["AH", "KH", "AD", "KD", "QH", "QD", "JH", "JD", "10H", "10D"]),
            np.array(["AS", "KS", "AC", "KC", "QS", "QC", "JS", "JC", "10S", "10C"]),
        ]
        df = _make_bidless_df(cards)
        scorecard = compute_health_scorecard(df)

        # hands_differ check should pass (all 4 hands are distinct)
        hands_check = next(c for c in scorecard.checks if c.name == "hands_differ")
        assert hands_check.status == "PASS"

    def test_python_list_hand_cards_still_works(self):
        """Ensure the fix doesn't regress on Python list hand_cards."""
        cards = [
            ["AH", "KH", "QH", "JH", "10H", "AS", "KS", "QS", "JS", "10S"],
            ["AD", "KD", "QD", "JD", "10D", "AC", "KC", "QC", "JC", "10C"],
            ["AH", "KH", "AD", "KD", "QH", "QD", "JH", "JD", "10H", "10D"],
            ["AS", "KS", "AC", "KC", "QS", "QC", "JS", "JC", "10S", "10C"],
        ]
        df = _make_bidless_df(cards)
        scorecard = compute_health_scorecard(df)

        hands_check = next(c for c in scorecard.checks if c.name == "hands_differ")
        assert hands_check.status == "PASS"

    def test_identical_numpy_hands_detected(self):
        """Identical numpy array hands across seats should trigger FAIL."""
        same_hand = np.array(["AH", "KH", "QH", "JH", "10H", "AS", "KS", "QS", "JS", "10S"])
        cards = [same_hand.copy() for _ in range(4)]
        df = _make_bidless_df(cards)
        scorecard = compute_health_scorecard(df)

        hands_check = next(c for c in scorecard.checks if c.name == "hands_differ")
        assert hands_check.status == "FAIL"
