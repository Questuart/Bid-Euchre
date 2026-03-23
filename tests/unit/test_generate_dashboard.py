"""Smoke tests for scripts/generate_dashboard.py."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Add scripts to path so we can import
scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
sys.path.insert(0, scripts_dir)
from generate_dashboard import (  # noqa: E402
    _GH_PR_LIMIT,
    WINDOW,
    _bollinger,
    _draw_bollinger_panel,
    _gather_pr_counts,
    generate_dashboard,
)


class TestBollinger:
    """Tests for the _bollinger computation."""

    def test_empty_data_below_window(self):
        """When data has fewer points than window, all SMA values are NaN."""
        data = np.array([1.0, 2.0, 3.0])
        sma, upper, lower, pct_b = _bollinger(data, window=10, num_std=2)
        assert np.all(np.isnan(sma))
        assert np.all(np.isnan(upper))
        assert np.all(np.isnan(lower))

    def test_basic_computation(self):
        """SMA is correct for a simple known input."""
        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0], dtype=float)
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        # First 2 values should be NaN (window-1)
        assert np.isnan(sma[0])
        assert np.isnan(sma[1])
        # SMA at index 2 = mean([2, 4, 6]) = 4.0
        assert sma[2] == pytest.approx(4.0)
        # SMA at index 3 = mean([4, 6, 8]) = 6.0
        assert sma[3] == pytest.approx(6.0)
        # SMA at index 4 = mean([6, 8, 10]) = 8.0
        assert sma[4] == pytest.approx(8.0)

    def test_constant_data_zero_bandwidth(self):
        """When all values are equal, bands collapse and %B is 0.5."""
        data = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        # band_width is 0 when std=0, so pct_b should be 0.5
        assert pct_b[2] == pytest.approx(0.5)

    def test_clamp_lower_default(self):
        """Lower band is clamped at 0 by default."""
        # Data where mean - 2*std would be negative
        data = np.array([1.0, 0.0, 1.0, 0.0, 1.0], dtype=float)
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        for i in range(2, 5):
            assert lower[i] >= 0, f"lower[{i}] = {lower[i]} should be >= 0"

    def test_clamp_lower_false(self):
        """Lower band can go negative when clamp_lower=False."""
        # Data with high variance where lower band should go negative
        data = np.array([100.0, -100.0, 100.0, -100.0, 100.0], dtype=float)
        sma, upper, lower, pct_b = _bollinger(
            data, window=3, num_std=2, clamp_lower=False
        )
        # At least one lower value should be negative given the high variance
        has_negative = any(lower[i] < 0 for i in range(2, 5) if not np.isnan(lower[i]))
        assert has_negative, "Expected negative lower band with clamp_lower=False"

    def test_empty_data(self):
        """Empty array returns four empty arrays without error."""
        data = np.array([], dtype=float)
        sma, upper, lower, pct_b = _bollinger(data, window=10, num_std=2)
        assert len(sma) == 0
        assert len(upper) == 0
        assert len(lower) == 0
        assert len(pct_b) == 0

    def test_exactly_window_points(self):
        """With exactly window data points, only the last index is valid."""
        data = np.arange(1.0, 11.0)  # 10 points, window=10
        sma, upper, lower, pct_b = _bollinger(data, window=10, num_std=2)
        # Indices 0-8 should be NaN
        assert np.all(np.isnan(sma[:9]))
        # Index 9 (last) should be valid — SMA = mean(1..10) = 5.5
        assert sma[9] == pytest.approx(5.5)
        assert not np.isnan(upper[9])
        assert not np.isnan(lower[9])
        assert not np.isnan(pct_b[9])

    def test_validity_mask_independence(self):
        """Different data series produce independent validity masks.

        Regression test: Panel 5 previously reused Panel 4's validity mask.
        When two series have different NaN patterns, their masks must differ.
        """
        # Series A: 5 points, window=3 → valid from index 2
        data_a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sma_a, _, _, _ = _bollinger(data_a, window=3, num_std=2)
        valid_a = ~np.isnan(sma_a)

        # Series B: 5 points, window=5 → valid only at index 4
        sma_b, _, _, _ = _bollinger(data_a, window=5, num_std=2)
        valid_b = ~np.isnan(sma_b)

        # Masks must be different when windows differ
        assert not np.array_equal(valid_a, valid_b)
        assert valid_a.sum() == 3  # indices 2, 3, 4
        assert valid_b.sum() == 1  # index 4 only


class TestGenerateDashboardWiring:
    """Wiring tests that exercise generate_dashboard() end-to-end with mock data."""

    def _make_dates(self, n: int = 12) -> list[str]:
        return [f"2026-03-{d:02d}" for d in range(1, n + 1)]

    def test_panel5_receives_file_churn_data(self, tmp_path):
        """Panel 5 receives file_churn_pct data/SMA/valid, not Panel 4's line churn.

        Wiring regression test for the validity mask fix in PR #1365 / #1346.
        The test captures data, SMA, and valid mask for each panel and verifies:
        1. Data arrays differ (churn_pct ≈ 33.33 vs file_churn_pct = 30.0)
        2. SMA arrays match the correct metric (not swapped)
        3. Valid mask is consistent with SMA (derived from correct Bollinger)

        Note: With same WINDOW and same date set, validity masks for panels 4
        and 5 are structurally identical (same NaN pattern). The SMA check is
        the discriminating assertion — it WILL fail if panel 5 accidentally
        receives panel 4's Bollinger outputs.
        """
        dates = self._make_dates(12)

        # PR data: 1 PR per day, 10 additions, 5 deletions
        pr_counts = {d: 1 for d in dates}
        pr_additions = {d: 10 for d in dates}
        pr_deletions = {d: 5 for d in dates}

        # Line stats: 100 insertions, 20 deletions per day
        # → gross = 120, net = 80, churn_ratio = 1 - 80/120 ≈ 0.333, churn_pct ≈ 33.33
        day_ins = {d: 100 for d in dates}
        day_del = {d: 20 for d in dates}

        # File churn: 10 unique files, 3 churned per day
        # → file_churn_ratio = 3/10 = 0.30, file_churn_pct = 30.0
        unique_files = {d: 10 for d in dates}
        churned_files = {d: 3 for d in dates}

        draw_calls: list[dict] = []

        def tracking_draw(*args, **kwargs):
            # _draw_bollinger_panel(ax, x, data, sma, upper, lower, pct_b, valid, ...)
            draw_calls.append(
                {
                    "data": args[2].copy(),
                    "sma": args[3].copy(),
                    "valid": args[7].copy(),
                }
            )

        output_path = str(tmp_path / "test_dashboard.png")

        with (
            patch(
                "generate_dashboard._gather_pr_counts",
                return_value=(pr_counts, pr_additions, pr_deletions),
            ),
            patch(
                "generate_dashboard._gather_line_stats",
                return_value=(day_ins, day_del),
            ),
            patch(
                "generate_dashboard._gather_file_churn",
                return_value=(unique_files, churned_files),
            ),
            patch(
                "generate_dashboard._draw_bollinger_panel",
                side_effect=tracking_draw,
            ),
        ):
            generate_dashboard("/fake/repo", output_path)

        assert len(draw_calls) == 5, f"Expected 5 panel draws, got {len(draw_calls)}"

        # ── Data arrays: correct metric routed to each panel ──────────────
        # Panel 4 (line churn): churn_pct ≈ 33.33 for every date
        panel4_data = draw_calls[3]["data"]
        assert panel4_data[0] == pytest.approx(33.33, abs=0.1)

        # Panel 5 (file churn): file_churn_pct = 30.0 for every date
        panel5_data = draw_calls[4]["data"]
        assert panel5_data[0] == pytest.approx(30.0, abs=0.1)

        # The two panels must receive different data arrays
        assert not np.allclose(panel4_data, panel5_data), (
            "Panel 4 and Panel 5 should receive different data arrays "
            "(churn_pct vs file_churn_pct)"
        )

        # ── SMA arrays: correct Bollinger wired to each panel ─────────────
        # This is the discriminating check: SMA values reflect the metric
        # passed to _bollinger(). If panel 5 accidentally received panel 4's
        # lc_sma (≈33.33) instead of fc_sma (≈30.0), this assertion fails.
        panel4_sma = draw_calls[3]["sma"]
        panel5_sma = draw_calls[4]["sma"]

        # At the first valid index (WINDOW-1), SMA = mean of first WINDOW values
        first_valid = WINDOW - 1
        assert (
            panel4_sma[first_valid] == pytest.approx(33.33, abs=0.1)
        ), f"Panel 4 SMA should match line churn (≈33.33), got {panel4_sma[first_valid]:.2f}"
        assert (
            panel5_sma[first_valid] == pytest.approx(30.0, abs=0.1)
        ), f"Panel 5 SMA should match file churn (≈30.0), got {panel5_sma[first_valid]:.2f}"

        # SMA arrays must differ (same test as data, but for the Bollinger output)
        assert not np.allclose(
            panel4_sma[first_valid:], panel5_sma[first_valid:]
        ), "Panel 4 and Panel 5 should receive different SMA arrays (lc_sma vs fc_sma)"

        # ── Valid masks: internal consistency + joint discrimination ───────
        # Both panels share the same WINDOW and date count, so their valid
        # masks are structurally identical (same NaN warmup pattern).
        # Internal consistency alone doesn't discriminate — we must also
        # verify that each mask was delivered alongside the correct data.
        panel4_valid = draw_calls[3]["valid"]
        panel5_valid = draw_calls[4]["valid"]

        # Internal consistency: each mask matches its own SMA NaN pattern
        assert np.array_equal(
            panel4_valid, ~np.isnan(panel4_sma)
        ), "Panel 4 valid mask should match NaN pattern of its SMA"
        assert np.array_equal(
            panel5_valid, ~np.isnan(panel5_sma)
        ), "Panel 5 valid mask should match NaN pattern of its SMA"

        n_dates = len(dates)
        expected_valid = n_dates - WINDOW + 1  # warmup period = WINDOW - 1

        assert panel4_valid.sum() == expected_valid, (
            f"Panel 4 validity mask: expected {expected_valid} valid, "
            f"got {panel4_valid.sum()}"
        )
        assert panel5_valid.sum() == expected_valid, (
            f"Panel 5 validity mask: expected {expected_valid} valid, "
            f"got {panel5_valid.sum()}"
        )

        # Joint discrimination: verify each valid mask was delivered with
        # the correct data values in the same draw_call.  At first_valid,
        # both masks are True (structurally identical), but the paired data
        # values differ — proving the (mask, data) pair came from the right
        # panel.  A swap bug would fail here even though the masks alone
        # are indistinguishable.
        assert panel4_valid[first_valid] and draw_calls[3]["data"][
            first_valid
        ] == pytest.approx(
            33.33, abs=0.1
        ), "Panel 4: valid-mask/data pair must correspond to line churn (≈33.33)"
        assert panel5_valid[first_valid] and draw_calls[4]["data"][
            first_valid
        ] == pytest.approx(
            30.0, abs=0.1
        ), "Panel 5: valid-mask/data pair must correspond to file churn (≈30.0)"


class TestDrawBollingerPanel:
    """Tests for the panel rendering, especially the n_valid==0 edge case."""

    def test_zero_valid_no_crash(self):
        """Panel renders without error when n_valid is 0 (all NaN SMA)."""
        fig, ax = plt.subplots()
        n = 5
        x = np.arange(n)
        data = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        # All NaN — simulates window > data length
        sma = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        pct_b = np.full(n, np.nan)
        valid = ~np.isnan(sma)  # All False

        # Should NOT raise ZeroDivisionError
        _draw_bollinger_panel(
            ax,
            x,
            data,
            sma,
            upper,
            lower,
            pct_b,
            valid,
            latest_idx=n - 1,
            band_color="#3498db",
            sma_color="#2980b9",
            dot_color="#2c3e50",
        )
        plt.close(fig)

    def test_normal_rendering(self):
        """Panel renders correctly with valid Bollinger data."""
        fig, ax = plt.subplots()
        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        valid = ~np.isnan(sma)

        _draw_bollinger_panel(
            ax,
            np.arange(5),
            data,
            sma,
            upper,
            lower,
            pct_b,
            valid,
            latest_idx=4,
            band_color="#3498db",
            sma_color="#2980b9",
            dot_color="#2c3e50",
        )
        plt.close(fig)

    def test_allow_negative_rendering(self):
        """Panel with allow_negative=True renders with y-axis below zero."""
        fig, ax = plt.subplots()
        data = np.array([50.0, -30.0, 20.0, -10.0, 40.0], dtype=float)
        sma, upper, lower, pct_b = _bollinger(
            data, window=3, num_std=2, clamp_lower=False
        )
        valid = ~np.isnan(sma)

        _draw_bollinger_panel(
            ax,
            np.arange(5),
            data,
            sma,
            upper,
            lower,
            pct_b,
            valid,
            latest_idx=4,
            band_color="#16a085",
            sma_color="#1abc9c",
            dot_color="#2c3e50",
            allow_negative=True,
        )
        y_low, y_high = ax.get_ylim()
        assert y_low < 0, f"y-axis lower limit should be < 0, got {y_low}"
        plt.close(fig)


class TestGatherPrCounts:
    """Tests for _gather_pr_counts with mocked gh CLI."""

    def _mock_gh_output(self, prs: list[dict]) -> str:
        return json.dumps(prs)

    def test_basic_counts(self):
        """PRs are grouped by mergedAt date correctly."""
        prs = [
            {"mergedAt": "2026-03-20T10:00:00Z", "additions": 50, "deletions": 10},
            {"mergedAt": "2026-03-20T14:00:00Z", "additions": 30, "deletions": 5},
            {"mergedAt": "2026-03-21T09:00:00Z", "additions": 100, "deletions": 20},
        ]
        fake_result = type(
            "Result", (), {"stdout": self._mock_gh_output(prs), "returncode": 0}
        )()
        with patch("generate_dashboard.subprocess.run", return_value=fake_result):
            counts, additions, deletions = _gather_pr_counts("/fake/repo")

        assert counts == {"2026-03-20": 2, "2026-03-21": 1}
        assert additions == {"2026-03-20": 80, "2026-03-21": 100}
        assert deletions == {"2026-03-20": 15, "2026-03-21": 20}

    def test_empty_pr_list(self):
        """Empty PR list returns empty dicts."""
        fake_result = type("Result", (), {"stdout": "[]", "returncode": 0})()
        with patch("generate_dashboard.subprocess.run", return_value=fake_result):
            counts, additions, deletions = _gather_pr_counts("/fake/repo")

        assert counts == {}
        assert additions == {}
        assert deletions == {}

    def test_missing_merged_at_skipped(self):
        """PRs with empty mergedAt are silently skipped."""
        prs = [
            {"mergedAt": "", "additions": 50, "deletions": 10},
            {"mergedAt": "2026-03-20T10:00:00Z", "additions": 30, "deletions": 5},
        ]
        fake_result = type(
            "Result", (), {"stdout": self._mock_gh_output(prs), "returncode": 0}
        )()
        with patch("generate_dashboard.subprocess.run", return_value=fake_result):
            counts, additions, deletions = _gather_pr_counts("/fake/repo")

        assert counts == {"2026-03-20": 1}
        assert additions == {"2026-03-20": 30}
        assert deletions == {"2026-03-20": 5}

    def test_warns_when_hitting_limit(self, caplog):
        """Emits a warning when PR count equals _GH_PR_LIMIT."""
        prs = [
            {"mergedAt": f"2026-03-{(i % 28) + 1:02d}T10:00:00Z", "additions": 1}
            for i in range(_GH_PR_LIMIT)
        ]
        fake_result = type(
            "Result", (), {"stdout": self._mock_gh_output(prs), "returncode": 0}
        )()
        with (
            patch("generate_dashboard.subprocess.run", return_value=fake_result),
            caplog.at_level(logging.WARNING),
        ):
            _gather_pr_counts("/fake/repo")

        assert any("truncated" in r.message for r in caplog.records)

    def test_no_warning_below_limit(self, caplog):
        """No warning when PR count is below _GH_PR_LIMIT."""
        prs = [
            {"mergedAt": "2026-03-20T10:00:00Z", "additions": 50},
        ]
        fake_result = type(
            "Result", (), {"stdout": self._mock_gh_output(prs), "returncode": 0}
        )()
        with (
            patch("generate_dashboard.subprocess.run", return_value=fake_result),
            caplog.at_level(logging.WARNING),
        ):
            _gather_pr_counts("/fake/repo")

        assert not any("truncated" in r.message for r in caplog.records)
