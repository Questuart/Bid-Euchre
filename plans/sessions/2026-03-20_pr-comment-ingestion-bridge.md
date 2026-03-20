# PR Comment Ingestion Bridge (Lane B)

**Date:** 2026-03-20
**Status:** in_progress
**Parent plan:** `plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md` (Lane B)
**Goal:** Make PR comments a first-class ops signal. Codex Cloud comments from
`chatgpt-codex-connector[bot]` are the primary real case.

## Locked Decisions

- Codex Cloud is comment-based unless new empirical evidence says otherwise
- Do NOT add `codex-review.yml`
- Do NOT add speculative `ADVISORY_CONTEXTS` entries
- Ingest/surface comments only; do NOT enable autonomous public replies

## Implementation Steps

### 1. Comment Query & Normalization (`scripts/internal/github_pr_state.py`)

Add to existing module:

- `TRUSTED_BOT_LOGINS: frozenset[str]` — `{"chatgpt-codex-connector[bot]"}`
- `@dataclass PRComment` — normalized comment record:
  - `pr_number: int`, `comment_id: int`, `author_login: str`
  - `author_type: str` (human|trusted_bot|other_bot)
  - `created_at: str`, `body: str`, `source_channel: str` (issue_comment)
- `classify_comment_author(login: str, user_type: str) -> str` — returns
  human/trusted_bot/other_bot
- `get_pr_comments(pr_number: int) -> list[PRComment]` — calls
  `gh api repos/{owner}/{repo}/issues/{pr_number}/comments` with
  `--jq` for login, id, body, created_at, author_association, user type

### 2. Event Type (`src/bid_euchre/ops/events.py`)

- Add `"pr_comment_ingested"` to `VALID_EVENT_TYPES`

### 3. Comment Overlay in Reviews (`src/bid_euchre/ops/reviews.py`)

- `@dataclass CommentOverlay` — per-PR comment signal:
  - `pr_number: int`, `total_comments: int`, `trusted_bot_comments: int`
  - `latest_trusted_bot_comment: str | None` (body excerpt, max 200 chars)
  - `latest_trusted_bot_author: str | None`
  - `latest_trusted_bot_time: str | None`
  - `comments: list[dict]` (optional raw list)
- `get_pr_comment_overlay(pr_number: int) -> CommentOverlay` — fetch + classify
- `format_comment_overlays_text(overlays: list[CommentOverlay]) -> str`
- `format_comment_overlays_json(overlays: list[CommentOverlay]) -> list[dict]`

### 4. Index Entry Type (`src/bid_euchre/ops/index.py`)

- Add `"pr_comment"` to `ENTRY_TYPES`
- Add `_ingest_pr_comments()` — reads from a JSONL sidecar file:
  `.claude/runtime/pr_comments/pr_{N}.jsonl`
- Wire into `build_index()` as step 10

### 5. CLI Surface (`scripts/internal/ops.py`)

- Add `comments` subcommand:
  - `ops.py comments --pr N [--json]` — show comment overlay for a PR
  - `ops.py comments --pr N --ingest [--json]` — ingest + emit event + index
- Wire parser and dispatch

### 6. Tests

All new test files (none exist yet):

- `tests/unit/test_github_pr_state.py` — PRComment dataclass, classify_comment_author,
  get_pr_comments mock
- `tests/unit/test_ops_events.py` — pr_comment_ingested event type works
- `tests/unit/test_ops_reviews.py` — CommentOverlay, format functions
- `tests/unit/test_ops_index.py` — pr_comment entry type, _ingest_pr_comments
- `tests/unit/test_ops_cli.py` — comments subcommand dispatch

## Validation

- Tier 1: `uv run pytest -q tests/unit/test_github_pr_state.py tests/unit/test_ops_events.py tests/unit/test_ops_index.py tests/unit/test_ops_reviews.py tests/unit/test_ops_cli.py`
- Tier 2: `make check-quiet`

## Outcome

<!-- filled after implementation -->
