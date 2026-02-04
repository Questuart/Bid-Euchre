"""
Unit tests for weighted win rate formula.

The weighted win rate formula treats ties as half-wins:
  win_rate = (count(tricks >= 6) + 0.5 × count(tricks == 5)) / total_hands

This ensures that both teams' win rates sum to 1.0.
"""

import pytest

from bid_euchre.reporting.metrics import compute_outcome_stats


class TestWeightedWinRate:
    """Tests for weighted win rate calculation in compute_outcome_stats."""

    def test_all_wins_returns_one(self):
        """10 games with 7 tricks each → win_rate = 1.0."""
        trick_counts = [7] * 10
        stats = compute_outcome_stats(trick_counts)
        assert stats.win_rate == pytest.approx(1.0)
        assert stats.n_wins == 10
        assert stats.n_pushes == 0
        assert stats.n_losses == 0

    def test_all_ties_returns_half(self):
        """10 games with 5 tricks each → win_rate = 0.5."""
        trick_counts = [5] * 10
        stats = compute_outcome_stats(trick_counts)
        assert stats.win_rate == pytest.approx(0.5)
        assert stats.n_wins == 0
        assert stats.n_pushes == 10
        assert stats.n_losses == 0

    def test_all_losses_returns_zero(self):
        """10 games with 3 tricks each → win_rate = 0.0."""
        trick_counts = [3] * 10
        stats = compute_outcome_stats(trick_counts)
        assert stats.win_rate == pytest.approx(0.0)
        assert stats.n_wins == 0
        assert stats.n_pushes == 0
        assert stats.n_losses == 10

    def test_mixed_outcomes_weighted_correctly(self):
        """Mixed: 5 wins (≥6), 3 ties (=5), 2 losses (≤4) → win_rate = 0.65."""
        # 5 wins (tricks >= 6)
        wins = [6, 7, 8, 9, 10]
        # 3 ties (tricks == 5)
        ties = [5, 5, 5]
        # 2 losses (tricks <= 4)
        losses = [4, 3]

        trick_counts = wins + ties + losses
        stats = compute_outcome_stats(trick_counts)

        # Expected: (5 + 0.5 * 3) / 10 = (5 + 1.5) / 10 = 0.65
        assert stats.win_rate == pytest.approx(0.65)
        assert stats.n_wins == 5
        assert stats.n_pushes == 3
        assert stats.n_losses == 2

    def test_single_win(self):
        """Single win returns 1.0."""
        stats = compute_outcome_stats([7])
        assert stats.win_rate == pytest.approx(1.0)

    def test_single_tie(self):
        """Single tie returns 0.5."""
        stats = compute_outcome_stats([5])
        assert stats.win_rate == pytest.approx(0.5)

    def test_single_loss(self):
        """Single loss returns 0.0."""
        stats = compute_outcome_stats([3])
        assert stats.win_rate == pytest.approx(0.0)

    def test_empty_returns_zero(self):
        """Empty list returns 0.0."""
        stats = compute_outcome_stats([])
        assert stats.win_rate == 0.0
        assert stats.n_total == 0

    def test_exactly_six_tricks_is_win(self):
        """Exactly 6 tricks counts as a full win."""
        trick_counts = [6] * 10
        stats = compute_outcome_stats(trick_counts)
        assert stats.win_rate == pytest.approx(1.0)
        assert stats.n_wins == 10

    def test_exactly_four_tricks_is_loss(self):
        """Exactly 4 tricks counts as a full loss."""
        trick_counts = [4] * 10
        stats = compute_outcome_stats(trick_counts)
        assert stats.win_rate == pytest.approx(0.0)
        assert stats.n_losses == 10

    def test_win_rate_plus_loss_rate_equals_one_minus_half_push_rate(self):
        """Verify the mathematical relationship between rates.

        Since ties count as 0.5 for both teams:
        win_rate = n_wins/n + 0.5 * n_pushes/n
        loss_rate_other = n_losses/n + 0.5 * n_pushes/n

        So win_rate + loss_rate_other = n_wins/n + n_losses/n + n_pushes/n = 1.0
        """
        # Mixed data
        trick_counts = [7, 7, 5, 5, 3, 3]  # 2 wins, 2 ties, 2 losses
        stats = compute_outcome_stats(trick_counts)

        # Team 0's weighted win rate + Team 1's weighted win rate should = 1.0
        # For team 0: (2 wins + 0.5 * 2 ties) / 6 = 3/6 = 0.5
        # For team 1: (2 wins + 0.5 * 2 ties) / 6 = 3/6 = 0.5
        # Total: 0.5 + 0.5 = 1.0

        # We compute team 0's win rate
        team0_win_rate = stats.win_rate

        # Team 1's win rate is: (losses + 0.5 * ties) / n
        team1_win_rate = (stats.n_losses + 0.5 * stats.n_pushes) / stats.n_total

        assert team0_win_rate + team1_win_rate == pytest.approx(1.0)

    def test_boundary_tricks_values(self):
        """Test all boundary trick values."""
        # 0 tricks - loss
        stats = compute_outcome_stats([0])
        assert stats.win_rate == pytest.approx(0.0)

        # 10 tricks - win
        stats = compute_outcome_stats([10])
        assert stats.win_rate == pytest.approx(1.0)

    def test_confidence_interval_for_weighted_wins(self):
        """Confidence intervals should be reasonable for weighted wins."""
        # 50 wins + 50 ties = effective 75 weighted wins out of 100
        trick_counts = [7] * 50 + [5] * 50
        stats = compute_outcome_stats(trick_counts)

        # win_rate should be (50 + 0.5 * 50) / 100 = 0.75
        assert stats.win_rate == pytest.approx(0.75)

        # CI should bracket the point estimate
        assert stats.win_ci[0] < stats.win_rate
        assert stats.win_ci[1] > stats.win_rate

        # CI should be reasonably tight with n=100
        ci_width = stats.win_ci[1] - stats.win_ci[0]
        assert ci_width < 0.2  # Sanity check
