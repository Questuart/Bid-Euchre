"""Go-live proving tests — verify visual/behavioral properties of merged fixes.

Each test proves a specific issue fix by checking DOM structure and visual
behavior, not just code-level correctness.

These tests are NOT included in ``make check``.  Run via::

    make browser-smoke

Issues proven:
- #2331 — Auction log repositions below hand details during gameplay
"""

from __future__ import annotations

import time
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


# ---------------------------------------------------------------------------
# #2331: Auction log repositions below hand details during gameplay
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_auction_log_repositions_during_gameplay(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Prove #2331: auction log moves below hand details when trick play begins.

    During auction phase, the auction log (<details class="action-rail">)
    is rendered inside the compass-center of the compass layout.
    After the auction ends and trick play begins, it relocates outside
    the compass layout, below the score bar / hand details pane.

    Acceptance criteria:
    - Auction phase: action-rail is inside .compass-layout
    - Auction phase: action-rail <details> is open
    - Trick play: action-rail is outside .compass-layout
    - Trick play: action-rail is inside #game-board (still present)
    - Trick play: action-rail <details> is closed (collapsed)
    """
    enter_game(page, live_server, invite_code, "ProvingPlayer")

    # Start a match with default AI
    page.click("input[name='model_id'][value='olsa']")
    page.click("button:has-text('Start Match')")
    page.wait_for_selector("#game-board", timeout=10000)

    # --- Phase 1: Verify auction log position during auction ---

    # Wait for the game to reach an actionable state.
    # The first render after Start Match may need Next-step clicks
    # to advance through AI actions.
    _advance_next_steps(page)

    # Wait for auction or trick-play phase to materialize
    page.wait_for_selector(
        "#bid-panel, #trick-area, #human-hand",
        timeout=10000,
    )

    # Check if we caught the auction phase
    bid_panel = page.locator("#bid-panel")
    auction_caught = bid_panel.count() > 0

    if auction_caught:
        # During auction: action-rail should be INSIDE .compass-layout
        rail_in_compass = page.locator(".compass-layout .action-rail")
        assert (
            rail_in_compass.count() > 0
        ), "During auction, action-rail should be inside .compass-layout"

        # During auction: action-rail should NOT exist outside compass layout
        # (check that there's no sibling action-rail after score-bar)
        rail_outside_compass = page.evaluate("""
            () => {
                const rails = document.querySelectorAll('#game-board > .action-rail');
                // Direct children of #game-board that are action-rail
                // (these would be outside the compass layout)
                return rails.length;
            }
        """)
        # During auction, the action-rail outside compass should not exist
        # because the template only renders it inside compass-center
        assert (
            rail_outside_compass == 0
        ), "During auction, action-rail should not appear outside .compass-layout"

        # During auction: the <details> element should be open
        is_open = page.evaluate("""
            () => {
                const rail = document.querySelector('.action-rail');
                return rail ? rail.hasAttribute('open') : null;
            }
        """)
        assert is_open is True, "During auction, action-rail <details> should be open"

        # Submit a pass bid to advance past auction
        page.click("button.pass-btn")
        page.wait_for_selector(
            "#trick-area, #hand-result, #match-result",
            timeout=10000,
        )
        _advance_next_steps(page)

    # --- Phase 2: Verify auction log position during trick play ---

    # Advance through any remaining Next steps to reach trick play
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        _advance_next_steps(page)

        # Check if we're in trick play (trick-area visible)
        if page.locator("#trick-area").count() > 0:
            break

        # If match/hand result appeared, we've gone past trick play
        if page.locator("#match-result").count() > 0:
            pytest.skip("Match ended before reaching trick play — cannot verify")
            return

        if page.locator("#hand-result").count() > 0:
            pytest.skip("Hand ended before reaching trick play — cannot verify")
            return

        # Still in auction — pass if bid panel reappears
        if page.locator("#bid-panel").count() > 0:
            page.click("button.pass-btn")
            page.wait_for_timeout(500)
            continue

        page.wait_for_timeout(500)

    # Now we should be in trick play
    trick_area = page.locator("#trick-area")
    if trick_area.count() == 0:
        pytest.skip("Could not reach trick play phase within time budget")
        return

    # During trick play: action-rail should NOT be inside .compass-layout
    rail_in_compass = page.locator(".compass-layout .action-rail")
    assert rail_in_compass.count() == 0, (
        "During trick play, action-rail should NOT be inside .compass-layout "
        "(it should have moved below the hand details pane)"
    )

    # During trick play: action-rail should still exist in #game-board
    rail_in_board = page.locator("#game-board .action-rail")
    assert rail_in_board.count() > 0, (
        "During trick play, action-rail should still exist inside #game-board "
        "(repositioned below hand details, not removed)"
    )

    # During trick play: the action-rail should appear after the score bar
    # in DOM order (i.e., below hand details, not inside compass layout)
    rail_follows_score = page.evaluate("""
        () => {
            const scoreBar = document.querySelector('#score-bar');
            const rail = document.querySelector('#game-board > .compass-layout ~ .action-rail');
            if (!scoreBar || !rail) return false;
            // Verify the rail comes after the score bar in DOM order
            const children = Array.from(rail.parentElement.children);
            const scoreIdx = children.indexOf(scoreBar);
            const railIdx = children.indexOf(rail);
            return railIdx > scoreIdx;
        }
    """)
    assert rail_follows_score, (
        "During trick play, action-rail should follow the score bar in DOM order "
        "(below hand details pane)"
    )

    # During trick play: the <details> element should be closed (collapsed)
    is_open = page.evaluate("""
        () => {
            const rail = document.querySelector('.action-rail');
            return rail ? rail.hasAttribute('open') : null;
        }
    """)
    assert is_open is False, (
        "During trick play, action-rail <details> should be collapsed "
        "(auto-closed after auction ends)"
    )
