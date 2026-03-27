"""Browser smoke suite — 5 critical paths for the hosted Bid Euchre game.

Tests exercise the full browser flow through Playwright against a live
FastAPI server.  They validate:

1. Start game → bid → play trick → verify score
2. Moon bid submission → verify moon-specific UI
3. Invite code → join game → verify nickname
4. Full hand → verify hand-result transition
5. Landing page → invalid code → error display

These tests are NOT included in ``make check``.  Run via::

    make browser-smoke

See ``plans/browser_game_expansion/governing_plan.md`` Phase 4 for context.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

from .conftest import enter_game

# Lazy import — only used at runtime when playwright is available
_expect = None


def _get_expect():
    """Lazy-load playwright's expect to avoid import errors."""
    global _expect
    if _expect is None:
        from playwright.sync_api import expect

        _expect = expect
    return _expect


def _current_hand_number(page: Page) -> int | None:
    """Extract the visible hand number from the score bar."""
    hand_info = page.locator("#score-bar .hand-info")
    if hand_info.count() > 0:
        text = hand_info.inner_text()
    else:
        game_board = page.locator("#game-board")
        if game_board.count() == 0:
            return None
        text = game_board.inner_text()
    match = re.search(r"Hand\s+(\d+)", text)
    if match is None:
        return None
    return int(match.group(1))


