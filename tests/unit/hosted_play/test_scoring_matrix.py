"""Exhaustive scoring test matrix for hosted-play bid/outcome combinations.

Covers all bid_type x contract_type x outcome x bidder_seat combinations to
verify that compute_points() produces correct results and the hand_result
template renders matching display text.

Ref: issue #1918
"""

from __future__ import annotations

import os
from typing import Any

import jinja2
import pytest

from bid_euchre.scoring import compute_points
from web.template_filters import display_rank

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "templates",
)


@pytest.fixture()
def env():
    """Jinja2 environment for rendering hand_result.html."""
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    environment.filters["display_rank"] = display_rank
    return environment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Seats on team 0: {0, 2}, team 1: {1, 3}
ALL_SEATS = [0, 1, 2, 3]
CONTRACT_TYPES = ["suit", "high", "low"]
SUITS = ["S", "H", "D", "C"]


def _team_for(seat: int) -> int:
    """Return 0 for seats 0/2, 1 for seats 1/3."""
    return 0 if seat in (0, 2) else 1


def _tricks_split(
    bidder_seat: int,
    declarer_tricks: int,
) -> tuple[int, int]:
    """Return (tricks_team0, tricks_team1) given bidder seat and declarer tricks."""
    defender_tricks = 10 - declarer_tricks
    if _team_for(bidder_seat) == 0:
        return declarer_tricks, defender_tricks
    return defender_tricks, declarer_tricks


# ---------------------------------------------------------------------------
# 1. compute_points — Regular bid matrix
# ---------------------------------------------------------------------------


class TestRegularBidMatrix:
    """All bidder_seat x outcome combinations for regular bids."""

    # (bid_amount, declarer_tricks, label)
    OUTCOMES = [
        (6, 6, "make_exact"),
        (6, 8, "make_over"),
        (6, 10, "make_sweep"),
        (6, 5, "set_by_1"),
        (8, 3, "set_by_many"),
        (7, 7, "make_exact_7"),
        (10, 10, "make_10"),
        (10, 9, "set_10"),
    ]

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize(
        "bid_amount,declarer_tricks,label",
        OUTCOMES,
        ids=[o[2] for o in OUTCOMES],
    )
    def test_regular_scoring(
        self,
        bidder_seat: int,
        bid_amount: int,
        declarer_tricks: int,
        label: str,
    ) -> None:
        tricks0, tricks1 = _tricks_split(bidder_seat, declarer_tricks)
        p0, p1 = compute_points(
            bid_amount, bidder_seat, tricks0, tricks1, bid_type="regular"
        )

        bid_team = _team_for(bidder_seat)
        bid_team_tricks = tricks0 if bid_team == 0 else tricks1
        non_bid_tricks = tricks1 if bid_team == 0 else tricks0

        if bid_team_tricks >= bid_amount:
            # Made — both teams get their tricks
            expected_bid_pts = bid_team_tricks
            expected_def_pts = non_bid_tricks
        else:
            # Set — bid team gets -bid, defenders get their tricks
            expected_bid_pts = -bid_amount
            expected_def_pts = non_bid_tricks

        if bid_team == 0:
            assert (
                p0 == expected_bid_pts
            ), f"team0 pts: {p0} != {expected_bid_pts} ({label})"
            assert (
                p1 == expected_def_pts
            ), f"team1 pts: {p1} != {expected_def_pts} ({label})"
        else:
            assert (
                p0 == expected_def_pts
            ), f"team0 pts: {p0} != {expected_def_pts} ({label})"
            assert (
                p1 == expected_bid_pts
            ), f"team1 pts: {p1} != {expected_bid_pts} ({label})"

        # Sanity: points are integers
        assert isinstance(p0, int)
        assert isinstance(p1, int)


# ---------------------------------------------------------------------------
# 2. compute_points — Moon bid matrix
# ---------------------------------------------------------------------------


