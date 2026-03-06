"""Tests proving H10: bid-level search degeneracy.

_compute_ev_static has a bid-independent make payoff (2*E[T|make] - 10) and a
bid-dependent set penalty (E[T|set] - bid_n - 10). Since set_ev decreases with
bid_n while make_ev is constant, EV is monotonically non-increasing in bid_n.
Consequently, compute_best_bid with bid_level_search=True always selects the
minimum legal bid, defeating the purpose of level search.
"""

import math

import pytest

from bid_euchre.strategy.bidding import _compute_ev_static, compute_best_bid


class TestH10EvMonotonicity:
    """Prove EV is monotonically non-increasing in bid_n."""

    @pytest.mark.parametrize("mu", [3.0, 5.0, 6.5, 8.0, 9.5])
    @pytest.mark.parametrize("sigma", [0.5, 1.0, 1.5, 2.5])
    def test_ev_monotonically_decreasing(self, mu: float, sigma: float) -> None:
        """EV must be non-increasing as bid_n rises (sigma > 0)."""
        evs = [_compute_ev_static(mu, sigma, n) for n in range(1, 11)]
        for i in range(len(evs) - 1):
            assert evs[i] >= evs[i + 1], (
                f"Monotonicity violated at n={i + 1}→{i + 2}: "
                f"ev[{i + 1}]={evs[i]:.6f} < ev[{i + 2}]={evs[i + 1]:.6f} "
                f"(mu={mu}, sigma={sigma})"
            )

    @pytest.mark.parametrize("mu", [3.0, 5.0, 7.0, 9.0])
    def test_ev_monotonically_decreasing_zero_sigma(self, mu: float) -> None:
        """EV must be non-increasing as bid_n rises (sigma=0 edge case)."""
        evs = [_compute_ev_static(mu, 0.0, n) for n in range(1, 11)]
        for i in range(len(evs) - 1):
            assert evs[i] >= evs[i + 1], (
                f"Monotonicity violated at n={i + 1}→{i + 2}: "
                f"ev[{i + 1}]={evs[i]:.6f} < ev[{i + 2}]={evs[i + 1]:.6f} "
                f"(mu={mu}, sigma=0.0)"
            )

    @pytest.mark.parametrize("mu", [5.0, 6.5, 8.0])
    @pytest.mark.parametrize("sigma", [1.0, 1.5])
    @pytest.mark.parametrize("current_high_bid", [0, 3, 5, 7])
    def test_search_always_selects_min_legal(
        self, mu: float, sigma: float, current_high_bid: int
    ) -> None:
        """bid_level_search=True always picks min_legal due to monotonicity.

        When EV at min_legal is non-positive, the function correctly returns
        None (pass). The key assertion: search never selects a bid above
        min_legal, because EV is monotonically decreasing.
        """
        result = compute_best_bid(mu, sigma, current_high_bid, bid_level_search=True)
        min_legal = max(1, current_high_bid + 1)
        if result is None:
            # Correctly passed — verify EV at min_legal is indeed non-positive
            if min_legal <= 10:
                ev_at_min = _compute_ev_static(mu, sigma, min_legal)
                assert ev_at_min <= 0.0, (
                    f"Search returned None but EV at min_legal={min_legal} is "
                    f"{ev_at_min:.6f} > 0 (mu={mu}, sigma={sigma})"
                )
        else:
            bid_n, _utility = result
            assert bid_n == min_legal, (
                f"Search selected bid_n={bid_n}, expected min_legal={min_legal} "
                f"(mu={mu}, sigma={sigma}, high={current_high_bid})"
            )

    @pytest.mark.parametrize("mu", [5.0, 6.5, 8.0])
    @pytest.mark.parametrize("sigma", [1.0, 1.5])
    @pytest.mark.parametrize("current_high_bid", [0, 3, 5, 7])
    def test_floor_mode_selects_floor_mu(
        self, mu: float, sigma: float, current_high_bid: int
    ) -> None:
        """bid_level_search=False evaluates floor(mu) only."""
        result = compute_best_bid(mu, sigma, current_high_bid, bid_level_search=False)
        floor_mu = math.floor(mu)
        min_legal = max(1, current_high_bid + 1)

        if floor_mu < min_legal or floor_mu > 10:
            assert result is None, (
                f"Expected None (floor_mu={floor_mu} out of legal range "
                f"[{min_legal}, 10]) but got {result}"
            )
        elif result is None:
            # Correctly passed — verify EV at floor(mu) is indeed non-positive
            ev_at_floor = _compute_ev_static(mu, sigma, floor_mu)
            assert ev_at_floor <= 0.0, (
                f"Floor mode returned None but EV at floor_mu={floor_mu} is "
                f"{ev_at_floor:.6f} > 0 (mu={mu}, sigma={sigma})"
            )
        else:
            bid_n, _utility = result
            assert bid_n == floor_mu, (
                f"Floor mode selected bid_n={bid_n}, expected floor(mu)={floor_mu} "
                f"(mu={mu}, sigma={sigma}, high={current_high_bid})"
            )

    @pytest.mark.parametrize(
        "mu, sigma, current_high_bid, expected_search, expected_floor",
        [
            (6.5, 1.3, 0, 1, 6),
            (8.0, 1.5, 0, 1, 8),
        ],
        ids=["mu6.5_search1_floor6", "mu8.0_search1_floor8"],
    )
    def test_search_vs_floor_divergence(
        self,
        mu: float,
        sigma: float,
        current_high_bid: int,
        expected_search: int,
        expected_floor: int,
    ) -> None:
        """Demonstrate specific cases where search and floor disagree."""
        search_result = compute_best_bid(
            mu, sigma, current_high_bid, bid_level_search=True
        )
        floor_result = compute_best_bid(
            mu, sigma, current_high_bid, bid_level_search=False
        )

        assert search_result is not None
        assert floor_result is not None

        search_bid = search_result[0]
        floor_bid = floor_result[0]

        assert (
            search_bid == expected_search
        ), f"Search bid={search_bid}, expected {expected_search}"
        assert (
            floor_bid == expected_floor
        ), f"Floor bid={floor_bid}, expected {expected_floor}"
        assert search_bid != floor_bid, (
            f"Expected divergence but both modes selected bid_n={search_bid} "
            f"(mu={mu}, sigma={sigma})"
        )


