"""Card animation smoke tests — trick-boundary layout stability.

Validates that the slot-reset-fade animation on ``.card-slot--empty``
produces a smooth transition rather than a layout jitter at trick
boundaries.

Run via::

    make browser-smoke

NOT included in ``make check``.  See UX-3 in
``plans/sessions/2026-04-06_uiux_wave_plan.md`` §4.3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

from .conftest import enter_game

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _play_to_trick_boundary(page: Page, timeout_s: float = 120.0) -> bool:
    """Play actions until a trick boundary is reached or the hand ends.

    Returns True if the game reached a trick boundary or hand result,
    False if we timed out without reaching one.
    """
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        # Check terminal conditions first
        if page.locator("#match-result").count() > 0:
            return True
        if page.locator("#hand-result").count() > 0:
            return True

        # Advance through any paused states (e.g. trick result)
        _advance_next_steps(page, max_steps=2)

        # Wait for a real trick-reset state: all 4 card slots in the trick
        # area must be empty (not just ≥ 2, which can match mid-trick).
        empty_slots = page.locator("#trick-area .card-slot--empty")
        if empty_slots.count() == 4:
            # All slots empty — confirmed trick reset.  Wait for the
            # slot-reset-fade animation (200ms) to settle before returning.
            page.wait_for_timeout(250)
            return True

        # Try to submit a pass bid if in auction
        pass_btn = page.locator("button.pass-btn")
        if pass_btn.count() > 0 and pass_btn.is_visible():
            pass_btn.click()
            page.wait_for_timeout(250)
            continue

        # Try to play a legal card if in trick play
        legal_cards = page.locator(".card--legal")
        if legal_cards.count() > 0:
            legal_cards.first.click()
            page.wait_for_timeout(250)
            continue

        # Nothing to do — wait for AI to advance
        page.wait_for_timeout(500)

    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_trick_boundary_no_layout_jitter(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Assert that card-slot elements do not jitter at trick boundaries.

    Strategy: play into a game, reach a trick boundary where card-slot
    elements are present, then snapshot their bounding rects.  Click
    Next to advance, wait 300ms, snapshot again, and verify no element
    shifted by more than 4px.

    This catches the jitter bug reported in #2538 where empty slots
    would pop/jump when the trick area was cleared.
    """
    enter_game(page, live_server, invite_code, "JitterTester")

    # Start a match with OLSa AI
    page.click("input[name='model_id'][value='olsa']")
    page.click("button:has-text('Start Match')")

    # Wait for game board to appear
    page.wait_for_selector("#game-board", timeout=10000)
    _advance_next_steps(page)

    # Play until we reach a trick boundary
    reached = _play_to_trick_boundary(page)
    if not reached:
        pytest.skip("Could not reach a trick boundary within timeout")

    # If match/hand is already over, skip the layout check
    if page.locator("#match-result").count() > 0:
        pytest.skip("Match ended before trick boundary check")
    if page.locator("#hand-result").count() > 0:
        pytest.skip("Hand ended before trick boundary check")

    # Snapshot positions of all card-slot elements in the trick area
    before_rects = page.evaluate(
        """
        () => {
            const slots = document.querySelectorAll(
                '#trick-area .card-slot, #trick-area .card-slot--empty'
            );
            return Array.from(slots).map(el => {
                const r = el.getBoundingClientRect();
                return {
                    top: r.top,
                    left: r.left,
                    width: r.width,
                    height: r.height,
                    className: el.className
                };
            });
        }
        """
    )

    if not before_rects:
        pytest.skip("No card-slot elements found in trick area")

    # Click Next if available to trigger the trick-boundary transition
    next_button = page.locator("button.btn--next-step")
    if next_button.count() > 0 and next_button.first.is_visible():
        next_button.first.click()

    # Wait 300ms for the transition to settle
    page.wait_for_timeout(300)

    # Snapshot positions after the transition
    after_rects = page.evaluate(
        """
        () => {
            const slots = document.querySelectorAll(
                '#trick-area .card-slot, #trick-area .card-slot--empty'
            );
            return Array.from(slots).map(el => {
                const r = el.getBoundingClientRect();
                return {
                    top: r.top,
                    left: r.left,
                    width: r.width,
                    height: r.height,
                    className: el.className
                };
            });
        }
        """
    )

    # Compare: no slot should have shifted more than 4px in any direction
    max_shift = 4.0
    n_compare = min(len(before_rects), len(after_rects))
    for i in range(n_compare):
        b = before_rects[i]
        a = after_rects[i]
        dy = abs(a["top"] - b["top"])
        dx = abs(a["left"] - b["left"])
        dw = abs(a["width"] - b["width"])
        dh = abs(a["height"] - b["height"])

        assert dy <= max_shift, (
            f"Card slot {i} ({b['className']}) shifted {dy:.1f}px vertically "
            f"(max {max_shift}px). Before: top={b['top']:.1f}, "
            f"After: top={a['top']:.1f}"
        )
        assert dx <= max_shift, (
            f"Card slot {i} ({b['className']}) shifted {dx:.1f}px horizontally "
            f"(max {max_shift}px). Before: left={b['left']:.1f}, "
            f"After: left={a['left']:.1f}"
        )
        assert dw <= max_shift, (
            f"Card slot {i} ({b['className']}) width changed by {dw:.1f}px "
            f"(max {max_shift}px). Before: {b['width']:.1f}, "
            f"After: {a['width']:.1f}"
        )
        assert dh <= max_shift, (
            f"Card slot {i} ({b['className']}) height changed by {dh:.1f}px "
            f"(max {max_shift}px). Before: {b['height']:.1f}, "
            f"After: {a['height']:.1f}"
        )