class TestMoonBidMatrix:
    """All bidder_seat x outcome combinations for moon bids."""

    # (declarer_tricks, label)
    OUTCOMES = [
        (10, "moon_made"),
        (9, "moon_set_by_1"),
        (5, "moon_set_by_5"),
        (0, "moon_set_all"),
    ]

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize(
        "declarer_tricks,label",
        OUTCOMES,
        ids=[o[1] for o in OUTCOMES],
    )
    def test_moon_scoring(
        self,
        bidder_seat: int,
        declarer_tricks: int,
        label: str,
    ) -> None:
        tricks0, tricks1 = _tricks_split(bidder_seat, declarer_tricks)
        p0, p1 = compute_points(10, bidder_seat, tricks0, tricks1, bid_type="moon")

        bid_team = _team_for(bidder_seat)
        non_bid_tricks = tricks1 if bid_team == 0 else tricks0

        if declarer_tricks == 10:
            expected_bid_pts = 20
        else:
            expected_bid_pts = -20
        expected_def_pts = non_bid_tricks

        if bid_team == 0:
            assert (
                p0 == expected_bid_pts
            ), f"team0: {p0} != {expected_bid_pts} ({label})"
            assert (
                p1 == expected_def_pts
            ), f"team1: {p1} != {expected_def_pts} ({label})"
        else:
            assert (
                p0 == expected_def_pts
            ), f"team0: {p0} != {expected_def_pts} ({label})"
            assert (
                p1 == expected_bid_pts
            ), f"team1: {p1} != {expected_bid_pts} ({label})"

        assert isinstance(p0, int)
        assert isinstance(p1, int)


# ---------------------------------------------------------------------------
# 3. compute_points — Loner bid matrix
# ---------------------------------------------------------------------------


class TestLonerBidMatrix:
    """All bidder_seat x outcome combinations for loner bids."""

    OUTCOMES = [
        (10, "loner_made"),
        (9, "loner_set_by_1"),
        (5, "loner_set_by_5"),
        (0, "loner_set_all"),
    ]

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize(
        "declarer_tricks,label",
        OUTCOMES,
        ids=[o[1] for o in OUTCOMES],
    )
    def test_loner_scoring(
        self,
        bidder_seat: int,
        declarer_tricks: int,
        label: str,
    ) -> None:
        tricks0, tricks1 = _tricks_split(bidder_seat, declarer_tricks)
        p0, p1 = compute_points(10, bidder_seat, tricks0, tricks1, bid_type="loner")

        bid_team = _team_for(bidder_seat)
        non_bid_tricks = tricks1 if bid_team == 0 else tricks0

        if declarer_tricks == 10:
            expected_bid_pts = 40
        else:
            expected_bid_pts = -40
        expected_def_pts = non_bid_tricks

        if bid_team == 0:
            assert (
                p0 == expected_bid_pts
            ), f"team0: {p0} != {expected_bid_pts} ({label})"
            assert (
                p1 == expected_def_pts
            ), f"team1: {p1} != {expected_def_pts} ({label})"
        else:
            assert (
                p0 == expected_def_pts
            ), f"team0: {p0} != {expected_def_pts} ({label})"
            assert (
                p1 == expected_bid_pts
            ), f"team1: {p1} != {expected_bid_pts} ({label})"

        assert isinstance(p0, int)
        assert isinstance(p1, int)


# ---------------------------------------------------------------------------
# 4. Template rendering — hand_result display matrix
# ---------------------------------------------------------------------------


def _make_hand_result_context(
    *,
    bidder_seat: int,
    bid_type: str,
    contract_type: str,
    trump: str | None,
    winning_bid: int,
    declarer_tricks: int,
) -> dict[str, Any]:
    """Build template context for hand_result.html."""
    tricks0, tricks1 = _tricks_split(bidder_seat, declarer_tricks)
    p0, p1 = compute_points(
        winning_bid, bidder_seat, tricks0, tricks1, bid_type=bid_type
    )
    return {
        "winning_bid": winning_bid,
        "bidder_seat": bidder_seat,
        "contract_type": contract_type,
        "trump": trump,
        "bid_type": bid_type,
        "tricks_team0": tricks0,
        "tricks_team1": tricks1,
        "points_team0": p0,
        "points_team1": p1,
        "score_human": p0,
        "score_ai": p1,
        "hands_played": 1,
        "link_uuid": "test-uuid",
    }


