# Testing & Evaluation Plan — Session 2026-04-02e

> **Scope:** All PRs produced during the 2026-04-02e afternoon fleet run.
> **Author:** analyst-c | **Date:** 2026-04-02
> **Goal:** A QA-engineer-ready plan with concrete pass/fail criteria for every change.

---

## Table of Contents

1. [PR #2126 — Glutton Bower Lifecycle Hook Fix](#pr-2126--glutton-bower-lifecycle-hook-fix)
2. [PR #2137 — Moon Counterfactual 3-Player Trick Tests](#pr-2137--moon-counterfactual-3-player-trick-tests)
3. [PR #2142 — False-Stall Detection Fix](#pr-2142--false-stall-detection-fix)
4. [PR #2143 — Comment Board Timestamps to Local Timezone](#pr-2143--comment-board-timestamps-to-local-timezone)
5. [PR #2145 — XSS Escaping Tests for Comments](#pr-2145--xss-escaping-tests-for-comments)
6. [PR #2146 — Comment Validation Error Messages](#pr-2146--comment-validation-error-messages)
7. [PR #2147 — New Player Guide](#pr-2147--new-player-guide)
8. [PR #2138 — Glutton Bower Validation Experiment (OPEN)](#pr-2138--glutton-bower-validation-experiment-open)
9. [PR #2140 — Auction UX Fix (OPEN)](#pr-2140--auction-ux-fix-open)
10. [PR #2141 — Glutton Low Contract Defense-in-Depth Sync (OPEN)](#pr-2141--glutton-low-contract-defense-in-depth-sync-open)
11. [Cross-PR Interaction Analysis](#cross-pr-interaction-analysis)
12. [Multi-PR Proving Scenarios](#multi-pr-proving-scenarios)
13. [Render Deployment Verification](#render-deployment-verification)
14. [Open PR Merge Order Recommendation](#open-pr-merge-order-recommendation)

---

## PR #2126 — Glutton Bower Lifecycle Hook Fix

### What Changed

Added `_fire_on_hand_start()` and `_fire_observe_play()` helper methods to `MatchEngine` in `src/bid_euchre/hosted_play/engine.py`. These fire after auction completion and after moon exchange, notifying `GluttonStrategy` of the contract type and trump suit. Previously, the hosted-play engine never called `on_hand_start()`, so GluttonStrategy defaulted to `contract_type="high"` / `trump_suit=None` — causing bowers (Jacks of trump and same-color suit) to be valued as low cards instead of the highest trump. The AI was effectively "discarding" right and left bowers on tricks already won by partner.

### Why It Matters

**Risk: HIGH (gameplay correctness).** This was the most impactful bug in the browser game. Without this fix, the AI consistently loses suit contract hands by misvaluing its two strongest cards. Players reported winning 8-2 routinely, making the game uncompetitive.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Suit contract bower play** | Start a match on Render. Play until a suit contract is won. Watch AI play in a trick where a bower is in their hand. | AI should play bowers strategically — leading with them as high trump or holding them, NOT dumping them on partner's won tricks. | |
| 2 | **Multiple suit contracts** | Play 3+ suit contract hands (any trump suit). Note the AI trick counts. | AI should win ~4-6 tricks per hand on average, not consistently 2-3. | |
| 3 | **High contract unaffected** | Play a "High" contract hand. | AI should play normally — bowers are just regular Jacks in high contracts. No behavioral change expected. | |
| 4 | **Low contract unaffected** | Play a "Low" contract hand. | AI plays normally — bowers are regular Jacks. No behavioral change. | |
| 5 | **Moon contract hooks fire** | Win a moon bid (bid 10). Complete the exchange. Watch AI play. | AI should play bowers correctly after moon exchange. The `_fire_on_hand_start` also fires post-exchange (line 373-375 of engine.py). | |
| 6 | **Leaderboard check** | After 3+ games, check the leaderboard. | AI win rate should be more competitive (not 20-80% human). Exact threshold varies but AI should win some hands. | |

### Automated Test Coverage

**Existing tests (4 new in this PR):**
- `TestGluttonBowerFix` in `tests/unit/hosted_play/test_engine.py`
  - Tests that `on_hand_start` fires with correct contract/trump info
  - Tests that bowers are valued correctly after hook fires

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_engine.py -k TestGluttonBowerFix -v
```

**Coverage gaps:**
- No test verifies `_fire_observe_play` is called after every card play (both human and AI). The PR adds the hook but only tests `on_hand_start`.
- No integration test that plays a full hand and checks bower plays are strategically correct (unit tests check hook wiring, not downstream play quality).
- No test for the moon exchange path (`_fire_on_hand_start` at line 373-375).

### Edge Cases to Probe

- **Redeal after all-pass:** Does `on_hand_start` fire correctly on the new hand after a redeal? The hooks fire in `_process_auction_end` — if all players pass, there's no auction winner, so the hooks shouldn't fire (and don't need to since there's no trick play).
- **Serialization round-trip:** If a game is saved and restored mid-hand, does the strategy still have the correct contract info? `_fire_on_hand_start` is called in `_process_auction_end`, which runs before trick play. On deserialization, `on_hand_start` is NOT re-fired. If the user refreshes the page mid-hand, the strategy instance is rebuilt from scratch — **potential gap**: the strategy may lose its `_contract_type`/`_trump_suit` state. However, PR #2141 addresses this with defense-in-depth sync.
- **Sitting-out seat in moon:** The code picks `ai_seat` as the first non-human, non-sitting-out seat (line 841-845). Verify this works for all 4 possible sitting-out seats.

### Render vs Localhost

- Manual scenarios 1-6: **Both** (localhost for fast iteration, Render for production confirmation)
- Automated tests: **Localhost only**

---

## PR #2137 — Moon Counterfactual 3-Player Trick Tests

### What Changed

Added 4 new test methods to `TestSimulateMoonCounterfactual` in `tests/unit/test_action_value_dataset.py`. These tests verify that the moon counterfactual simulation (introduced in PR #2114) correctly uses 3-player trick play (`_play_tricks_loner`) instead of 4-player (`_play_tricks`), and that the partner seat is properly excluded.

### Why It Matters

**Risk: LOW (test-only).** No production code changed. This locks the correctness fix from PR #2114 so future refactors can't silently regress the moon simulation. Critical for dataset quality — incorrect moon counterfactuals would contaminate training data.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Run the test suite** | `uv run python -m pytest tests/unit/test_action_value_dataset.py::TestSimulateMoonCounterfactual -v` | All 4 new tests pass (plus existing tests). | |

### Automated Test Coverage

**New tests:**
- `test_moon_uses_3_player_trick_play` — mock spy verifies `_play_tricks_loner` is called
- `test_moon_partner_sits_out` — verifies correct partner seat (focal+2 mod 4) for all 4 focal seats
- `test_moon_3_player_tricks_exclude_partner` — instruments `trick_winner` to verify 3 plays per trick
- `test_moon_counterfactual_3_player_all_contract_types` — same verification across suit/high/low

**Verification command:**
```bash
uv run python -m pytest tests/unit/test_action_value_dataset.py::TestSimulateMoonCounterfactual -v
# Expected: all tests pass (was 92, now 96)
```

**Coverage gaps:** None identified — this is a test-only PR filling a gap flagged in issue #2120.

### Edge Cases to Probe

- None — test-only PR. The production code being tested was shipped in PR #2114.

### Render vs Localhost

- **Localhost only** — no production impact.

---

## PR #2142 — False-Stall Detection Fix

### What Changed

Four changes to `src/bid_euchre/ops/monitor.py`:
1. Increased `_ACTIVITY_TAIL_LINES` from 5 to 20 — the activity scanner now checks 20 lines instead of 5, catching Bash tool spinners that scroll off the visible prompt area.
2. Added `-S -50` flag to `tmux capture-pane` for scrollback inclusion.
3. Added `make check` / validation progress patterns (`Running full check`, `Waiting for slot`, `check-gated`, `check-quiet`) to `_ACTIVE_WORK_PATTERNS`.
4. Added `_detect_background_validation()` — process-tree detection that checks for running `make`/`pytest`/`ruff` processes under the lane's pane PID, immune to TUI rendering differences.

### Why It Matters

**Risk: LOW (ops infrastructure only).** The orchestrator was repeatedly misdiagnosing lanes running `make check` as "stalled," causing premature redispatches and wasted context. This fix has no gameplay or strategy impact but significantly improves fleet reliability.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Lane running make check** | Start `make check-gated` in an author lane. Run the orchestrator monitor cycle. | Lane should NOT be flagged as stalled. The wider capture and process detection should identify active validation work. | |
| 2 | **Actually stalled lane** | Leave an author lane idle (no active work, no processes) for 2+ monitor cycles. | Lane SHOULD be flagged as stalled after the configured threshold. | |
| 3 | **Multiple lanes validating** | Start `make check-gated` in 3+ lanes simultaneously. Run monitor. | No false stall alerts. All lanes recognized as actively validating. | |
| 4 | **Process-tree detection** | Start `uv run python -m pytest tests/ -x` in a lane. Check if `_detect_background_validation` finds the process. | Should detect `pytest` in the pane's PID tree and return True. | |

### Automated Test Coverage

**New tests (11 in this PR):**
- Tests for 20-line tail window (`test_only_checks_tail_lines`)
- Tests for `make check` progress pattern detection (`test_detects_make_check_progress_line`)
- Tests for `Waiting for slot` pattern
- Tests for `check-quiet` pattern
- `TestDetectBackgroundValidation` class — process-tree detection tests
- `TestProcessGuard` — integration tests

**Verification command:**
```bash
uv run python -m pytest tests/unit/test_ops_monitor.py -v -k "line_8 or make_check_progress or waiting_for_slot or check_quiet or BackgroundValidation or ProcessGuard"
# Expected: 11 passed
```

**Full monitor suite:**
```bash
uv run python -m pytest tests/unit/test_ops_monitor*.py -v
# Expected: 175 passed
```

**Coverage gaps:**
- No test for the `-S -50` scrollback flag in actual tmux integration (tests mock pane content).
- No test for interaction between wider tail window and existing stall detection thresholds.

### Edge Cases to Probe

- **Zombie processes:** What if `make` dies but `pytest` subprocess continues? Does `_detect_background_validation` handle orphaned processes?
- **PID reuse:** If the pane PID is reused by a different process, could the detection produce false negatives?
- **Long-running make check:** `make check` can take 2-5 minutes. The existing stall threshold may still trigger if multiple monitor cycles pass. Verify the process-tree check runs on every cycle, not just the first.

### Render vs Localhost

- **Localhost only** — ops infrastructure, not deployed to Render.

---

## PR #2143 — Comment Board Timestamps to Local Timezone

### What Changed

Two files modified:
1. `web/templates/partials/comments_list.html` — Changed `datetime` attribute to use explicit UTC format (`%Y-%m-%dT%H:%M:%SZ` with `Z` suffix). Added "UTC" text suffix as no-JS fallback.
2. `web/templates/comments.html` — Added inline `<script>` block that converts `<time>` elements from UTC to local timezone using `date.toLocaleString()`. Re-runs after HTMX swaps (15s polling and post-submit refresh).

### Why It Matters

**Risk: LOW (UI cosmetic).** Timestamps previously showed raw UTC, confusing users in non-UTC timezones. The fix is client-side only — no backend changes, no data migration.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Local timezone display** | Navigate to the comments page on Render. Post a comment. | Timestamp should show in your local timezone format (e.g., "Apr 2, 2026, 7:30 PM" for EDT), NOT "Apr 02, 2026 11:30 PM UTC". | |
| 2 | **No-JS fallback** | Disable JavaScript in browser settings. Navigate to comments page. | Timestamps should display with "UTC" suffix (e.g., "Apr 02, 2026 11:30 PM UTC"). The raw server-rendered time is visible. | |
| 3 | **HTMX polling refresh** | Post a comment. Wait 15 seconds for the automatic refresh. | New comments loaded via HTMX polling should also have localized timestamps (the `htmx:afterSwap` listener re-runs conversion). | |
| 4 | **Different timezone** | If possible, test from a device in a different timezone (or change system timezone). | Timestamp should adapt to the viewer's locale. A comment posted at 3:00 PM EDT should show as 12:00 PM PDT for a Pacific user. | |
| 5 | **Multiple comments** | View a page with 5+ comments posted at different times. | All timestamps should be converted to local time, not just the first one. | |
| 6 | **Invalid datetime graceful handling** | Inspect a `<time>` element. Manually change the `datetime` attribute to an invalid value in DevTools. Reload. | The JS should gracefully handle `NaN` dates — the `if (isNaN(date.getTime())) { return; }` guard should prevent crashes. The original server text remains. | |

### Automated Test Coverage

**Existing tests:** The comment tests in `test_comments.py` cover comment creation, ordering, and display, but do NOT test the JavaScript timezone conversion (server-side tests only).

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_comments.py -v
# Expected: all tests pass
```

**Coverage gaps:**
- **No JS test coverage.** The core logic is a `<script>` tag in the template. Python unit tests cannot verify `toLocaleString()` behavior.
- **No Playwright test** for timezone conversion. This would require a browser-based test that checks the rendered text after JS executes.
- The `datetime` attribute format change (`isoformat()` → `strftime('%Y-%m-%dT%H:%M:%SZ')`) is untested — if `created_at` is not UTC-aware, the `Z` suffix would be misleading.

### Edge Cases to Probe

- **Timezone-naive datetimes:** If `comment.created_at` is a naive datetime (no tzinfo), `strftime('%Y-%m-%dT%H:%M:%SZ')` will still append `Z`, claiming UTC even if the value isn't. Verify the SQLAlchemy `Comment.created_at` column stores UTC.
- **Midnight boundary:** A comment posted at 11:55 PM UTC on Apr 2 should show as Apr 2 for UTC+0 users but potentially Apr 3 for UTC+5 users. Verify no date-wrapping bugs.
- **Locale formatting:** `toLocaleString(undefined, FORMAT_OPTIONS)` uses the browser's locale. Verify it doesn't crash on uncommon locales.

### Render vs Localhost

- Scenarios 1-5: **Render** (production confirmation of timezone behavior)
- Scenario 6: **Localhost** (DevTools manipulation)
- Automated tests: **Localhost only**

---

## PR #2145 — XSS Escaping Tests for Comments

### What Changed

Added `TestCommentXSSEscaping` test class to `tests/unit/hosted_play/test_comments.py` with 5 tests covering common XSS attack vectors: `<script>` injection, `<img onerror>`, HTML entity encoding, full-page rendering, and malicious nicknames.

### Why It Matters

**Risk: LOW (test-only, security assurance).** No production code changed. Jinja2's autoescape is already enabled by default via Starlette's `Jinja2Templates`, but there were no tests guaranteeing this. These tests lock the escaping behavior so a future template change (e.g., adding `|safe` filter or `{% autoescape false %}`) would fail CI.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Run XSS tests** | `uv run python -m pytest tests/unit/hosted_play/test_comments.py::TestCommentXSSEscaping -v` | All 5 tests pass. | |
| 2 | **Manual script injection** | On Render, post a comment with content: `<script>alert('xss')</script>` | The literal text `<script>alert('xss')</script>` should appear as comment text. No alert dialog should pop up. Inspect the HTML — angle brackets should be entity-encoded (`&lt;script&gt;`). | |
| 3 | **Image onerror injection** | Post a comment: `<img src=x onerror=alert('xss')>` | Should render as literal text, not as an image tag. No alert. | |
| 4 | **Nickname injection** | Set nickname to `<b>Evil</b>` (if nickname change is available). Post a comment. | Nickname should display as literal `<b>Evil</b>`, not bolded text. | |

### Automated Test Coverage

**New tests (5):**
- `test_htmx_partial_escapes_script_tags` — `<script>` in HTMX partial response
- `test_full_page_escapes_script_tags` — `<script>` on full page
- `test_img_onerror_escaped` — `<img onerror>` vector
- `test_html_entities_escaped` — angle brackets and ampersands entity-encoded
- `test_nickname_escaped_in_comments` — HTML in player nicknames

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_comments.py::TestCommentXSSEscaping -v
# Expected: 5 passed
```

**Coverage gaps:**
- No test for JavaScript event handler injection (`<div onclick="...">`)
- No test for CSS-based injection (`<style>body{background:url(...)}</style>`)
- No test for Unicode-encoded XSS payloads
- These are minor — Jinja2 autoescape covers all HTML context escaping by default.

### Edge Cases to Probe

- **Template `|safe` filter:** Search for any use of `|safe` in comment-rendering templates. If found, that bypasses autoescape and is a vulnerability.
- **Markdown rendering:** If future PRs add markdown support to comments, that would require careful sanitization beyond autoescape.

### Render vs Localhost

- Scenario 1: **Localhost only**
- Scenarios 2-4: **Render** (production security verification)

---

## PR #2146 — Comment Validation Error Messages

### What Changed

Three files modified:
1. `web/routes.py` — `post_comment()` now passes `error` to the HTMX partial context when validation fails. Non-HTMX fallback renders the full page with the error instead of silently redirecting.
2. `web/templates/partials/comments_list.html` — Added optional `error` variable rendering with `role="alert"` banner at the top of the partial.
3. `tests/unit/hosted_play/test_comments.py` — 3 new tests for error display.

### Why It Matters

**Risk: LOW (UX improvement).** Previously, submitting an empty or too-long comment silently failed — the user got no feedback. Now they see a red error banner. The `role="alert"` attribute ensures screen readers announce the error.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Empty comment (HTMX)** | On the comments page, clear the textarea and click "Post" (with JS enabled for HTMX). | A red error banner appears at the top of the comments list: "Comment cannot be empty." The banner has `role="alert"`. The existing comments remain visible below the error. | |
| 2 | **Too-long comment (HTMX)** | Post a comment exceeding 500 characters (the `_COMMENT_MAX_LENGTH` limit). | Error banner: "Comment too long (max 500 characters)." | |
| 3 | **Empty comment (non-HTMX)** | Disable JavaScript. Submit the empty form via the native `<form>` action. | The full comments page renders with the error message at the top. No redirect. | |
| 4 | **Too-long comment (non-HTMX)** | Disable JavaScript. Submit a >500 char comment. | Full page with error message. No redirect. | |
| 5 | **Successful comment after error** | Trigger an error (empty submit), then type valid content and submit again. | Error clears and the new comment appears in the list. The `hx-on::after-request` handler resets the form on success. | |
| 6 | **Error banner accessibility** | Use a screen reader (VoiceOver on Mac). Trigger a validation error. | Screen reader should announce the error message due to `role="alert"`. | |

### Automated Test Coverage

**New tests (3):**
- `test_post_comment_too_long_returns_error` — HTMX response includes error text
- `test_post_empty_comment_returns_error` ��� HTMX response includes empty error text
- `test_post_comment_too_long_non_htmx_returns_error` — non-HTMX full page with error

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_comments.py -k "returns_error" -v
# Expected: 3 passed
```

**Coverage gaps:**
- No test for the error clearing after successful submission.
- No test for the `role="alert"` attribute presence (the tests check for error text but not ARIA attributes).
- No test for the HTML structure of the error banner (CSS class `comments__error`).

### Edge Cases to Probe

- **Whitespace-only comments:** The code does `content = content.strip()` then checks `if not content`. Post a comment that's only spaces/tabs — should get "Comment cannot be empty."
- **Exactly 500 characters:** Post a comment that is exactly 500 chars — should succeed. Post 501 chars — should fail.
- **HTML in error message:** The error messages are hardcoded strings ("Comment cannot be empty."), so no injection risk. But verify the template uses `{{ error }}` (autoescaped) not `{{ error|safe }}`.
- **Concurrent HTMX polling:** If the 15s polling fires while an error is displayed, does the error banner persist or get swapped out? The polling hits `/comments/{uuid}/list` which doesn't pass `error`, so the error banner would disappear on the next poll cycle. This is probably acceptable behavior.

### Render vs Localhost

- Scenarios 1-5: **Both** (Render for production, localhost for fast iteration)
- Scenario 6: **Render** (needs real screen reader)

---

## PR #2147 — New Player Guide

### What Changed

Seven files modified:
1. `web/templates/guide.html` — New 252-line full guide page with sections: Quick Start, The Basics, Bidding, Card Play, Scoring, Icons & Indicators, Tips & Tricks, Basic Strategies.
2. `web/routes.py` — New `GET /guide/{link_uuid}` route handler (auth-gated, returns 404 for unknown UUIDs).
3. `web/templates/base.html` — "Guide" tab added to header navigation bar.
4. `web/templates/partials/model_select.html` — Quick-start guide callout with link to full guide.
5. `web/static/style.css` — CSS for `.quick-start-guide` component.
6. `tests/unit/hosted_play/test_partials.py` — 5 template tests for guide and quick-start.
7. `tests/unit/hosted_play/test_routes.py` — 6 route tests for the guide page.

### Why It Matters

**Risk: LOW (new feature, additive).** No existing functionality changed. Adds discoverable onboarding for new players — previously, users went straight from invite code to opponent selection with no rules explanation.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Guide accessible from nav** | Log in on Render. Click the "Guide" tab in the header navigation. | Guide page loads with title "How to Play". The "Guide" tab is highlighted as active. | |
| 2 | **Guide accessible from model select** | Start a new match. On the AI opponent selection screen, look for the quick-start callout. | A "New to Bid Euchre?" callout box appears below the start button with 4 quick tips and a "Read the full guide" link. | |
| 3 | **Quick-start link works** | Click "Read the full guide" on the model select page. | Navigates to `/guide/{link_uuid}`. Full guide renders. | |
| 4 | **All sections present** | Scroll through the guide page. | All 7 sections visible: The Basics, Bidding, Card Play, Scoring, Icons & Indicators, Tips & Tricks, Basic Strategies. Plus the Quick Start callout at the top. | |
| 5 | **Icon legend accurate** | Check the Icons & Indicators section. Compare each icon/symbol with actual game UI. | Icons match what the game actually uses (trump badges, legal play border, pass badge, etc.). | |
| 6 | **Back-to-game link** | On the guide page, look for a "Back to game" link. | Should link back to `/play/{link_uuid}` to return to active gameplay. | |
| 7 | **404 for invalid UUID** | Navigate to `/guide/invalid-uuid-here`. | Returns 404 error, not a server crash. | |
| 8 | **Mobile layout** | View the guide on a mobile device or narrow browser window (<600px). | Content should be readable, no horizontal scrolling, sections properly stacked. Guide container has `max-width: 720px` with auto margins. | |
| 9 | **Rules accuracy audit** | Read each section carefully. Compare claims against `docs/01_core/RULES.md`. | All rules descriptions should be accurate: 40-card double-deck, 10 cards per player, 10 tricks, suits (SHDC), bowers, scoring, moon/loner rules. | |
| 10 | **Guide without active match** | Navigate to guide when no match is in progress. | Guide should still render (it's auth-gated by player link, not by active match). | |

### Automated Test Coverage

**New tests (11):**
Route tests (`test_routes.py::TestGuide`):
- `test_guide_unknown_uuid_returns_404`
- `test_guide_renders_for_valid_player`
- `test_guide_contains_all_sections`
- `test_guide_tab_active_in_nav`
- `test_guide_tab_in_nav`
- `test_guide_back_to_game_link`

Template tests (`test_partials.py`):
- `test_guide_title`
- `test_guide_all_sections`
- `test_guide_icon_legend`
- `test_guide_back_link_with_uuid`
- `test_model_select_renders_without_link_uuid` (quick-start callout)

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_routes.py -k Guide -v
uv run python -m pytest tests/unit/hosted_play/test_partials.py -k guide -v
# Expected: 11 passed total
```

**Coverage gaps:**
- No test verifying the quick-start callout content matches the guide content (consistency check).
- No test for mobile CSS breakpoints.
- No content accuracy test (rules correctness vs. RULES.md) — this requires manual audit.

### Edge Cases to Probe

- **Long guide on slow connections:** The guide is 252 lines of HTML. No lazy loading or pagination. Should be fine for typical connections but verify no layout jank on initial render.
- **Browser back button:** Navigate to guide from game → press back → should return to game page (no history stack issues).
- **Guide tab highlight:** Verify the `current_page` context variable correctly highlights the Guide tab and de-highlights others.

### Render vs Localhost

- Scenarios 1-9: **Both** (Render for production confirmation, especially mobile and navigation)
- Scenario 10: **Localhost** (easier to test without active match)

---

## PR #2138 — Glutton Bower Validation Experiment (OPEN)

### What Changed

Added a seeded experiment (48,000 hands) validating GluttonStrategy bower handling in the **simulation** path. Key finding: PR #2126's bower fix only affected the hosted-play engine — the simulation path (`sim/simulation.py`) already called `on_hand_start()` correctly. Added 10 bower-specific unit tests, a new experiment config (`glutton_bower_validation.yaml`), an analysis script (`scripts/analyze_bower_validation.py`), and a validation report.

### Why It Matters

**Risk: LOW (experiment + docs, no behavior change).** Documents that the sim path is unaffected by the bower bug. The experiment data shows Glutton's Low contract weakness (-0.625 tricks vs Greedy) — this is expected and tracked.

### Status: OPEN — CI lint failure

The `checks` job failed; test shards passed. Likely a ruff lint or format issue.

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Fix lint and merge** | Run `uv run ruff check scripts/analyze_bower_validation.py` and `uv run ruff format --check` on all changed files. Fix any issues. | CI should pass after lint fixes. | |
| 2 | **Run the experiment** | `uv run python experiments/run_experiment.py --config experiments/configs/glutton_bower_validation.yaml --seed 42` | Experiment completes without error. Results land in `data/runs/`. | |
| 3 | **Verify unit tests** | `uv run python -m pytest tests/unit/test_greedy.py -v` | 10 new bower validation tests pass. | |
| 4 | **Report accuracy** | Read `plans/gameplay_intelligence/glutton_bower_validation_report.md`. Compare the table values against a fresh experiment run. | Metrics should match within expected variance. Glutton advantage in suit contracts ~+0.2-0.3, Low disadvantage ~-0.6. | |

### Automated Test Coverage

**New tests (10):** Bower validation tests in `tests/unit/test_greedy.py`.

**Verification command:**
```bash
uv run python -m pytest tests/unit/test_greedy.py -v
# Expected: 10 passed (total now includes existing + 10 new)
```

**Coverage gaps:**
- The experiment config is new but has no automated config validation test (though `scripts/validate_configs.py` covers it).

### Edge Cases to Probe

- **Lint fix scope:** Ensure the lint fix doesn't change any experiment logic.
- **Config registered:** Verify `glutton_bower_validation.yaml` is recognized by the experiment runner.

### Render vs Localhost

- **Localhost only** — experiment infrastructure, not deployed.

---

## PR #2140 — Auction UX Fix (OPEN)

### What Changed

Two bugs fixed in `web/routes.py` with supporting state changes:

**Bug 1 (#2133):** During hidden auction bid reveal, the human's hand was re-sorted with trump-aware ordering, leaking trump information before the winning bid was revealed. Fix: Added `_auction_reveal_active()` helper and override in `_build_game_context()` that re-sorts the visible hand without trump/contract knowledge during the hidden auction phase using `sort_hand_for_display()` with no contract info.

**Bug 2 (#2134):** When the human bids early and AI bids are auto-advanced, the last bid reveal would jump straight to trick play with no pause. Fix: Added `auction_settled: bool` field to `HandState` (default `True` for migration safety). After the last bid is revealed, `auction_settled` is `False`, requiring one extra "Next" click before play begins. No settle pause when the human bids last (dealer seat).

### Why It Matters

**Risk: MEDIUM (gameplay UX correctness).** Bug 1 gave players advance information about trump suit before it was supposed to be revealed — a gameplay fairness issue. Bug 2 caused players to miss the dealer's bid entirely — a confusing UX gap.

### Status: OPEN — CI/review pending

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Hand sort during auction reveal (Bug 1)** | Start a match. Bid something other than pass. Watch the auction reveal phase (clicking "Next" through bids). During reveal, check your hand display. | Cards should remain in their original sort order (suit-grouped, no trump awareness). Cards should NOT rearrange or regroup until after the auction is complete and trick play begins. | |
| 2 | **Trump grouping after auction** | Complete the auction reveal phase. Continue to trick play. | Now the hand SHOULD be sorted with trump awareness — trump suit cards grouped first, bowers moved to trump group. | |
| 3 | **Settle pause after last bid (Bug 2)** | Start a match where you bid early (seat 0, bidding first). Watch as AI bids are revealed one by one. After the last AI bid is revealed. | A settle pause should appear with text like "Auction complete" or similar. Clicking "Next" should advance to trick play. The last bid should be visible and readable before play starts. | |
| 4 | **No settle when human bids last (dealer)** | Start a match where you are the dealer (bid last). Submit your bid. | No extra settle pause needed — your bid was the last one, and you already know it. Trick play should begin immediately after your bid. | |
| 5 | **Migration safety** | Load a saved game that was created BEFORE this PR (no `auction_settled` field). | Should load without error. The `auction_settled` field defaults to `True` for existing games (safe default — no extra pause). | |
| 6 | **Serialization round-trip** | Start a game. During the auction settle pause, refresh the page. | Game should restore correctly. The settle pause should still be active if it was active before refresh. | |
| 7 | **All-pass + settle** | Get an all-pass hand (all players pass). | No settle pause should occur — there's no winning bid to settle. The hand should redeal immediately. | |

### Automated Test Coverage

**New tests (5):**
- `TestAuctionRevealUX::test_hand_sort_during_hidden_auction_no_trump_grouping`
- `TestAuctionRevealUX::test_settle_pause_after_last_bid_reveal`
- `TestAuctionRevealUX::test_no_settle_pause_when_human_bids_last`
- `TestHandState::test_round_trip_auction_settled_false`
- `TestHandState::test_from_dict_missing_optional_keys` (migration)

**Verification command:**
```bash
uv run python -m pytest tests/unit/hosted_play/test_routes.py::TestAuctionRevealUX -v
uv run python -m pytest tests/unit/hosted_play/test_state.py -k "auction_settled or missing_optional" -v
# Expected: 5 passed
```

**Coverage gaps:**
- No test for the all-pass + no-settle interaction.
- No test verifying the exact text shown during the settle pause.
- No test for the hand sort visual order (tests check that sort happened, but not the exact card order).

### Edge Cases to Probe

- **Moon bid during reveal:** What happens if someone bids moon (10)? Does the reveal flow handle the exchange phase correctly after the settle pause?
- **Human passes, AI wins:** After the settle pause, does the hand sort apply the correct trump for the AI's winning bid?
- **conftest `advance_pending_reveals` change:** The PR modifies `conftest.py` to advance through the settle pause. Verify this doesn't break any existing tests that rely on the old behavior.

### Render vs Localhost

- Scenarios 1-7: **Both** (Render for production UX, localhost for fast iteration)

---

## PR #2141 — Glutton Low Contract Defense-in-Depth Sync (OPEN)

### What Changed

Added 2 lines at the top of `choose_card()` in both `GluttonStrategy` and `GluttonIsolatedStrategy` (in `src/bid_euchre/strategy/greedy.py`):
```python
self._contract_type = contract_type
self._trump_suit = trump_suit
```

This ensures `_contract_type` and `_trump_suit` are always fresh from the call parameters, not reliant on `on_hand_start()` having been called. Added 6 new tests proving correct behavior without lifecycle hooks.

### Why It Matters

**Risk: MEDIUM (strategy correctness, defense-in-depth).** This eliminates a class of bugs where `_choose_discard` and `_choose_lead` use stale `self._contract_type`. Without `on_hand_start()`, the default was `"high"` — in a Low contract, this inverts card ranking (Aces treated as strongest when they should be weakest). PR #2126 fixed the hosted-play path, but this PR ensures correctness in ALL callers (tests, direct API, future integrations).

### Status: OPEN — review blocked

### Manual Testing Checklist

| # | Scenario | Steps | Expected Result | Pass/Fail |
|---|----------|-------|-----------------|-----------|
| 1 | **Run defense-in-depth tests** | `uv run python -m pytest tests/unit/test_glutton.py::TestContractSyncDefenseInDepth -v` | All 6 tests pass. | |
| 2 | **Low contract discard behavior** | Play a Low contract game on Render (after merge). When AI discards, observe which cards are discarded. | AI should discard Aces (strongest in Low = least valuable) and keep 10s (weakest in Low = most valuable). Previously, without the sync, AI would discard 10s (thinking they're weakest in "high" mode). | |
| 3 | **Low contract lead behavior** | In a Low contract, watch which card AI leads with. | AI should lead with weak cards (10s, Jacks) to conserve strong cards, not lead with Aces. | |
| 4 | **Suit contract unchanged** | Play several suit contract hands. | No behavioral change — `on_hand_start()` already sets these values in the normal hosted-play path. The sync is redundant but harmless. | |
| 5 | **Experiment determinism** | Run `uv run python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42` before and after the change. | Results should be **identical** — the simulation path already calls `on_hand_start()`, so the sync is a no-op there. | |
| 6 | **Full Glutton test suite** | `uv run python -m pytest tests/unit/test_glutton.py -v` | All 39 tests pass (33 existing + 6 new). | |

### Automated Test Coverage

**New tests (6):**
- `test_low_discard_without_on_hand_start` — Low contract discard correct without lifecycle hook
- `test_low_lead_without_on_hand_start` — Low contract lead correct without lifecycle hook
- `test_contract_type_synced_on_every_call` — contract_type updated on every choose_card call
- `test_following_trick1_no_fallback` — following behavior correct without on_hand_start
- `test_isolated_low_discard_without_on_hand_start` — same for GluttonIsolatedStrategy
- `test_isolated_contract_type_synced` — same sync verification for isolated variant

**Verification command:**
```bash
uv run python -m pytest tests/unit/test_glutton.py::TestContractSyncDefenseInDepth -v
# Expected: 6 passed
```

**Coverage gaps:**
- No test combining the defense-in-depth sync with the hosted-play lifecycle hooks (verifying they don't conflict).
- No experiment-level test proving sim determinism is unaffected.

### Edge Cases to Probe

- **Order of assignment:** The sync happens BEFORE `get_legal_indices()` is called. Verify no code path reads `self._contract_type` before the sync lines execute.
- **GluttonIsolatedStrategy parity:** The PR modifies both `GluttonStrategy` and `GluttonIsolatedStrategy`. Verify the changes are identical.
- **Interaction with PR #2126:** The lifecycle hooks from #2126 also set `_contract_type`. With both PRs merged, there's double-assignment (hook sets it, then `choose_card` sets it again). This is harmless but should be documented.

### Render vs Localhost

- Scenarios 1, 5, 6: **Localhost**
- Scenarios 2-4: **Render** (after merge and deploy)

---

## Cross-PR Interaction Analysis

### Overlapping Code Paths

| PR Pair | Overlap | Risk |
|---------|---------|------|
| **#2126 + #2141** | Both modify Glutton's contract state management. #2126 wires lifecycle hooks in `engine.py`; #2141 adds defense-in-depth sync in `greedy.py`. | **LOW** — complementary changes. #2141 is a safety net for #2126. Double-assignment of `_contract_type` is harmless. |
| **#2126 + #2138** | #2126 is the fix; #2138 validates it didn't affect the sim path. | **NONE** — #2138 is read-only analysis confirming sim already had correct hook calls. |
| **#2141 + #2138** | #2141 changes `choose_card()` which #2138's experiment exercises. | **LOW** — #2141 is a no-op when `on_hand_start()` is called (the sim path). Determinism should be preserved. Verify with seeded experiment. |
| **#2143 + #2145 + #2146** | All three touch the comments subsystem. #2143 modifies `comments_list.html` datetime format; #2145 adds tests for comment rendering; #2146 adds error handling to the same partial. | **MEDIUM** — These PRs modify the same template (`comments_list.html`). If merged out of order, merge conflicts are possible. The error banner (#2146) and the UTC suffix (#2143) both add content to the partial. |
| **#2147 + #2146** | Both modify `web/routes.py`. #2147 adds the guide route; #2146 adds error handling to comment route. | **LOW** — different functions in the same file. No overlap in route handlers. |
| **#2140 + #2126** | #2140 modifies auction flow in `routes.py`; #2126 modifies `engine.py`. Both affect the hand lifecycle. | **LOW** — different files, but the auction-to-play transition is where #2126's `_fire_on_hand_start` triggers. The settle pause from #2140 adds a step between auction end and play start — verify hooks still fire at the right time. |
| **#2142 + all others** | #2142 is ops infrastructure, completely independent of web/strategy changes. | **NONE** |
| **#2137 + all others** | #2137 is test-only for moon counterfactuals, independent of web changes. | **NONE** |

### Regression Risks

1. **Comment template collisions:** PRs #2143, #2145, and #2146 all touch the comment subsystem. They were merged in order (#2143 → #2145 → #2146), so no merge conflicts occurred. But if any is reverted, the others may need adjustment.

2. **Auction flow + bower hooks:** PR #2140 (settle pause) adds a step between auction completion and trick play. PR #2126's `_fire_on_hand_start` fires in `_process_auction_end()`. Verify the settle pause doesn't delay the hook fire — the hook should fire before the settle pause, not after.

3. **Glutton Low behavior convergence:** PRs #2126, #2138, and #2141 all relate to Glutton strategy correctness. Together they form a complete fix: #2126 (hosted-play hooks) + #2141 (defense-in-depth) + #2138 (sim validation). After all three merge, Glutton should be correct in all contexts.

---

## Multi-PR Proving Scenarios

### Scenario 1: "Full Suit Contract Game" (Tests #2126 + #2141 + #2147)

**Setup:** Log into Render. Open the player guide first to review suit contract rules.

**Steps:**
1. Start a new match (any AI opponent).
2. Navigate to the guide tab — verify it loads with all sections (#2147).
3. Return to game. Wait for a suit contract hand.
4. During the auction reveal phase, note that your hand does NOT rearrange (#2140, if merged).
5. During trick play, watch the AI opponent play. When a bower is in play:
   - The AI should play the right bower (J of trump) as a high-value card, not dump it.
   - The AI should value the left bower (J of same color) as second-highest trump (#2126).
6. Play a Low contract hand specifically. Observe AI discard and lead behavior — should prefer keeping 10s and discarding Aces (#2141).

**Expected:** AI plays competitively in suit contracts (not losing 2-8). Guide is accessible and accurate. Auction reveal doesn't spoil trump.

**Evidence to capture:** Screenshot of AI playing a bower strategically (not dumping). Screenshot of guide page loaded.

### Scenario 2: "Comment Board Full Cycle" (Tests #2143 + #2145 + #2146)

**Setup:** Log into Render with a valid invite code.

**Steps:**
1. Navigate to the Comments tab.
2. Post a normal comment: "Testing timestamps." Verify the timestamp shows in your local timezone, not UTC (#2143).
3. Try posting an empty comment (clear textarea, click Post). Verify error banner appears: "Comment cannot be empty." (#2146).
4. Try posting: `<script>alert('test')</script>`. Verify it renders as literal text with no popup (#2145).
5. Wait 15 seconds for HTMX polling. Verify new comments load with correct local timestamps (#2143 HTMX handler).
6. Post a valid long comment (~400 chars). Verify it appears correctly.
7. Post a >500 char comment. Verify error banner: "Comment too long (max 500 characters)." (#2146).

**Expected:** All timestamps localized. Error messages displayed for invalid input. XSS payloads safely escaped.

**Evidence to capture:** Screenshots of: (a) localized timestamp, (b) error banner for empty comment, (c) XSS payload rendered as text.

### Scenario 3: "New Player Onboarding Flow" (Tests #2147 + game flow)

**Setup:** Use a fresh invite code to simulate a new player experience.

**Steps:**
1. Enter the invite code. Land on the model select / opponent selection screen.
2. Read the quick-start callout box: "New to Bid Euchre?" with 4 tips (#2147).
3. Click "Read the full guide" link. Verify full guide loads.
4. Review each section: Basics, Bidding, Card Play, Scoring, Icons, Tips, Strategies.
5. Navigate back to the game using the "Back to game" link or browser back button.
6. Start a match. Play through one hand using the guide's advice.
7. Navigate to the Guide tab in the header at any point during gameplay.

**Expected:** Smooth onboarding flow. Guide is discoverable, accurate, and navigable. All links work. Guide tab works from within active gameplay.

**Evidence to capture:** Screenshots of: (a) quick-start callout on model select, (b) full guide page, (c) Guide tab in header nav.

### Scenario 4: "Auction UX Verification" (Tests #2140 + #2126)

> Only applicable after PR #2140 merges.

**Setup:** Log into Render.

**Steps:**
1. Start a match. If you are NOT the dealer (seats 1-3 bid first), bid 5 of any suit.
2. Click "Next" to reveal each AI bid one at a time.
3. During bid reveal, look at your hand. **Critical check:** Cards should NOT rearrange or regroup by trump (#2140 Bug 1).
4. After the last bid is revealed, verify a settle pause appears before trick play (#2140 Bug 2).
5. Click "Next" to dismiss the settle pause. Verify trick play begins.
6. Now check that your hand IS sorted with trump grouping (bowers moved to trump suit).
7. In a second match, be the dealer (bid last). Verify NO settle pause after your bid (#2140 no-settle-when-last).

**Expected:** Hand doesn't spoil trump during reveal. Settle pause gives time to read the last bid. No unnecessary pause when human bids last.

**Evidence to capture:** Screenshots of: (a) hand during auction reveal (no trump grouping), (b) settle pause message, (c) hand after trick play starts (with trump grouping).

### Scenario 5: "AI Competitive Play Validation" (Tests #2126 + #2141)

**Setup:** Play 5+ complete games on Render, tracking scores.

**Steps:**
1. Play 5 games against any AI opponent.
2. For each game, record:
   - Total hands played
   - Final score
   - Number of suit contract hands
   - Any bower plays observed (did AI play bowers early/strategically?)
   - Any Low contract hands (did AI discard/lead correctly?)
3. Check the leaderboard after all games.

**Expected:** AI should be competitive — not losing every game by a wide margin. Suit contract hands should be roughly balanced (not 8-2 human every time). Leaderboard should show a reasonable AI win rate (>30%).

**Evidence to capture:** Leaderboard screenshot after 5+ games. Notes on bower plays observed.

---

## Render Deployment Verification

### Post-Merge Deployment Checklist

After all open PRs (#2138, #2140, #2141) merge and Render auto-deploys:

| # | Check | URL / Action | Expected Result | Pass/Fail |
|---|-------|-------------|-----------------|-----------|
| 1 | **Health endpoint** | `GET https://bideuchre-web.onrender.com/health` | Returns 200 with `{"status": "ok"}` | |
| 2 | **Readiness endpoint** | `GET https://bideuchre-web.onrender.com/ready` | Returns 200 (DB connection healthy) | |
| 3 | **Landing page** | Visit `https://bideuchre-web.onrender.com/` | Landing page renders with invite code input | |
| 4 | **Invite code entry** | Enter a valid code (e.g., `OLIVIA-TEST`) | Redirects to model select page | |
| 5 | **Guide quick-start visible** | On model select page | "New to Bid Euchre?" callout box visible | |
| 6 | **Guide page** | Click "Read the full guide" | Guide page renders with all 7 sections | |
| 7 | **Guide nav tab** | Click "Guide" in header nav | Guide page loads; tab is active/highlighted | |
| 8 | **Start match** | Select AI opponent, click Start | Match begins, hand dealt, auction starts | |
| 9 | **Auction reveal** | Bid, then click Next through reveals | Hand doesn't reorg during reveal; settle pause after last bid | |
| 10 | **Trick play** | Play through a suit contract hand | AI plays bowers correctly (not dumping them) | |
| 11 | **Low contract** | Play a Low contract hand | AI discards Aces, leads weak cards | |
| 12 | **Comments page** | Navigate to Comments tab | Comments render with local timezone timestamps | |
| 13 | **Comment submission** | Post a comment | Comment appears with correct timestamp | |
| 14 | **Comment validation** | Submit empty / too-long comment | Error banner displayed | |
| 15 | **XSS protection** | Post `<script>alert(1)</script>` | Renders as text, no execution | |
| 16 | **Leaderboard** | Navigate to Leaderboard tab | Renders with current stats | |
| 17 | **Match completion** | Play to match completion (52 points) | Result screen renders correctly | |
| 18 | **Mobile check** | Visit on phone or narrow viewport | All pages responsive, no horizontal scroll | |

### Database / State Considerations

- **`auction_settled` migration (#2140):** The field defaults to `True` for existing games. No database migration needed — it's a `HandState` JSON field with a `from_dict` default. Existing in-progress games should load without error.
- **No schema changes:** None of the PRs add database columns or tables. All state changes are in the JSON-serialized `HandState` / `MatchState`.
- **Comment table:** Already exists from PR #2124 (pre-session). No migration needed.

### Rollback Plan

If a critical issue is found after deployment:
1. **Revert the specific PR** on main. Render auto-deploys the revert.
2. **Most isolated (safe to revert individually):**
   - #2147 (guide) — purely additive, no dependencies
   - #2142 (false-stall) — ops only, no web impact
   - #2137 (moon tests) — test only
   - #2145 (XSS tests) — test only
3. **Requires care when reverting:**
   - #2143 (timestamps) — reverts the `datetime` format; JS would fail on old format
   - #2146 (validation) — reverts error handling; silent failures resume
   - #2126 (bower fix) — reverts to broken AI; significant gameplay impact
4. **Requires coordinated revert:**
   - #2140 + conftest changes — revert conftest alongside the route changes
   - #2141 — revert requires checking if any in-progress games rely on the defense-in-depth sync

---

## Open PR Merge Order Recommendation

### Recommended Order: #2138 ��� #2141 → #2140

**Rationale:**

1. **#2138 (Glutton bower validation experiment)** — FIRST
   - Needs only a lint fix. No code dependencies on other open PRs.
   - Once merged, it documents the sim-path baseline before #2141 changes `choose_card()`.
   - Tests and experiment config are isolated.

2. **#2141 (Glutton Low contract sync)** — SECOND
   - Modifies `greedy.py` (`choose_card()` in `GluttonStrategy` and `GluttonIsolatedStrategy`).
   - Should merge after #2138 so the experiment baseline is established.
   - No merge conflict with #2138 (different files: `greedy.py` vs experiment configs).

3. **#2140 (Auction UX fix)** — THIRD
   - Most complex change (routes.py, state.py, conftest.py).
   - Modifies `conftest.py` which is shared test infrastructure — merging last minimizes disruption.
   - No code dependency on #2138 or #2141, but merge conflicts are most likely in `routes.py` (heavily modified file).
   - Has the `auction_settled` state field which affects serialization — best to merge when other changes are stable.

### Conflict Risk Assessment

| PR Pair | Conflict Risk | Specific Files |
|---------|---------------|----------------|
| #2138 + #2141 | **None** | Different files (experiments/ vs strategy/) |
| #2138 + #2140 | **None** | Different files (experiments/ vs web/) |
| #2141 + #2140 | **Low** | Both modify test files, but different test classes. `conftest.py` change in #2140 is independent. |

---

## Outcome

_To be filled after testing is complete._

- [ ] All manual checklists executed
- [ ] All automated test commands verified
- [ ] Multi-PR proving scenarios completed
- [ ] Render deployment verified
- [ ] Open PRs merged in recommended order
- [ ] Evidence screenshots captured and linked
