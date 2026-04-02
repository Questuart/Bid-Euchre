"""Exhaustive bid/outcome test scaffold (#1918).

Full cross-product matrix:
    bid_type × contract_type × outcome × bidder_seat

Verifies:
    1. compute_points() returns correct values for every cell
    2. hand_result.html renders points, banner, contract label, seat label,
       and CSS class that are consistent with the scoring output

Complements test_scoring_matrix.py by exhaustively crossing contract_type (all
4 suits + high + low) with every bid_type/outcome/seat combination, and
verifying the score-delta emphasis section for moon/loner.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jinja2
import pytest

from bid_euchre.scoring import compute_points

# ---------------------------------------------------------------------------
# Template environment
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "templates",
)


@pytest.fixture()
def jinja_env():
    """Jinja2 environment pointing at the web templates directory."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(_TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_SEATS = [0, 1, 2, 3]

# (contract_type, trump) — 6 contract variants
CONTRACTS: list[tuple[str, str | None]] = [
    ("suit", "S"),
    ("suit", "H"),
    ("suit", "D"),
    ("suit", "C"),
    ("high", None),
    ("low", None),
]

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

SEAT_LABELS = {0: "You", 1: "AI Left", 2: "AI Partner", 3: "AI Right"}


# ---------------------------------------------------------------------------
# Outcome descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One outcome scenario for a bid type."""

    label: str
    bid_amount: int
    declarer_tricks: int
    made: bool  # True if declaring team made the contract


# Regular outcomes: vary bid amount and tricks
REGULAR_OUTCOMES = [
    Outcome("make_exact", 6, 6, True),
    Outcome("make_over", 6, 8, True),
    Outcome("set_by_1", 6, 5, False),
    Outcome("set_by_many", 8, 3, False),
]

# Moon: must take all 10 tricks
MOON_OUTCOMES = [
    Outcome("made", 10, 10, True),
    Outcome("set_by_1", 10, 9, False),
    Outcome("set_by_many", 10, 5, False),
]

# Loner: same trick requirement as moon, higher stakes
LONER_OUTCOMES = [
    Outcome("made", 10, 10, True),
    Outcome("set_by_1", 10, 9, False),
    Outcome("set_by_many", 10, 5, False),
]