class TestHandResultDisplay:
    """Verify hand_result.html renders correct banners and points for all combos."""

    DISPLAY_CASES: list[tuple[str, str, str | None, int, int, str]] = []

    # Regular bids: each contract_type, make and set
    for ct in CONTRACT_TYPES:
        trump = "S" if ct == "suit" else None
        DISPLAY_CASES.append(
            (
                "regular",
                ct,
                trump,
                6,
                7,
                "Made it!",
            )
        )
        DISPLAY_CASES.append(
            (
                "regular",
                ct,
                trump,
                6,
                5,
                "Set!",
            )
        )

    # Moon: each contract_type, make and set
    for ct in CONTRACT_TYPES:
        trump = "H" if ct == "suit" else None
        DISPLAY_CASES.append(
            (
                "moon",
                ct,
                trump,
                10,
                10,
                "Moon Made!",
            )
        )
        DISPLAY_CASES.append(
            (
                "moon",
                ct,
                trump,
                10,
                8,
                "Moon Set!",
            )
        )

    # Loner: each contract_type, make and set
    for ct in CONTRACT_TYPES:
        trump = "D" if ct == "suit" else None
        DISPLAY_CASES.append(
            (
                "loner",
                ct,
                trump,
                10,
                10,
                "Loner Made!",
            )
        )
        DISPLAY_CASES.append(
            (
                "loner",
                ct,
                trump,
                10,
                7,
                "Loner Set!",
            )
        )

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize(
        "bid_type,contract_type,trump,winning_bid,declarer_tricks,expected_banner",
        DISPLAY_CASES,
        ids=[
            f"{c[0]}-{c[1]}-{'make' if c[4] >= c[3] else 'set'}" for c in DISPLAY_CASES
        ],
    )
    def test_banner_text(
        self,
        env: jinja2.Environment,
        bidder_seat: int,
        bid_type: str,
        contract_type: str,
        trump: str | None,
        winning_bid: int,
        declarer_tricks: int,
        expected_banner: str,
    ) -> None:
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type=bid_type,
            contract_type=contract_type,
            trump=trump,
            winning_bid=winning_bid,
            declarer_tricks=declarer_tricks,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        assert expected_banner in html, (
            f"Expected '{expected_banner}' in HTML for "
            f"seat={bidder_seat} {bid_type}/{contract_type}"
        )

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize(
        "bid_type,contract_type,trump,winning_bid,declarer_tricks,_banner",
        DISPLAY_CASES,
        ids=[
            f"{c[0]}-{c[1]}-{'make' if c[4] >= c[3] else 'set'}" for c in DISPLAY_CASES
        ],
    )
    def test_points_displayed(
        self,
        env: jinja2.Environment,
        bidder_seat: int,
        bid_type: str,
        contract_type: str,
        trump: str | None,
        winning_bid: int,
        declarer_tricks: int,
        _banner: str,
    ) -> None:
        """Points shown in the result table match compute_points output."""
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type=bid_type,
            contract_type=contract_type,
            trump=trump,
            winning_bid=winning_bid,
            declarer_tricks=declarer_tricks,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)

        p0 = ctx["points_team0"]
        p1 = ctx["points_team1"]

        # Points should appear in the scoring table
        p0_str = f"+{p0}" if p0 > 0 else str(p0)
        p1_str = f"+{p1}" if p1 > 0 else str(p1)
        assert p0_str in html, f"Expected '{p0_str}' in HTML (team0 points)"
        assert p1_str in html, f"Expected '{p1_str}' in HTML (team1 points)"

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    @pytest.mark.parametrize("contract_type", CONTRACT_TYPES)
    def test_contract_type_displayed(
        self,
        env: jinja2.Environment,
        bidder_seat: int,
        contract_type: str,
    ) -> None:
        """Contract type label (suit symbol / High / Low) is rendered."""
        trump = "C" if contract_type == "suit" else None
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type="regular",
            contract_type=contract_type,
            trump=trump,
            winning_bid=6,
            declarer_tricks=7,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)

        if contract_type == "suit":
            assert "♣" in html, "Suit symbol expected for suit contract"
        elif contract_type == "high":
            assert "High" in html, "High label expected for high contract"
        elif contract_type == "low":
            assert "Low" in html, "Low label expected for low contract"


# ---------------------------------------------------------------------------
# 5. Seat label display in hand_result
# ---------------------------------------------------------------------------


class TestSeatLabelDisplay:
    """Verify the correct seat label is shown for the bidder."""

    EXPECTED_LABELS = {
        0: "You",
        1: "Slim",
        2: "Ace",
        3: "Deuce",
    }

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    def test_bidder_label(self, env: jinja2.Environment, bidder_seat: int) -> None:
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type="regular",
            contract_type="high",
            trump=None,
            winning_bid=6,
            declarer_tricks=7,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        expected = self.EXPECTED_LABELS[bidder_seat]
        assert (
            expected in html
        ), f"Expected seat label '{expected}' for seat {bidder_seat}"


# ---------------------------------------------------------------------------
# 6. All suits rendered correctly for suit contracts
# ---------------------------------------------------------------------------


