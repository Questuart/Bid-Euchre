"""
Unit tests for points-based scoring in Bid Euchre.

Tests the compute_points() function with exact integer results.
"""

from bid_euchre.scoring import compute_points


class TestComputePoints:
    """Test compute_points() function with exact test cases."""

    def test_no_bid_case(self):
        """Test case with no bidding: both teams get their tricks."""
        points_team0, points_team1 = compute_points(None, None, 6, 4)
        assert points_team0 == 6
        assert points_team1 == 4
        assert isinstance(points_team0, int)
        assert isinstance(points_team1, int)

    def test_team0_makes_bid(self):
        """Test case where team 0 makes their bid."""
        points_team0, points_team1 = compute_points(6, 0, 8, 2)
        assert points_team0 == 8
        assert points_team1 == 2
        assert isinstance(points_team0, int)
        assert isinstance(points_team1, int)

    def test_team0_gets_set(self):
        """Test case where team 0 gets set."""
        points_team0, points_team1 = compute_points(6, 2, 5, 5)
        assert points_team0 == -6
        assert points_team1 == 5
        assert isinstance(points_team0, int)
        assert isinstance(points_team1, int)

    def test_team1_makes_bid(self):
        """Test case where team 1 makes their bid."""
        points_team0, points_team1 = compute_points(7, 1, 3, 7)
        assert points_team0 == 3
        assert points_team1 == 7
        assert isinstance(points_team0, int)
        assert isinstance(points_team1, int)

    def test_team1_gets_set(self):
        """Test case where team 1 gets set."""
        points_team0, points_team1 = compute_points(8, 3, 6, 4)
        assert points_team0 == 6
        assert points_team1 == -8
        assert isinstance(points_team0, int)
        assert isinstance(points_team1, int)

    def test_no_bidder_position_none(self):
        """Test case with winning_bid but bidder_position None (should treat as no bid)."""
        points_team0, points_team1 = compute_points(6, None, 8, 2)
        assert points_team0 == 8
        assert points_team1 == 2

    def test_winning_bid_none_with_bidder(self):
        """Test case with bidder_position but winning_bid None (should treat as no bid)."""
        points_team0, points_team1 = compute_points(None, 0, 8, 2)
        assert points_team0 == 8
        assert points_team1 == 2

    def test_edge_case_minimum_bid(self):
        """Test edge case with minimum bid of 6."""
        # Team 0 makes minimum bid
        points_team0, points_team1 = compute_points(6, 0, 6, 4)
        assert points_team0 == 6
        assert points_team1 == 4

        # Team 0 gets set on minimum bid
        points_team0, points_team1 = compute_points(6, 2, 5, 5)
        assert points_team0 == -6
        assert points_team1 == 5

    def test_edge_case_maximum_tricks(self):
        """Test edge case with maximum tricks (10 total)."""
        # Team 0 makes bid with 10 tricks
        points_team0, points_team1 = compute_points(6, 0, 10, 0)
        assert points_team0 == 10
        assert points_team1 == 0

        # No bid case with 10 tricks
        points_team0, points_team1 = compute_points(None, None, 10, 0)
        assert points_team0 == 10
        assert points_team1 == 0