def _wait_for_hand_number(page: Page, timeout_ms: int = 10000) -> int:
    """Wait until the game board exposes a visible hand number."""
    page.wait_for_function(
        """
        () => {
            const board = document.querySelector('#game-board');
            return !!board && /Hand\\s+\\d+/.test(board.innerText);
        }
        """,
        timeout=timeout_ms,
    )
    hand_number = _current_hand_number(page)
    assert hand_number is not None, "Expected score bar hand number to render"
    return hand_number


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
# Test 1: Start game → bid → play trick → verify score
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_start_game_bid_play_verify_score(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Full happy path: invite → nickname → select AI → bid → play → score.

    Validates that:
    - The invite code flow works end to end
    - Model selection starts a match
    - Auction phase shows bid controls
    - A pass bid can be submitted
    - The game advances through AI turns
    - The score bar is visible during play
    """
    enter_game(page, live_server, invite_code, "SmokePlayer")

    # Select the default OLSa AI model and start match
    page.select_option("select[name='model_id']", "olsa")
    page.click("button:has-text('Start Match')")

    # Wait for the game board to show auction or trick play
    # (AI may auto-advance through auction before we see it)
    page.wait_for_selector("#game-board", timeout=10000)

    # The game should be in one of the active phases
    game_board = page.locator("#game-board")
    game_board.wait_for(timeout=10000)

    # The game can transition from invite -> model select directly to trick
    # play, so wait for the first meaningful active-phase element before
    # asserting. This avoids a flake window where selectors have not
    # materialized yet immediately after Start Match.
    _advance_next_steps(page)
    page.wait_for_selector(
        "#bid-panel, #trick-area, #human-hand, #score-bar, #match-result, #hand-result",
        timeout=10000,
    )

    # Check that we have either the bid panel or trick area
    # (depends on whether AI has already bid)
    has_bid_panel = page.locator("#bid-panel").count() > 0
    has_trick_area = page.locator("#trick-area").count() > 0
    has_hand = page.locator("#human-hand").count() > 0

    assert (
        has_bid_panel or has_trick_area
    ), "Expected bid panel or trick area after starting match"
    assert has_hand, "Expected human hand to be visible"

    # If in auction, submit a pass bid
    if has_bid_panel:
        page.click("button.pass-btn")
        # Wait for post-auction state — exclude #bid-panel since it is
        # already visible and would make the wait resolve immediately
        # before the HTMX swap completes.
        page.wait_for_selector(
            "#trick-area, #hand-result, #match-result",
            timeout=10000,
        )
        _advance_next_steps(page)

    # Verify score bar is present during play
    score_bar = page.locator("#score-bar")
    if score_bar.count() > 0:
        # Score bar should contain "You:" and "AI:" labels
        score_text = score_bar.inner_text()
        assert "You:" in score_text, f"Expected 'You:' in score bar, got: {score_text}"
        assert "AI:" in score_text, f"Expected 'AI:' in score bar, got: {score_text}"

    # If in trick play, play a card
    legal_cards = page.locator(".card--legal")
    if legal_cards.count() > 0:
        legal_cards.first.click()
        # Wait for the board to update (HTMX swap)
        page.wait_for_selector(
            "#trick-area, #hand-result, #match-result, #score-bar",
            timeout=10000,
        )
        _advance_next_steps(page)

    # Verify the game is still running (board has content)
    assert (
        page.locator("#game-board").inner_html().strip()
    ), "Game board should not be empty after playing"


# ---------------------------------------------------------------------------
# Test 2: Moon bid UI availability
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_moon_bid_ui_available(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Verify the moon bid option is available in the auction UI.

    The bid panel should include the Moon option in the bid type selector.
    We verify the UI structure rather than making a specific game-state
    dependent assertion about scoring, since the dealt hand is random.
    """
    enter_game(page, live_server, invite_code, "MoonTester")

    # Start a match
    page.select_option("select[name='model_id']", "olsa")
    page.click("button:has-text('Start Match')")
    _advance_next_steps(page)
    page.wait_for_function(
        """
        () => {
            const board = document.querySelector('#game-board');
            if (!board) return false;
            return /Hand\\s+\\d+/.test(board.innerText) ||
                document.querySelector('#match-result') !== null;
        }
        """,
        timeout=10000,
    )

    # If we're in auction phase, check for moon option
    bid_panel = page.locator("#bid-panel")
    if bid_panel.count() > 0:
        # The bid type selector should have Moon and Loner options
        bid_type_select = page.locator("#bid-type")
        _get_expect()(bid_type_select).to_be_visible()

        # Verify Moon option exists
        moon_option = bid_type_select.locator("option[value='moon']")
        assert moon_option.count() > 0, "Moon option should exist in bid type selector"

        # Verify Loner option exists
        loner_option = bid_type_select.locator("option[value='loner']")
        assert (
            loner_option.count() > 0
        ), "Loner option should exist in bid type selector"

        # Select Moon and verify the bid level wrapper hides
        bid_type_select.select_option("moon")
        bid_type_select.dispatch_event("change")

        # Moon is always level 10, so the level selector should be hidden
        level_wrapper = page.locator("#bid-level-wrapper")
        # The JS hides it via display:none
        is_hidden = level_wrapper.evaluate(
            "el => window.getComputedStyle(el).display === 'none'"
        )
        assert is_hidden, "Bid level wrapper should be hidden when Moon is selected"


# ---------------------------------------------------------------------------
# Test 3: Invite code → join game → verify nickname
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_invite_code_join_verify_nickname(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Verify the invite code → nickname → game flow displays the nickname.

    Validates that:
    - The landing page shows the invite code form
    - A valid code redirects to the game page
    - The nickname form appears and accepts input
    - After setting nickname, the model select screen greets the player
    """
    # Navigate to landing page
    page.goto(live_server)
    page.wait_for_load_state("domcontentloaded")

    # Verify landing page structure
    _get_expect()(page.locator("#invite-code-form")).to_be_visible()
    _get_expect()(page.locator("#invite-code-input")).to_be_visible()

    # Enter invite code
    page.fill("#invite-code-input", invite_code)
    page.click("button:has-text('Enter Game')")

    # Wait for redirect to play page
    page.wait_for_url("**/play/**", timeout=5000)

    # Should see nickname form
    _get_expect()(page.locator("#nickname-form")).to_be_visible()
    _get_expect()(page.locator("#nickname-input")).to_be_visible()

    # Set nickname
    test_nickname = "TestNickname42"
    page.fill("#nickname-input", test_nickname)
    page.click("button:has-text('Set Nickname')")

    # Wait for model selection to appear
    page.wait_for_selector("#model-select", timeout=5000)

    # Verify the welcome message includes the nickname
    welcome_text = page.locator("#model-select h2").inner_text()
    assert (
        test_nickname in welcome_text
    ), f"Expected nickname '{test_nickname}' in welcome text, got: {welcome_text}"


# ---------------------------------------------------------------------------
# Test 4: Full hand → verify hand-result transition
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_full_hand_verify_transition(
    page: Page,
    live_server: str,
    invite_code: str,
) -> None:
    """Play through a complete hand and verify the hand result screen appears.

    This test starts a game and repeatedly submits actions (pass bids and
    card plays) until the hand completes, then verifies the hand-result
    transition UI displays correctly.

    Note: This test may take a while due to the full hand flow. Timeout
    is generous to accommodate AI thinking time.
    """
    enter_game(page, live_server, invite_code, "HandFlowTester")

    # Start a match
    page.select_option("select[name='model_id']", "olsa")
    page.click("button:has-text('Start Match')")
    initial_hand_number = _wait_for_hand_number(page)

    # Play through the hand by repeatedly taking actions. The current product
    # auto-deals the next hand immediately after scoring, so the observable
    # success condition is either a match result or the visible hand number
    # advancing beyond the starting hand.
    deadline = time.monotonic() + 180.0
    actions_taken = 0
    hand_complete = False

    while time.monotonic() < deadline:
        actions_taken += 1
        # Check if match result is showing (match ended)
        if page.locator("#match-result").count() > 0:
            hand_complete = True
            break

        # Hand result is now the expected intermediate state before advancing.
        if page.locator("#hand-result").count() > 0:
            hand_complete = True
            break

        current_hand_number = _current_hand_number(page)
        if (
            current_hand_number is not None
            and current_hand_number > initial_hand_number
        ):
            hand_complete = True
            break

        hand_result = page.locator("#hand-result")
        if hand_result.count() > 0:
            next_hand_button = hand_result.locator(".btn--next-hand")
            if next_hand_button.count() > 0:
                next_hand_button.click()
                page.wait_for_timeout(350)
                continue
            hand_complete = True
            break

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

    assert hand_complete, (
        "Expected hand to complete within time budget. "
        f"Actions taken: {actions_taken}. "
        f"Current page content: {page.locator('#game-board').inner_text()[:200]}"
    )

    # If the match ended outright, match-result checks are sufficient.
    if page.locator("#match-result").count() > 0:
        return

    # Verify hand-result rendered, then click through to next hand.
    hand_result = page.locator("#hand-result")
    _get_expect()(hand_result).to_be_visible(timeout=5000)
    next_hand_button = page.locator(
        "#hand-result button:has-text('Next Hand'), button:has-text('Next Hand')"
    )
    _get_expect()(next_hand_button).to_be_visible(timeout=5000)
    next_hand_button.first.click()

    # Next hand should render as active hand state.
    page.wait_for_selector("#game-board", timeout=10000)
    next_hand_number = _wait_for_hand_number(page)
    assert next_hand_number >= initial_hand_number + 1

    # Ensure we can see trick/auction/play controls after advancing.
    page.wait_for_selector("#trick-area, #bid-panel", timeout=10000)

    # If we got a hand result, verify its structure
    hand_result = page.locator("#hand-result")
    if hand_result.count() > 0:
        # Should show a result title (Made/Set/Moon/Loner)
        result_title = page.locator(".result-title")
        assert result_title.count() > 0, "Hand result should have a result title"
        title_text = result_title.inner_text()
        assert any(
            kw in title_text for kw in ["Made", "Set", "Moon", "Loner", "Win", "Lose"]
        ), f"Unexpected result title: {title_text}"

        # Should show scoring details
        result_table = page.locator(".result-table, .score-table")
        assert result_table.count() > 0, "Hand result should show scoring table"

        # Should show match score
        match_score = page.locator(".result-match-score, .final-score")
        assert match_score.count() > 0, "Hand result should show match score"


# ---------------------------------------------------------------------------
# Test 5: Invalid invite code shows error
# ---------------------------------------------------------------------------


@pytest.mark.browser
def test_invalid_invite_code_shows_error(
    page: Page,
    live_server: str,
) -> None:
    """Verify that entering an invalid invite code shows an error message.

    This is a negative path test ensuring the access control system
    provides clear feedback for bad codes.
    """
    page.goto(live_server)
    page.wait_for_load_state("domcontentloaded")

    # Enter an invalid code
    page.fill("#invite-code-input", "INVALID9")
    page.click("button:has-text('Enter Game')")

    # The error message should be visible
    error_div = page.locator(".invite-error")
    _get_expect()(error_div).to_be_visible(timeout=5000)

    error_text = error_div.inner_text()
    assert (
        "Invalid" in error_text or "invalid" in error_text
    ), f"Expected 'Invalid' in error message, got: {error_text}"

    # Should still be on the landing page (not redirected)
    assert (
        "/play/" not in page.url
    ), f"Should not redirect with invalid code, but URL is: {page.url}"
