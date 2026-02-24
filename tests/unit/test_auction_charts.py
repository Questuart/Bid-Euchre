"""Unit tests for auction diagnostic chart functions."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # Non-interactive backend for testing

from bid_euchre.diagnostics.auction_charts import (
    plot_auction_health,
    plot_bidder_performance,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic eval DataFrames
# ---------------------------------------------------------------------------


def _make_eval_df(n_deals: int = 50, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic eval-style DataFrame mimicking build_eval_dataset output."""
    rng = np.random.RandomState(seed)
    rows = []
    contract_types = ["suit", "high", "low"]
    for deal_id in range(n_deals):
        ct = rng.choice(contract_types)
        winning_bid = rng.randint(6, 11)
        bidder_seat = rng.randint(0, 4)
        bidder_team = 0 if bidder_seat in (0, 2) else 1
        t0 = rng.randint(3, 8)
        t1 = 10 - t0
        made_bid = (t0 >= winning_bid) if bidder_team == 0 else (t1 >= winning_bid)
        n_bids = rng.randint(1, 5)
        n_passes = rng.randint(1, 4)
        auction_rounds = n_bids + n_passes

        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            tricks_won = t0 if team == 0 else t1
            rows.append(
                {
                    "deal_id": deal_id,
                    "seat": seat,
                    "team": team,
                    "contract_type": ct,
                    "trump": "H" if ct == "suit" else None,
                    "tricks_won": tricks_won,
                    "winning_bid": winning_bid,
                    "bidder_seat": bidder_seat,
                    "bidder_team": bidder_team,
                    "is_bidder": seat == bidder_seat,
                    "is_declaring_team": team == bidder_team,
                    "made_bid": made_bid,
                    "n_bids": n_bids,
                    "n_passes": n_passes,
                    "auction_rounds": auction_rounds,
                    "hand_id": deal_id,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests: plot_auction_health
# ---------------------------------------------------------------------------


class TestPlotAuctionHealth:
    """Tests for plot_auction_health function."""

    @pytest.fixture
    def eval_df(self) -> pd.DataFrame:
        return _make_eval_df()

    def test_returns_figure(self, eval_df: pd.DataFrame) -> None:
        """plot_auction_health returns a matplotlib Figure."""
        fig = plot_auction_health(eval_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_three_panels(self, eval_df: pd.DataFrame) -> None:
        """Figure contains 3 axes (panels)."""
        fig = plot_auction_health(eval_df)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 3
        plt.close(fig)

    def test_custom_title(self, eval_df: pd.DataFrame) -> None:
        """Custom title is applied."""
        fig = plot_auction_health(eval_df, title="Test Title")
        assert fig._suptitle.get_text() == "Test Title"
        plt.close(fig)

    def test_custom_figsize(self, eval_df: pd.DataFrame) -> None:
        """Custom figsize is respected."""
        fig = plot_auction_health(eval_df, figsize=(12, 4))
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame handled gracefully."""
        empty_df = pd.DataFrame(
            columns=[
                "deal_id",
                "contract_type",
                "winning_bid",
                "auction_rounds",
            ]
        )
        fig = plot_auction_health(empty_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_missing_columns(self) -> None:
        """DataFrame missing required columns handled gracefully."""
        bad_df = pd.DataFrame({"x": [1, 2, 3]})
        fig = plot_auction_health(bad_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_contract_type(self) -> None:
        """Works with only one contract type."""
        df = _make_eval_df()
        df = df[df["contract_type"] == "suit"].copy()
        fig = plot_auction_health(df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Tests: plot_bidder_performance
# ---------------------------------------------------------------------------


class TestPlotBidderPerformance:
    """Tests for plot_bidder_performance function."""

    @pytest.fixture
    def eval_df(self) -> pd.DataFrame:
        return _make_eval_df()

    def test_returns_figure(self, eval_df: pd.DataFrame) -> None:
        """plot_bidder_performance returns a matplotlib Figure."""
        fig = plot_bidder_performance(eval_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_three_panels(self, eval_df: pd.DataFrame) -> None:
        """Figure contains 3 axes (panels)."""
        fig = plot_bidder_performance(eval_df)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 3
        plt.close(fig)

    def test_custom_title(self, eval_df: pd.DataFrame) -> None:
        """Custom title is applied."""
        fig = plot_bidder_performance(eval_df, title="Bidder Test")
        assert fig._suptitle.get_text() == "Bidder Test"
        plt.close(fig)

    def test_custom_figsize(self, eval_df: pd.DataFrame) -> None:
        """Custom figsize is respected."""
        fig = plot_bidder_performance(eval_df, figsize=(14, 5))
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame handled gracefully."""
        empty_df = pd.DataFrame(
            columns=[
                "is_bidder",
                "contract_type",
                "made_bid",
                "winning_bid",
                "is_declaring_team",
                "tricks_won",
            ]
        )
        fig = plot_bidder_performance(empty_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_missing_columns(self) -> None:
        """DataFrame missing required columns handled gracefully."""
        bad_df = pd.DataFrame({"x": [1, 2, 3]})
        fig = plot_bidder_performance(bad_df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_contract_type(self) -> None:
        """Works with only one contract type."""
        df = _make_eval_df()
        df = df[df["contract_type"] == "high"].copy()
        fig = plot_bidder_performance(df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_no_bidder_rows(self) -> None:
        """Handles case where no rows have is_bidder == True."""
        df = _make_eval_df()
        df["is_bidder"] = False
        fig = plot_bidder_performance(df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Teardown: close all figures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _close_all_figures():
    """Close all matplotlib figures after each test to prevent leaks."""
    yield
    plt.close("all")