BID_TYPE_OUTCOMES: dict[str, list[Outcome]] = {
    "regular": REGULAR_OUTCOMES,
    "moon": MOON_OUTCOMES,
    "loner": LONER_OUTCOMES,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _team_for(seat: int) -> int:
    """0 for seats 0/2, 1 for seats 1/3."""
    return 0 if seat in (0, 2) else 1


def _tricks_split(bidder_seat: int, declarer_tricks: int) -> tuple[int, int]:
    """Return (tricks_team0, tricks_team1) from bidder perspective."""
    defender_tricks = 10 - declarer_tricks
    if _team_for(bidder_seat) == 0:
        return declarer_tricks, defender_tricks
    return defender_tricks, declarer_tricks


def _expected_points(
    bid_type: str, outcome: Outcome, bidder_seat: int
) -> tuple[int, int]:
    """Compute expected (pts_team0, pts_team1) from first principles.

    This duplicates the scoring rules intentionally — the test verifies
    compute_points matches this independent calculation.
    """
    bid_team = _team_for(bidder_seat)
    defender_tricks = 10 - outcome.declarer_tricks

    if bid_type == "regular":
        if outcome.made:
            bid_pts = outcome.declarer_tricks
        else:
            bid_pts = -outcome.bid_amount
        def_pts = defender_tricks
    elif bid_type == "moon":
        bid_pts = 20 if outcome.made else -20
        def_pts = defender_tricks
    elif bid_type == "loner":
        bid_pts = 40 if outcome.made else -40
        def_pts = defender_tricks
    else:
        raise ValueError(bid_type)

    if bid_team == 0:
        return bid_pts, def_pts
    return def_pts, bid_pts


# ---------------------------------------------------------------------------
# Matrix case and generation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One cell in the exhaustive test matrix."""

    bid_type: str
    contract_type: str
    trump: str | None
    outcome: Outcome
    bidder_seat: int

    @property
    def test_id(self) -> str:
        ct = f"{self.contract_type}_{self.trump}" if self.trump else self.contract_type
        return f"{self.bid_type}-{ct}-{self.outcome.label}-seat{self.bidder_seat}"


def _build_matrix() -> list[Case]:
    cases: list[Case] = []
    for bid_type, outcomes in BID_TYPE_OUTCOMES.items():
        for ct, trump in CONTRACTS:
            for outcome in outcomes:
                for seat in ALL_SEATS:
                    cases.append(Case(bid_type, ct, trump, outcome, seat))
    return cases


MATRIX = _build_matrix()
MATRIX_IDS = [c.test_id for c in MATRIX]


def _render(jinja_env: jinja2.Environment, case: Case) -> tuple[str, int, int]:
    """Render hand_result.html for *case* and return (html, pts0, pts1)."""
    t0, t1 = _tricks_split(case.bidder_seat, case.outcome.declarer_tricks)
    p0, p1 = compute_points(
        case.outcome.bid_amount,
        case.bidder_seat,
        t0,
        t1,
        bid_type=case.bid_type,
    )
    ctx = {
        "winning_bid": case.outcome.bid_amount,
        "bidder_seat": case.bidder_seat,
        "contract_type": case.contract_type,
        "trump": case.trump,
        "bid_type": case.bid_type,
        "tricks_team0": t0,
        "tricks_team1": t1,
        "points_team0": p0,
        "points_team1": p1,
        "score_human": p0,
        "score_ai": p1,
        "hands_played": 1,
        "link_uuid": "test-uuid",
    }
    tmpl = jinja_env.get_template("partials/hand_result.html")
    return tmpl.render(**ctx), p0, p1


# ---------------------------------------------------------------------------
# 1. Scoring correctness — full matrix
# ---------------------------------------------------------------------------


class TestScoringMatrix:
    """compute_points returns expected values for every matrix cell."""

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_points_match_rules(self, case: Case) -> None:
        t0, t1 = _tricks_split(case.bidder_seat, case.outcome.declarer_tricks)
        actual = compute_points(
            case.outcome.bid_amount,
            case.bidder_seat,
            t0,
            t1,
            bid_type=case.bid_type,
        )
        expected = _expected_points(case.bid_type, case.outcome, case.bidder_seat)
        assert (
            actual == expected
        ), f"compute_points returned {actual}, expected {expected}"


# ---------------------------------------------------------------------------
# 2. Display consistency — scoring × template agreement
# ---------------------------------------------------------------------------


class TestDisplayConsistency:
    """Template-rendered content matches compute_points output."""

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_points_in_html(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Rendered points strings match compute_points output."""
        html, p0, p1 = _render(jinja_env, case)

        p0_str = f"+{p0}" if p0 > 0 else str(p0)
        p1_str = f"+{p1}" if p1 > 0 else str(p1)
        assert p0_str in html, f"Team0 points '{p0_str}' not in HTML"
        assert p1_str in html, f"Team1 points '{p1_str}' not in HTML"

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_banner_text(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Correct banner (Made it! / Set! / Moon Made! / …) rendered."""
        html, _, _ = _render(jinja_env, case)

        if case.bid_type == "moon":
            expected = "Moon Made!" if case.outcome.made else "Moon Set!"
        elif case.bid_type == "loner":
            expected = "Loner Made!" if case.outcome.made else "Loner Set!"
        else:
            expected = "Made it!" if case.outcome.made else "Set!"

        assert expected in html, f"Banner '{expected}' not found in HTML"

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_contract_label(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Correct contract label (suit symbol / High / Low) rendered."""
        html, _, _ = _render(jinja_env, case)

        if case.contract_type == "suit" and case.trump:
            assert (
                SUIT_SYMBOLS[case.trump] in html
            ), f"Suit symbol for {case.trump} not in HTML"
        elif case.contract_type == "high":
            assert "High" in html, "High label not in HTML"
        elif case.contract_type == "low":
            assert "Low" in html, "Low label not in HTML"

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_seat_label(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Correct seat label (You / AI Left / AI Partner / AI Right)."""
        html, _, _ = _render(jinja_env, case)
        expected = SEAT_LABELS[case.bidder_seat]
        assert expected in html, f"Seat label '{expected}' not in HTML"


# ---------------------------------------------------------------------------
# 3. CSS class correctness — full matrix
# ---------------------------------------------------------------------------


class TestCSSClasses:
    """Correct result CSS class for every matrix cell."""

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_result_class(self, case: Case, jinja_env: jinja2.Environment) -> None:
        html, _, _ = _render(jinja_env, case)

        if case.bid_type == "moon":
            expected_cls = (
                "result--moon-made" if case.outcome.made else "result--moon-set"
            )
        elif case.bid_type == "loner":
            expected_cls = (
                "result--loner-made" if case.outcome.made else "result--loner-set"
            )
        else:
            # Regular: class depends on whether outcome is good for human
            human_declared = case.bidder_seat in (0, 2)
            is_good_for_human = (case.outcome.made and human_declared) or (
                not case.outcome.made and not human_declared
            )
            expected_cls = "result--made" if is_good_for_human else "result--set"

        assert expected_cls in html, f"CSS class '{expected_cls}' not in HTML"

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_points_css_classes(
        self, case: Case, jinja_env: jinja2.Environment
    ) -> None:
        """Points cells have correct positive/negative CSS class."""
        html, p0, _p1 = _render(jinja_env, case)

        if p0 > 0:
            assert "points--positive" in html
        elif p0 < 0:
            assert "points--negative" in html

    @pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
    def test_title_mood_class(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Result title has contextual positive/negative class (2c)."""
        html, _, _ = _render(jinja_env, case)
        human_declared = case.bidder_seat in (0, 2)
        is_good_for_human = (case.outcome.made and human_declared) or (
            not case.outcome.made and not human_declared
        )
        expected = (
            "result-title--positive" if is_good_for_human else "result-title--negative"
        )
        assert expected in html, f"Title mood class '{expected}' not in HTML"


# ---------------------------------------------------------------------------
# 4. Moon/loner score-delta emphasis
# ---------------------------------------------------------------------------


class TestScoreDeltaEmphasis:
    """Moon/loner results render a score-delta section with correct text."""

    _SPECIAL_CASES = [c for c in MATRIX if c.bid_type in ("moon", "loner")]
    _SPECIAL_IDS = [c.test_id for c in _SPECIAL_CASES]

    @pytest.mark.parametrize("case", _SPECIAL_CASES, ids=_SPECIAL_IDS)
    def test_score_delta_section(
        self, case: Case, jinja_env: jinja2.Environment
    ) -> None:
        """Score-delta div present with MOON/LONER MADE/SET text."""
        html, _p0, _ = _render(jinja_env, case)

        assert "score-delta" in html, "score-delta section missing"

        label = case.bid_type.upper()
        assert label in html, f"'{label}' not in score-delta section"

        if case.outcome.made:
            assert "MADE" in html
        else:
            assert "SET" in html

    @pytest.mark.parametrize("case", _SPECIAL_CASES, ids=_SPECIAL_IDS)
    def test_score_delta_value(self, case: Case, jinja_env: jinja2.Environment) -> None:
        """Score-delta shows correct human point delta."""
        html, p0, _ = _render(jinja_env, case)

        delta_str = f"+{p0}" if p0 > 0 else str(p0)
        assert delta_str in html, f"Score delta '{delta_str}' not in HTML"

    _REGULAR_CASES = [c for c in MATRIX if c.bid_type == "regular"]
    _REGULAR_IDS = [c.test_id for c in _REGULAR_CASES]

    @pytest.mark.parametrize("case", _REGULAR_CASES, ids=_REGULAR_IDS)
    def test_no_score_delta_for_regular(
        self, case: Case, jinja_env: jinja2.Environment
    ) -> None:
        """Regular bids do not render a score-delta section."""
        html, _, _ = _render(jinja_env, case)
        assert (
            "score-delta--" not in html
        ), "score-delta modifier class should not appear for regular bids"


# ---------------------------------------------------------------------------
# 5. All-pass (no bid) edge cases
# ---------------------------------------------------------------------------


class TestAllPass:
    """Scoring when no bid is placed (all pass → redeal)."""

    @pytest.mark.parametrize(
        "t0,t1",
        [(5, 5), (0, 10), (10, 0), (3, 7), (7, 3)],
        ids=["even", "team0_zero", "team1_zero", "team0_low", "team1_low"],
    )
    def test_both_teams_get_tricks(self, t0: int, t1: int) -> None:
        """No-bid: both teams score their trick count as points."""
        p0, p1 = compute_points(None, None, t0, t1)
        assert p0 == t0
        assert p1 == t1

    def test_invalid_bid_type_raises(self) -> None:
        """Invalid bid_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bid_type"):
            compute_points(6, 0, 7, 3, bid_type="bogus")
