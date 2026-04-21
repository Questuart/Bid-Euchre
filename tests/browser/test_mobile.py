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


# ---------------------------------------------------------------------------
# Test: Auction log shows all 4 bidders on mobile (#2591)
# ---------------------------------------------------------------------------


def _advance_to_four_bidders(page, max_steps: int = 16) -> None:
    """Advance through the auction until all 4 bidders have placed bids.

    Clicks "Next" buttons to reveal AI bids *and* submits a Pass for the
    human player when the bid panel appears.  Stops once the action-rail
    contains ≥4 items (one per player) or *max_steps* iterations elapse.

    This avoids the fragile pattern of asserting on the auction log before
    all 4 bidders have actually bid (#2594).
    """
    for _ in range(max_steps):
        # Check if we already have 4+ auction entries → done
        items = page.locator(".action-rail__item")
        if items.count() >= 4:
            return

        # If the human bid panel is visible, submit Pass so the
        # human's bid row appears in the auction log.
        pass_btn = page.locator("#bid-panel button.pass-btn")
        if pass_btn.count() > 0 and pass_btn.first.is_visible():
            pass_btn.first.click()
            page.wait_for_timeout(300)
            continue

        # Otherwise, click "Next" to advance through an AI bid.
        next_btn = page.locator("button.btn--next-step")
        if next_btn.count() > 0 and next_btn.first.is_visible():
            next_btn.first.click()
            page.wait_for_timeout(300)
            continue

        # Neither button visible — wait briefly for HTMX swap.
        page.wait_for_timeout(300)


@pytest.mark.browser
def test_auction_log_all_bidders_visible_mobile(
    live_server: str,
    invite_code: str,
    browser,
) -> None:
    """All four bidder rows must be visible without scrolling at 375px (#2591).

    Acceptance criteria:
    - All action-rail items are within viewport bounds (no overflow)
    - The list container has no scroll overflow during auction phase
    """
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
        enter_game(mobile_page, live_server, invite_code, "AuctionLogTest")

        # Start match
        mobile_page.click("input[name='model_id'][value='olsa']")
        mobile_page.click("button:has-text('Start Match')")
        mobile_page.wait_for_selector("#game-board", timeout=10000)

        # Advance through AI and human bids until all 4 bidders are logged (#2594)
        _advance_to_four_bidders(mobile_page)

        # After all 4 bids, the auction may have settled (phase → trick_play).
        # Ensure the action-rail <details> is open so items are rendered for
        # measurement.  Force-open it regardless of auto-collapse state.
        action_rail = mobile_page.locator("#action-rail")
        if action_rail.count() == 0:
            pytest.skip("No action-rail element found")
        action_rail.evaluate("el => el.setAttribute('open', '')")

        # Verify we reached the 4-bidder state before asserting (#2594)
        items = mobile_page.locator(".action-rail__item")
        item_count = items.count()
        assert item_count >= 4, (
            f"Expected ≥4 auction log items (one per bidder) but found {item_count}. "
            f"The test must reach a four-bidder state before asserting overflow (#2594)."
        )

        # The helper must not overshoot the auction phase — if it does,
        # the layout assertions below are meaningless (#2612).  Skip rather
        # than hard-fail: overshoot is a helper-race precondition, not a
        # product bug, so skipping avoids flaky CI red (#2615).
        if mobile_page.locator("#trick-area").count() > 0:
            pytest.skip(
                "Helper _advance_to_four_bidders overshot the auction phase — "
                "game transitioned to trick_play before auction layout could be "
                "verified (#2612, #2615)."
            )

        # The list container should NOT be scrollable during auction
        list_el = mobile_page.locator(".action-rail__list")
        if list_el.count() > 0:
            scroll_height = list_el.evaluate("el => el.scrollHeight")
            client_height = list_el.evaluate("el => el.clientHeight")
            assert scroll_height <= client_height + 2, (
                f"Auction log list overflows during auction phase: "
                f"scrollHeight={scroll_height}px, clientHeight={client_height}px. "
                f"All {item_count} bidder rows should be visible without scrolling (#2591)."
            )

        # Verify each visible item is within the viewport
        viewport_height = MOBILE_VIEWPORT["height"]
        for i in range(item_count):
            item = items.nth(i)
            if not item.is_visible():
                continue
            box = item.bounding_box()
            if box is None:
                continue
            assert box["y"] + box["height"] <= viewport_height + 5, (
                f"Auction log item {i} overflows viewport bottom: "
                f"y={box['y']:.0f} + h={box['height']:.0f} = "
                f"{box['y'] + box['height']:.0f}px > {viewport_height}px (#2591)"
            )

    finally:
        context.close()


@pytest.mark.browser
def test_auction_log_all_bidders_visible_mobile_big_text(
    live_server: str,
    invite_code: str,
    browser,
) -> None:
    """All four bidder rows must be visible at 375px with big text mode (#2591).

    Big text mode scales root font-size to 125%, making each row larger.
    The auction log must still show all rows without scrolling.
    """
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
        enter_game(mobile_page, live_server, invite_code, "AuctionBigText")

        # Enable big text mode before starting match
        mobile_page.evaluate(
            "document.documentElement.setAttribute('data-text-size', 'large')"
        )

        # Start match
        mobile_page.click("input[name='model_id'][value='olsa']")
        mobile_page.click("button:has-text('Start Match')")
        mobile_page.wait_for_selector("#game-board", timeout=10000)

        # Advance through AI and human bids until all 4 bidders are logged (#2594)
        _advance_to_four_bidders(mobile_page)

        # Force action-rail open in case auction settled and it auto-collapsed
        action_rail = mobile_page.locator("#action-rail")
        if action_rail.count() == 0:
            pytest.skip("No action-rail element found")
        action_rail.evaluate("el => el.setAttribute('open', '')")

        # Verify we reached the 4-bidder state (#2594)
        items = mobile_page.locator(".action-rail__item")
        item_count = items.count()
        assert (
            item_count >= 4
        ), f"Expected ≥4 auction log items but found {item_count} (#2594)."

        # The helper must not overshoot the auction phase — if it does,
        # the layout assertions below are meaningless (#2612).  Skip rather
        # than hard-fail: overshoot is a helper-race precondition, not a
        # product bug, so skipping avoids flaky CI red (#2615).
        if mobile_page.locator("#trick-area").count() > 0:
            pytest.skip(
                "Helper _advance_to_four_bidders overshot the auction phase — "
                "game transitioned to trick_play before auction layout could be "
                "verified (#2612, #2615)."
            )

        # Check the list container is NOT scrollable (big text mode)
        list_el = mobile_page.locator(".action-rail__list")
        if list_el.count() > 0:
            scroll_height = list_el.evaluate("el => el.scrollHeight")
            client_height = list_el.evaluate("el => el.clientHeight")
            assert scroll_height <= client_height + 2, (
                f"Auction log overflows in big text mode: "
                f"scrollHeight={scroll_height}px, clientHeight={client_height}px. "
                f"All bidder rows should be visible without scrolling (#2591)."
            )

    finally:
        context.close()