class TestBidBonusFix:
    """Prove that bid_bonus parameter breaks H10 degeneracy."""

    @pytest.mark.parametrize("mu", [4.0, 6.5, 8.0])
    @pytest.mark.parametrize("sigma", [0.5, 1.0, 1.5, 2.5])
    def test_bid_bonus_zero_preserves_monotonicity(
        self, mu: float, sigma: float
    ) -> None:
        """With bid_bonus=0.0, EV is still monotonically non-increasing (backward compat)."""
        evs = [_compute_ev_static(mu, sigma, n, bid_bonus=0.0) for n in range(1, 11)]
        for i in range(len(evs) - 1):
            assert evs[i] >= evs[i + 1], (
                f"Monotonicity violated at n={i + 1}->{i + 2}: "
                f"ev[{i + 1}]={evs[i]:.6f} < ev[{i + 2}]={evs[i + 1]:.6f} "
                f"(mu={mu}, sigma={sigma}, bid_bonus=0.0)"
            )

    def test_bid_bonus_breaks_monotonicity(self) -> None:
        """With bid_bonus=1.0, EV is NOT monotonically decreasing for mu=6.5, sigma=1.3.

        There should be a peak near floor(mu), proving the bonus creates
        a non-trivial optimum.
        """
        mu, sigma, bid_bonus = 6.5, 1.3, 1.0
        evs = [
            _compute_ev_static(mu, sigma, n, bid_bonus=bid_bonus) for n in range(1, 11)
        ]

        # Check that monotonicity is broken: at least one pair where ev[i] < ev[i+1]
        has_increase = any(evs[i] < evs[i + 1] for i in range(len(evs) - 1))
        assert has_increase, (
            f"Expected non-monotonic EV with bid_bonus={bid_bonus}, "
            f"but EVs are still non-increasing: {[f'{e:.3f}' for e in evs]}"
        )

        # Peak should be near floor(mu)=6
        peak_n = max(range(1, 11), key=lambda n: evs[n - 1])
        floor_mu = math.floor(mu)
        assert abs(peak_n - floor_mu) <= 2, (
            f"Peak at n={peak_n}, expected near floor(mu)={floor_mu} "
            f"(mu={mu}, sigma={sigma}, bid_bonus={bid_bonus})"
        )

    @pytest.mark.parametrize(
        "mu, sigma, bid_bonus, min_expected_bid",
        [
            (5.0, 1.5, 0.5, 3),
            (6.5, 1.3, 0.5, 4),
            (8.0, 1.5, 0.5, 5),
        ],
        ids=["mu5.0_bonus0.5", "mu6.5_bonus0.5", "mu8.0_bonus0.5"],
    )
    def test_bid_bonus_selects_near_floor_mu(
        self,
        mu: float,
        sigma: float,
        bid_bonus: float,
        min_expected_bid: int,
    ) -> None:
        """With bid_bonus > 0, bid_level_search selects near floor(mu), not min_legal."""
        result = compute_best_bid(
            mu, sigma, 0, bid_level_search=True, bid_bonus=bid_bonus
        )
        assert result is not None, (
            f"Expected a bid but got None "
            f"(mu={mu}, sigma={sigma}, bid_bonus={bid_bonus})"
        )
        bid_n, _utility = result
        assert bid_n > 1, (
            f"bid_bonus={bid_bonus} should prevent min_legal=1 selection, "
            f"but got bid_n={bid_n} (mu={mu}, sigma={sigma})"
        )
        assert bid_n >= min_expected_bid, (
            f"Expected bid_n >= {min_expected_bid} but got {bid_n} "
            f"(mu={mu}, sigma={sigma}, bid_bonus={bid_bonus})"
        )

    @pytest.mark.parametrize("mu", [6.0, 6.5, 8.0])
    @pytest.mark.parametrize("sigma", [1.0, 1.5])
    def test_bid_bonus_backward_compat(self, mu: float, sigma: float) -> None:
        """With bid_bonus=0.0, compute_best_bid returns same as current behavior (min_legal).

        Uses mu >= 6.0 so that EV at min_legal=1 is positive (hands that actually bid).
        """
        result_bonus_zero = compute_best_bid(
            mu, sigma, 0, bid_level_search=True, bid_bonus=0.0
        )
        # With bid_bonus=0.0, monotonicity holds => search always selects min_legal=1
        assert (
            result_bonus_zero is not None
        ), f"Expected a bid but got None (mu={mu}, sigma={sigma}, bid_bonus=0.0)"
        bid_n, _utility = result_bonus_zero
        min_legal = 1  # current_high_bid=0 => min_legal=1
        assert bid_n == min_legal, (
            f"bid_bonus=0.0 should select min_legal={min_legal} but got {bid_n} "
            f"(mu={mu}, sigma={sigma})"
        )

    @pytest.mark.parametrize("bid_bonus", [0.0, 0.25, 0.5, 1.0])
    def test_bid_bonus_does_not_affect_pass_decision(self, bid_bonus: float) -> None:
        """For a hand that should pass (mu=3.0, sigma=1.5), result is None regardless of bid_bonus."""
        # mu=3.0, sigma=1.5 with current_high_bid=5
        # means min_legal=6, which is far above mu => should pass
        result = compute_best_bid(
            mu=3.0,
            sigma=1.5,
            current_high_bid=5,
            bid_level_search=True,
            bid_bonus=bid_bonus,
        )
        assert result is None, (
            f"Expected None (pass) for mu=3.0, high_bid=5, bid_bonus={bid_bonus} "
            f"but got {result}"
        )

    def test_diagnostic_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Print diagnostic table showing bid selection across (mu, sigma, bid_bonus)."""
        mus = [4.0, 5.0, 6.0, 6.5, 7.0, 8.0, 9.0]
        sigmas = [1.0, 1.5]
        bonuses = [0.0, 0.25, 0.5, 1.0]

        print()
        print("## Bid Selection Diagnostic Table")
        print()
        header = (
            "| mu  | sigma | "
            + " | ".join(f"bonus={b}" for b in bonuses)
            + " | floor(mu) |"
        )
        print(header)
        sep = (
            "|-----|-------|" + "|".join("--------" for _ in bonuses) + "|-----------|"
        )
        print(sep)

        for mu in mus:
            for sigma in sigmas:
                row_parts = [f"| {mu:3.1f} | {sigma:5.1f} |"]
                for bonus in bonuses:
                    result = compute_best_bid(
                        mu,
                        sigma,
                        0,
                        bid_level_search=True,
                        bid_bonus=bonus,
                    )
                    if result is None:
                        row_parts.append(" None   |")
                    else:
                        bid_n, utility = result
                        row_parts.append(f" {bid_n:2d} ({utility:+.2f}) |")
                row_parts.append(f" {math.floor(mu):9d} |")
                print("".join(row_parts))
        print()