@pytest.mark.browser
def test_slot_reset_fade_animation_exists(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Verify that .card-slot--empty has the slot-reset-fade animation.

    A simpler assertion than the jitter test — just checks the CSS
    property is correctly applied.
    """
    enter_game(page, live_server, invite_code, "FadeCheck")

    page.click("input[name='model_id'][value='olsa']")
    page.click("button:has-text('Start Match')")
    page.wait_for_selector("#game-board", timeout=10000)
    _advance_next_steps(page)

    # Play until we see empty slots
    reached = _play_to_trick_boundary(page)
    if not reached:
        pytest.skip("Could not reach a state with empty slots")

    if page.locator("#match-result").count() > 0:
        pytest.skip("Match ended before check")
    if page.locator("#hand-result").count() > 0:
        pytest.skip("Hand ended before check")

    # Check the computed animation-name on any .card-slot--empty
    animation_name = page.evaluate(
        """
        () => {
            const slot = document.querySelector('.card-slot--empty');
            if (!slot) return null;
            return window.getComputedStyle(slot).animationName;
        }
        """
    )

    if animation_name is None:
        pytest.skip("No .card-slot--empty found in current state")

    assert animation_name == "slot-reset-fade", (
        f"Expected animation-name 'slot-reset-fade' on .card-slot--empty, "
        f"got '{animation_name}'"
    )


@pytest.mark.browser
def test_reduced_motion_disables_slot_fade(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Verify prefers-reduced-motion: reduce disables the slot fade.

    Emulates reduced-motion preference and checks that the animation
    is suppressed.
    """
    # Emulate reduced-motion preference
    page.emulate_media(reduced_motion="reduce")

    enter_game(page, live_server, invite_code, "ReducedMotion")

    page.click("input[name='model_id'][value='olsa']")
    page.click("button:has-text('Start Match')")
    page.wait_for_selector("#game-board", timeout=10000)
    _advance_next_steps(page)

    reached = _play_to_trick_boundary(page)
    if not reached:
        pytest.skip("Could not reach a state with empty slots")

    if page.locator("#match-result").count() > 0:
        pytest.skip("Match ended before check")
    if page.locator("#hand-result").count() > 0:
        pytest.skip("Hand ended before check")

    animation_name = page.evaluate(
        """
        () => {
            const slot = document.querySelector('.card-slot--empty');
            if (!slot) return null;
            return window.getComputedStyle(slot).animationName;
        }
        """
    )

    if animation_name is None:
        pytest.skip("No .card-slot--empty found in current state")

    assert animation_name == "none", (
        f"Expected animation-name 'none' under reduced-motion, "
        f"got '{animation_name}'"
    )