class TestAllSuitsDisplay:
    """Verify all 4 suit symbols render in hand_result for suit contracts."""

    SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

    @pytest.mark.parametrize("trump", SUITS, ids=lambda s: f"trump_{s}")
    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    def test_suit_symbol_rendered(
        self,
        env: jinja2.Environment,
        trump: str,
        bidder_seat: int,
    ) -> None:
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type="regular",
            contract_type="suit",
            trump=trump,
            winning_bid=6,
            declarer_tricks=7,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        expected_symbol = self.SUIT_SYMBOLS[trump]
        assert (
            expected_symbol in html
        ), f"Expected '{expected_symbol}' for trump {trump}"


# ---------------------------------------------------------------------------
# 7. Edge cases — no-bid (all pass) and boundary trick counts
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: zero tricks, all tricks, boundary bids."""

    def test_no_bid_both_get_tricks(self) -> None:
        """All-pass: both teams get their tricks."""
        p0, p1 = compute_points(None, None, 4, 6)
        assert p0 == 4
        assert p1 == 6

    def test_no_bid_zero_tricks(self) -> None:
        """All-pass: team with 0 tricks gets 0 points."""
        p0, p1 = compute_points(None, None, 0, 10)
        assert p0 == 0
        assert p1 == 10

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS)
    def test_minimum_bid_exact_make(self, bidder_seat: int) -> None:
        """Minimum bid (6) exactly made."""
        t0, t1 = _tricks_split(bidder_seat, 6)
        p0, p1 = compute_points(6, bidder_seat, t0, t1, bid_type="regular")
        team = _team_for(bidder_seat)
        bid_pts = p0 if team == 0 else p1
        assert bid_pts == 6

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS)
    def test_minimum_bid_set_by_one(self, bidder_seat: int) -> None:
        """Minimum bid (6) set by one trick."""
        t0, t1 = _tricks_split(bidder_seat, 5)
        p0, p1 = compute_points(6, bidder_seat, t0, t1, bid_type="regular")
        team = _team_for(bidder_seat)
        bid_pts = p0 if team == 0 else p1
        assert bid_pts == -6

    def test_invalid_bid_type_raises(self) -> None:
        """Invalid bid_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bid_type"):
            compute_points(6, 0, 7, 3, bid_type="bogus")


# ---------------------------------------------------------------------------
# 8. Result CSS class matrix
# ---------------------------------------------------------------------------


class TestResultCSSClasses:
    """Verify the correct CSS class is applied per bid_type/outcome/perspective."""

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    def test_regular_made_human_declared(
        self, env: jinja2.Environment, bidder_seat: int
    ) -> None:
        """Human team declares and makes: result--made."""
        if _team_for(bidder_seat) != 0:
            pytest.skip("Only team 0 seats for human-declared test")
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type="regular",
            contract_type="high",
            trump=None,
            winning_bid=6,
            declarer_tricks=7,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        assert "result--made" in html

    @pytest.mark.parametrize("bidder_seat", ALL_SEATS, ids=lambda s: f"seat{s}")
    def test_regular_set_human_declared(
        self, env: jinja2.Environment, bidder_seat: int
    ) -> None:
        """Human team declares and gets set: result--set."""
        if _team_for(bidder_seat) != 0:
            pytest.skip("Only team 0 seats for human-declared test")
        ctx = _make_hand_result_context(
            bidder_seat=bidder_seat,
            bid_type="regular",
            contract_type="high",
            trump=None,
            winning_bid=6,
            declarer_tricks=5,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        assert "result--set" in html

    @pytest.mark.parametrize("bid_type", ["moon", "loner"])
    def test_special_made_class(self, env: jinja2.Environment, bid_type: str) -> None:
        """Moon/loner made gets specific CSS class."""
        ctx = _make_hand_result_context(
            bidder_seat=0,
            bid_type=bid_type,
            contract_type="suit",
            trump="H",
            winning_bid=10,
            declarer_tricks=10,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        assert f"result--{bid_type}-made" in html

    @pytest.mark.parametrize("bid_type", ["moon", "loner"])
    def test_special_set_class(self, env: jinja2.Environment, bid_type: str) -> None:
        """Moon/loner set gets specific CSS class."""
        ctx = _make_hand_result_context(
            bidder_seat=0,
            bid_type=bid_type,
            contract_type="suit",
            trump="H",
            winning_bid=10,
            declarer_tricks=8,
        )
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)
        assert f"result--{bid_type}-set" in html
