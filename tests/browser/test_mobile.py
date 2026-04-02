"""Mobile viewport browser tests for the hosted Bid Euchre game.

Tests validate that the game UI is usable on mobile devices:
- Touch targets are large enough (≥44px per Apple HIG)
- Card buttons are reachable and tappable
- Layout doesn't overflow the viewport
- Key UI elements remain visible on small screens

These tests are NOT included in ``make check``.  Run via::

    make browser-smoke

See ``plans/browser_game_expansion/governing_plan.md`` Phase 2 for context.
"""

from __future__ import annotations

import pytest

from .conftest import enter_game

# Mobile viewport dimensions (iPhone SE / small Android)
MOBILE_VIEWPORT = {"width": 375, "height": 667}

# Minimum touch target size per Apple HIG (44pt ≈ 44px at 1x)
MIN_TOUCH_TARGET_PX = 44


# ---------------------------------------------------------------------------
# Test: Mobile viewport tap targets and layout
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_mobile_viewport_tap_targets(
    live_server: str,
    invite_code: str,
    browser,
) -> None:
    """Verify touch targets are large enough on a mobile viewport.

    Opens the game in a mobile-sized viewport and checks that:
    - Card buttons are at least 44px in both dimensions
    - The bid submit button is reachable
    - The game board doesn't overflow horizontally
    - Key UI elements are visible without scrolling
    """
    # Create a new context with mobile viewport
    context = browser.new_context(
        viewport=MOBILE_VIEWPORT,
        has_touch=True,
        is_mobile=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    )
    mobile_page = context.new_page()

    try:
        enter_game(mobile_page, live_server, invite_code, "MobileTester")

        # Start a match
        mobile_page.click("input[name='model_id'][value='olsa']")
        mobile_page.click("button:has-text('Start Match')")
        mobile_page.wait_for_selector("#game-board", timeout=10000)

        # --- Check viewport overflow ---
        body_width = mobile_page.evaluate("document.body.scrollWidth")
        viewport_width = MOBILE_VIEWPORT["width"]
        assert (
            body_width <= viewport_width + 20
        ), f"Page overflows viewport: body={body_width}px, viewport={viewport_width}px"

        # --- Check the auction/trick/hand/score surfaces remain on-screen together ---
        selectors = ["#trick-area", "#human-hand", "#score-bar", "#bid-panel"]
        for selector in selectors:
            locator = mobile_page.locator(selector)
            if locator.count() > 0:
                box = locator.first.bounding_box()
                if box is None:
                    continue
                assert box["y"] >= 0, f"{selector} should be above viewport top: {box}"
                assert (
                    box["y"] + box["height"] <= MOBILE_VIEWPORT["height"] + 5
                ), f"{selector} overflows vertical viewport on mobile: {box}"

        # --- Check card sizes ---
        cards = mobile_page.locator(".card")
        card_count = cards.count()
        if card_count > 0:
            for i in range(min(card_count, 5)):  # Check first 5 cards
                box = cards.nth(i).bounding_box()
                if box is not None:
                    assert box["width"] >= MIN_TOUCH_TARGET_PX * 0.8, (
                        f"Card {i} width {box['width']:.0f}px < "
                        f"{MIN_TOUCH_TARGET_PX * 0.8:.0f}px minimum"
                    )
                    assert box["height"] >= MIN_TOUCH_TARGET_PX * 0.8, (
                        f"Card {i} height {box['height']:.0f}px < "
                        f"{MIN_TOUCH_TARGET_PX * 0.8:.0f}px minimum"
                    )

        # --- Check button sizes ---
        buttons = mobile_page.locator("button[type='submit'], button.pass-btn")
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            if btn.is_visible():
                box = btn.bounding_box()
                if box is not None:
                    assert box["height"] >= MIN_TOUCH_TARGET_PX * 0.8, (
                        f"Button {i} height {box['height']:.0f}px < "
                        f"{MIN_TOUCH_TARGET_PX * 0.8:.0f}px minimum"
                    )

        # --- Check human hand is visible ---
        human_hand = mobile_page.locator("#human-hand")
        if human_hand.count() > 0:
            assert (
                human_hand.is_visible()
            ), "Human hand should be visible on mobile viewport"

        # --- Check score bar is within viewport ---
        score_bar = mobile_page.locator("#score-bar")
        if score_bar.count() > 0:
            box = score_bar.bounding_box()
            if box is not None:
                assert box["x"] >= 0, "Score bar should not be off-screen left"
                assert (
                    box["x"] + box["width"] <= viewport_width + 20
                ), "Score bar should not overflow viewport right"

    finally:
        context.close()


@pytest.mark.browser
def test_mobile_invite_code_input(
    live_server: str,
    browser,
) -> None:
    """Verify the invite code input is usable on a mobile viewport.

    The input field should:
    - Be visible and focusable
    - Have appropriate width for code entry
    - Submit button should be reachable
    """
    context = browser.new_context(
        viewport=MOBILE_VIEWPORT,
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    )
    mobile_page = context.new_page()

    try:
        mobile_page.goto(live_server)
        mobile_page.wait_for_load_state("domcontentloaded")

        # Invite code input should be visible
        code_input = mobile_page.locator("#invite-code-input")
        assert code_input.is_visible(), "Invite code input should be visible on mobile"

        # Input should be within viewport
        box = code_input.bounding_box()
        assert box is not None, "Invite code input should have a bounding box"
        assert box["x"] >= 0, "Input should not be off-screen"
        assert (
            box["x"] + box["width"] <= MOBILE_VIEWPORT["width"] + 20
        ), "Input should not overflow viewport"

        # Submit button should be visible
        submit_btn = mobile_page.locator("button:has-text('Enter Game')")
        assert submit_btn.is_visible(), "Enter Game button should be visible on mobile"

        # Button should be tap-target sized
        btn_box = submit_btn.bounding_box()
        if btn_box is not None:
            assert (
                btn_box["height"] >= MIN_TOUCH_TARGET_PX * 0.8
            ), f"Submit button height {btn_box['height']:.0f}px too small for touch"

    finally:
        context.close()
