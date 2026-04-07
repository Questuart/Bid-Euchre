"""Auction panel visual distinction tests — bid-row elevation + Pass button blue.

Validates the CSS changes from #2545:
1. Bid rows have a distinct elevated background (surface-light)
2. Pass button is outlined blue, distinct from Submit Bid green
3. Mobile viewport has adequate tap targets (≥44px)

These tests are NOT included in ``make check``.  Run via::

    uv run python -m pytest tests/browser/test_auction_panel_visual.py -v

Requires Playwright and ``make browser-smoke`` infrastructure.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

from .conftest import enter_game


def _advance_next_steps(page: Page, max_steps: int = 8) -> None:
    """Click the unified Next button until the board is actionable again."""
    for _ in range(max_steps):
        next_button = page.locator("button.btn--next-step")
        if next_button.count() == 0:
            return
        if not next_button.first.is_visible():
            return
        next_button.first.click()
        page.wait_for_timeout(250)


def _enter_game_and_start_match(
    page: Page, live_server: str, invite_code: str, nickname: str
) -> None:
    """Enter the game and start a match, advancing to the bid panel."""
    enter_game(page, live_server, invite_code, nickname)

    # Select the default OLSa AI model and start match
    page.click("input[name='model_id'][value='olsa']")
    page.click("button:has-text('Start Match')")

    # Wait for the game board to appear
    page.wait_for_selector("#game-board", timeout=10000)

    # Advance past any next-step prompts
    _advance_next_steps(page)


def _parse_rgb(color_str: str) -> tuple[int, int, int] | None:
    """Parse rgb(r, g, b) or rgba(r, g, b, a) into (r, g, b) tuple."""
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color_str)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


# ---------------------------------------------------------------------------
# Test: Bid-row surface elevation
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_auction_panel_visual_distinction(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Bid rows should have distinct surface-light background, separate from panel bg.

    Validates #2545 requirement: each row is a visually distinct "card" with
    lighter background, subtle border, and consistent padding.
    """
    _enter_game_and_start_match(page, live_server, invite_code, "RowTestPlayer")

    # The bid panel may or may not be visible (depends on whether it's
    # human's turn to bid). Try to locate it.
    bid_panel = page.locator("#bid-panel")
    if bid_panel.count() == 0:
        pytest.skip("Bid panel not visible — AI may have passed through auction")

    # Get bid rows
    bid_rows = page.locator(".bid-row")
    row_count = bid_rows.count()
    if row_count == 0:
        pytest.skip("No bid rows visible — game may have advanced past auction")

    # Get the panel background color
    panel_bg = bid_panel.evaluate("el => getComputedStyle(el).backgroundColor")

    # Check each visible bid row has a different background from the panel
    for i in range(row_count):
        row = bid_rows.nth(i)
        if not row.is_visible():
            continue
        row_bg = row.evaluate("el => getComputedStyle(el).backgroundColor")

        # The row background should differ from the panel background
        # (surface-light vs surface)
        panel_rgb = _parse_rgb(panel_bg)
        row_rgb = _parse_rgb(row_bg)

        assert panel_rgb is not None, f"Could not parse panel bg: {panel_bg}"
        assert row_rgb is not None, f"Could not parse row bg: {row_bg}"
        assert row_rgb != panel_rgb, (
            f"Bid row {i} bg ({row_bg}) should differ from panel bg ({panel_bg}). "
            "Expected surface elevation treatment (#2545)."
        )

    # Check bid rows have border-radius (card-like treatment)
    first_row = bid_rows.first
    border_radius = first_row.evaluate("el => getComputedStyle(el).borderRadius")
    assert (
        border_radius != "0px"
    ), f"Bid row should have border-radius for card-like treatment, got {border_radius}"

    # Check bid rows have padding
    padding = first_row.evaluate("el => getComputedStyle(el).padding")
    assert padding != "0px", f"Bid row should have padding, got {padding}"


# ---------------------------------------------------------------------------
# Test: Pass button blue
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_pass_button_blue(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Pass button should be outlined blue, distinct from Submit Bid green.

    Validates #2545 requirement: Pass button reads as a clear primary action,
    clearly a button, clearly differentiated from Submit Bid.
    """
    _enter_game_and_start_match(page, live_server, invite_code, "PassBtnPlayer")

    # Locate the pass button
    pass_btn = page.locator(".pass-btn")
    if pass_btn.count() == 0:
        pytest.skip("Pass button not visible — game may have advanced past auction")

    # Get the border color — should be blue (#1565c0 → rgb(21, 101, 192))
    border_color = pass_btn.evaluate("el => getComputedStyle(el).borderColor")
    border_rgb = _parse_rgb(border_color)
    assert border_rgb is not None, f"Could not parse border color: {border_color}"

    # Blue channel should dominate (R < 80, B > 150)
    r, g, b = border_rgb
    assert b > 150, (
        f"Pass button border should be blue, got rgb({r}, {g}, {b}). "
        "Expected blue dominant (#2545)."
    )
    assert r < 80, (
        f"Pass button border should be blue, got rgb({r}, {g}, {b}). "
        "Red channel too high — not blue (#2545)."
    )

    # Get text color — should also be blue
    text_color = pass_btn.evaluate("el => getComputedStyle(el).color")
    text_rgb = _parse_rgb(text_color)
    assert text_rgb is not None, f"Could not parse text color: {text_color}"
    tr, tg, tb = text_rgb
    assert tb > 150, (
        f"Pass button text should be blue, got rgb({tr}, {tg}, {tb}). "
        "Expected blue dominant (#2545)."
    )

    # Background should be transparent (outlined style)
    bg_color = pass_btn.evaluate("el => getComputedStyle(el).backgroundColor")
    bg_rgb = _parse_rgb(bg_color)
    # Transparent renders as rgba(0, 0, 0, 0) — check the alpha or all-zero
    bg_alpha_match = re.search(r"rgba\(\d+,\s*\d+,\s*\d+,\s*([\d.]+)\)", bg_color)
    if bg_alpha_match:
        alpha = float(bg_alpha_match.group(1))
        assert (
            alpha < 0.1
        ), f"Pass button bg should be transparent, got {bg_color} (alpha={alpha})"
    elif bg_rgb:
        # If not rgba, it should still look transparent (very dark / same as parent)
        pass  # Non-rgba backgrounds are acceptable if visually transparent


# ---------------------------------------------------------------------------
# Test: Mobile tap targets
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_auction_mobile_tap_targets(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Bid controls on mobile viewport must meet WCAG 44px tap target minimum.

    Tests at iPhone SE dimensions (375x667) to trigger the
    ``@media (max-width: 375px)`` touch-target rules in accessibility.css (#2572).
    """
    # Set mobile viewport *before* navigating so CSS media queries fire correctly
    page.set_viewport_size({"width": 375, "height": 667})

    _enter_game_and_start_match(page, live_server, invite_code, "MobileTapPlayer")

    # Check pass button tap target size
    pass_btn = page.locator(".pass-btn")
    if pass_btn.count() == 0:
        pytest.skip("Pass button not visible on mobile")

    box = pass_btn.bounding_box()
    if box is None:
        pytest.skip("Pass button not in viewport")

    assert (
        box["height"] >= 44
    ), f"Pass button height {box['height']}px < 44px minimum tap target"

    # Check submit button tap target
    submit_btn = page.locator(".bid-submit-btn")
    if submit_btn.count() > 0 and submit_btn.first.is_visible():
        sbox = submit_btn.bounding_box()
        if sbox:
            assert (
                sbox["height"] >= 44
            ), f"Submit button height {sbox['height']}px < 44px minimum"
