# Hybrid Playtest Round 6: Comments System

**Date:** 2026-04-03
**Player:** Claude-HYB (invite code QXBIA590)
**Focus:** Comments board — posting, validation, XSS protection, edge cases
**Method:** JavaScript fetch() POST battery (8 test cases) + Playwright screenshot verification

## Test Environment

- **Comments endpoint:** POST `/play/{link_uuid}/comment` with `content` form field
- **Max comment length:** 500 characters
- **Pre-existing comments:** 3 (from users Meeks and TEST)
- **Comment model:** Community board visible to all players

## Test Battery Results

| # | Test Case | Input | HTTP Status | Error Response | Comment Posted? | Verdict |
|---|-----------|-------|-------------|---------------|----------------|---------|
| 1 | Normal comment | "Testing the comments system..." (64 chars) | 200 | None | YES | **PASS** |
| 2 | Whitespace only | `"   "` (3 spaces) | 200 | "Comment cannot be empty." | NO | **PASS** |
| 3 | Empty string | `""` | **422** | FastAPI validation JSON | NO | **BUG** |
| 4 | HTML/XSS injection | `<script>alert("xss")</script><b>bold</b>&amp;` | 200 | None | YES (escaped) | **PASS** |
| 5 | Max length (500) | `"A" × 500` | 200 | None | YES | **PASS** |
| 6 | Over max length (501) | `"B" × 501` | 200 | "Comment too long (max 500 characters)." | NO | **PASS** |
| 7 | Unicode / emoji | `"Great game! ♠♥♦♣ 🎴🃏"` | 200 | None | YES | **PASS** |
| 8 | Duplicate content | Same as test 1 | 200 | None | YES (2nd copy) | **PASS** |

**Score: 7/8 pass.** One bug (empty string returns 422 JSON in HTMX context).

## Visual Verification

After all tests, reloaded the Comments page and verified:

| Aspect | DOM State | Visual State | Match? |
|--------|-----------|-------------|--------|
| Comment count | 8 `<li>` elements | 8 comments visible | ✅ |
| Author names | All show "Claude-HYB" (5) + "Meeks" (2) + "TEST" (1) | Correct bold names | ✅ |
| Timestamps | All show "Apr 3, 2026, 1:29 AM" for new comments | Correct localized times | ✅ |
| Ordering | Newest first | Newest first visually | ✅ |
| XSS content | `<script>` tags as text entities | Literal HTML visible, no execution | ✅ |
| 500-char comment | Full "AAA..." text | Wraps within container | ✅ |
| Emoji | `♠♥♦♣ 🎴🃏` in DOM | Rendered correctly | ✅ |
| Duplicate | Both copies present | Both visible as separate entries | ✅ |

## Detailed Findings

### Finding 1: XSS Protection Working Correctly (PASS)

HTML injection via `<script>alert("xss")</script><b>bold</b>&amp;` is properly escaped. The comment renders as literal text:
```
<script>alert("xss")</script><b>bold</b>&amp;
```

No script execution, no HTML rendering. The Jinja2 template engine auto-escapes by default, which is the correct behavior.

### Finding 2: Empty String Returns 422 JSON (BUG — variant of #2219)

When `content=""` is submitted, FastAPI returns HTTP 422 with a JSON validation error instead of an HTMX-compatible HTML partial. This is a variant of the same 422 handling gap identified in round 3 (#2219).

**Trigger:** Empty string form submission (rare in browser — textarea always sends at least `""`)
**Impact:** Low — normal browser form submissions send either the text or whitespace (which is caught by the handler's trim check). The 422 case only fires for truly empty programmatic requests.
**Already tracked:** #2219

### Finding 3: No Duplicate Comment Prevention (Observation)

Posting the same comment twice creates two separate entries. No deduplication or rate limiting on comments. This is acceptable for a pilot/MVP but could be abused.

**Recommendation (low priority):** Add a simple client-side debounce (disable Post button for 2s after submission) and/or server-side dedup check (reject identical content from same player within 30s).

### Finding 4: Whitespace-Only Validation Works (PASS)

The handler correctly strips whitespace (`content.strip()`) and rejects empty results with "Comment cannot be empty." — returning an HTML partial with `role="alert"` error message.

### Finding 5: Max Length Boundary Correct (PASS)

- 500 characters: accepted ✅
- 501 characters: rejected with clear error ✅
- No off-by-one error in the boundary check

### Finding 6: Community Board — All Players See All Comments (Observation)

Comments from Meeks, TEST, and Claude-HYB all appear on the same page. The comments system is a shared community board, not per-match or per-player. This is clear from the code (`_fetch_comments()` queries all comments without player filter).

### Finding 7: HTMX Polling for Live Updates (Observation)

The comments list uses `hx-trigger="every 10s"` for live polling (visible in the page source from the initial snapshot). This means new comments from other players would appear within 10 seconds without a page refresh. Good UX for a community board.

### Finding 8: Error Messages Use role="alert" (PASS)

Validation error messages include `role="alert"` attribute, making them accessible to screen readers. The error class `comments__error` provides visual styling.

## Screenshots

| File | Description |
|------|-------------|
| `playtest/09_comments_page_empty.png` | Comments page before tests (3 existing comments) |
| `playtest/10_comments_after_posts.png` | Comments page after 8 test posts (8 total comments) |

## Outcome

- **No new issues to file** — the only bug (422 on empty string) is already tracked in #2219
- **Overall assessment:** Comments system is well-implemented with proper XSS escaping, input validation, accessible error messages, and live polling. The community board model works correctly. One minor gap in 422 handling (shared with other endpoints).
