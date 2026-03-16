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

    def test_regular_bid_type_default(self):
        """Regular bid_type (default) leaves existing logic unchanged."""
        # Explicit "regular" should match default
        p0, p1 = compute_points(6, 0, 8, 2, bid_type="regular")
        assert p0 == 8
        assert p1 == 2

        p0, p1 = compute_points(6, 2, 5, 5, bid_type="regular")
        assert p0 == -6
        assert p1 == 5


class TestMoonScoring:
    """Tests for moon bid scoring (bid_type='moon')."""

    def test_moon_make_team0(self):
        """Moon make: team 0 declares and wins all 10 tricks -> +20."""
        p0, p1 = compute_points(10, 0, 10, 0, bid_type="moon")
        assert p0 == 20
        assert p1 == 0

    def test_moon_make_team1(self):
        """Moon make: team 1 declares and wins all 10 tricks -> +20."""
        p0, p1 = compute_points(10, 1, 0, 10, bid_type="moon")
        assert p0 == 0
        assert p1 == 20

    def test_moon_fail_team0(self):
        """Moon fail: team 0 declares but doesn't win all 10 -> -20."""
        p0, p1 = compute_points(10, 0, 9, 1, bid_type="moon")
        assert p0 == -20
        assert p1 == 1

    def test_moon_fail_team1(self):
        """Moon fail: team 1 declares but doesn't win all 10 -> -20."""
        p0, p1 = compute_points(10, 3, 3, 7, bid_type="moon")
        assert p0 == 3
        assert p1 == -20

    def test_moon_fail_defending_gets_tricks(self):
        """Moon fail: defending team always gets their tricks won."""
        p0, p1 = compute_points(10, 2, 5, 5, bid_type="moon")
        assert p0 == -20
        assert p1 == 5

    def test_moon_make_defending_zero_tricks(self):
        """Moon make: defending team gets 0 tricks (since declaring won all 10)."""
        p0, p1 = compute_points(10, 0, 10, 0, bid_type="moon")
        assert p0 == 20
        assert p1 == 0

    def test_moon_bidder_seat2(self):
        """Moon with bidder on seat 2 (team 0)."""
        p0, p1 = compute_points(10, 2, 10, 0, bid_type="moon")
        assert p0 == 20
        assert p1 == 0

    def test_moon_bidder_seat3(self):
        """Moon with bidder on seat 3 (team 1)."""
        p0, p1 = compute_points(10, 3, 2, 8, bid_type="moon")
        assert p0 == 2
        assert p1 == -20


class TestLonerScoring:
    """Tests for loner bid scoring (bid_type='loner')."""

    def test_loner_make_team0(self):
        """Loner make: team 0 declares and wins all 10 tricks -> +40."""
        p0, p1 = compute_points(10, 0, 10, 0, bid_type="loner")
        assert p0 == 40
        assert p1 == 0

    def test_loner_make_team1(self):
        """Loner make: team 1 declares and wins all 10 tricks -> +40."""
        p0, p1 = compute_points(10, 1, 0, 10, bid_type="loner")
        assert p0 == 0
        assert p1 == 40

    def test_loner_fail_team0(self):
        """Loner fail: team 0 declares but doesn't win all 10 -> -40."""
        p0, p1 = compute_points(10, 0, 9, 1, bid_type="loner")
        assert p0 == -40
        assert p1 == 1

    def test_loner_fail_team1(self):
        """Loner fail: team 1 declares but doesn't win all 10 -> -40."""
        p0, p1 = compute_points(10, 3, 4, 6, bid_type="loner")
        assert p0 == 4
        assert p1 == -40

    def test_loner_fail_defending_gets_tricks(self):
        """Loner fail: defending team always gets their tricks won."""
        p0, p1 = compute_points(10, 2, 5, 5, bid_type="loner")
        assert p0 == -40
        assert p1 == 5

    def test_loner_make_defending_zero_tricks(self):
        """Loner make: defending team gets 0 tricks."""
        p0, p1 = compute_points(10, 1, 0, 10, bid_type="loner")
        assert p0 == 0
        assert p1 == 40

    def test_loner_bidder_seat2(self):
        """Loner with bidder on seat 2 (team 0)."""
        p0, p1 = compute_points(10, 2, 10, 0, bid_type="loner")
        assert p0 == 40
        assert p1 == 0

    def test_loner_bidder_seat3(self):
        """Loner with bidder on seat 3 (team 1)."""
        p0, p1 = compute_points(10, 3, 3, 7, bid_type="loner")
        assert p0 == 3
        assert p1 == -40
