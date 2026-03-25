# Sub-Plan: Feedback Forum and Claude User Constraints

**ID:** SP-AC-02
**Parent phase:** Analytics and Community (`4_analytics_and_community`)
**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Status:** proposed
**Created:** 2026-03-25
**Depends on:** SP-AC-01 (leaderboard ships first)

---

## Goal

Add an invite-only feedback forum tab and define Claude (bot) user constraints.
The forum provides a simple post-based feedback channel for pilot participants.
Claude can participate as a labeled automated user with strict rate limits and
no admin/moderation privileges.

## Requirements

### Forum Access

- Forum is invite-only: only authenticated players with a valid invite code
  can view and post.
- Access gating reuses the existing Phase 3 invite-code session mechanism.

### Forum Features

- **Read posts:** Chronological post list with category filter.
- **Create post:** Simple form with title, body, and category selector.
- **Category set:** Small, fixed set of categories (e.g., Bug Report,
  Feature Request, General Feedback, Game Strategy). Categories are
  admin-defined, not user-created.
- **Moderation:** Hide/unhide only. No editing or deleting others' posts.
  Moderation is reserved for admin users (human operators).
- **No threaded replies:** Posts are top-level only. No nested comments or
  threaded discussion.
- **No chat or community expansion:** The forum is a simple feedback channel,
  not a social platform.

### Claude (Bot) Constraints

Claude may participate in matches and the forum as a labeled automated user.
The following constraints apply:

| Constraint | Limit |
|------------|-------|
| Labeled as automated | Claude's posts and match participation are visually marked as bot/automated |
| No invite admin | Claude cannot create, distribute, or revoke invite codes |
| No moderation | Claude cannot hide/unhide others' posts |
| No edit/delete others | Claude cannot modify or remove other users' content |
| Max active matches | 1 concurrent active match |
| Max completed matches per 24h | 3 |
| Max forum posts per 24h | 3 |

### Architecture

- **Route-backed tab:** The forum is a real route (`/forum`) that renders
  server-side within the shared invited-user shell layout. No SPA-only tab
  state.
- **No websockets:** Forum content is served via standard HTTP
  request/response. Page refresh or simple polling for new posts is
  acceptable.
- **Shared shell:** Game, Leaderboard, and Forum tabs share the same
  invited-user shell layout with consistent navigation.
- **Claude user record:** Claude's user record has an `is_bot` flag (or
  equivalent) that drives the constraint enforcement and visual labeling.

## Implementation Constraints

- No websockets.
- No SPA-only tab state -- must use real routes.
- No threaded chat or community expansion.
- No Claude privileged bypass routes.
- Claude bot constraints are enforced at the application layer, not just UI.

## File Scope

| Area | Files |
|------|-------|
| Data model | `src/bid_euchre/web/models.py` (Post model, category enum, bot flag) |
| Backend | `src/bid_euchre/web/routes/forum.py` (new) |
| Bot constraints | `src/bid_euchre/web/bot_constraints.py` (new) |
| Templates | `src/bid_euchre/web/templates/forum/` (new) |
| Shell layout | `src/bid_euchre/web/templates/base.html` or shared shell template |
| Unit tests | `tests/unit/hosted_play/test_forum.py` (new) |
| Unit tests | `tests/unit/hosted_play/test_bot_constraints.py` (new) |
| Route tests | `tests/unit/hosted_play/test_forum_routes.py` (new) |
| Integration | `tests/integration/hosted_play/test_forum_integration.py` (new) |

## Validation

### Tier A -- Unit

- Post creation persists correctly with category.
- Category filter returns only matching posts.
- Hide/unhide toggles post visibility.
- Bot constraints enforce rate limits (1 active match, 3 completed/24h,
  3 posts/24h).
- Bot user cannot call admin or moderation endpoints.
- Access gating rejects unauthenticated requests.

### Tier B -- Route/Integration

- `GET /forum` returns 200 with valid invite session, 401/403 without.
- `POST /forum/new` creates a post and redirects to forum list.
- Bot-labeled posts render with automated badge.
- Rate limit enforcement returns 429 when exceeded.

### Tier C -- Browser E2E

- Playwright test: navigate to forum tab, create a post, verify it appears
  in the list.
- Playwright test: verify bot posts display the automated label.

## Outcome

_To be filled after implementation._
