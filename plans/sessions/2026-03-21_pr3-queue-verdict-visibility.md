# PR3 — Queue / Verdict Visibility

**Date:** 2026-03-21
**Status:** in-progress
**Lane:** author-c
**Parent Plan:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Depends on:** PR1 (#1176, merged)

## Goal

Surface the local review queue state (request + verdict packets from
`review_queue.py`) in operator tooling so operators can inspect pending,
blocked, clean, stale, and error states before the PR4 cutover.

## Key Design Decisions

1. **New `queue` subcommand** — add `ops.py queue` rather than overloading
   the existing `reviews` subcommand. `reviews` is online-first (GitHub API);
   `queue` is local-first (file-based packets). They are conceptually separate.

2. **Read from review_queue substrate** — use `review_queue.read_request()` /
   `review_queue.read_verdict()` to read packet state. No legacy review-loop
   state.

3. **Effective status computation** — derive a single human-friendly status
   from the combination of request + verdict state:
   - `no_request` — no request.json exists (queue slot empty)
   - `pending` — request exists but no verdict
   - `running` — verdict exists with status "running"
   - `passed` — verdict status "passed" and SHA matches request
   - `blocked` — verdict status "blocked" and SHA matches request
   - `failed` — verdict status "failed" and SHA matches request
   - `stale` — verdict exists but reviewed_sha ≠ request head_sha
   - `error` — verdict file exists but is unparseable, or other unexpected state

4. **SHA freshness in output** — always show request head_sha and verdict
   reviewed_sha side by side so staleness is visually obvious.

5. **Graceful degradation** — missing files, corrupt JSON, missing directory
   all produce degraded output, not crashes.

## Write Scope

| File | Action |
|------|--------|
| `src/bid_euchre/ops/reviews.py` | Add `QueueEntry`, `get_queue_entries()`, `get_queue_entry()`, `format_queue_text()`, `format_queue_json()` |
| `scripts/internal/ops.py` | Add `queue` subcommand + `cmd_queue()` |
| `tests/unit/test_ops_reviews.py` | Add tests for all new queue functions |
| `tests/unit/test_ops_cli.py` | Add CLI integration test for `queue` subcommand |

## Out Of Scope

- `.claude/hooks/**`
- `.claude/settings.json`
- `scripts/internal/review_lane_runner.py`
- `scripts/internal/review_driver.py`
- Merge behavior changes

## Validation

- `ops.py queue` shows pending / blocked / clean / stale / error states
- `ops.py queue --pr N` shows detail for a specific PR
- Missing packet state degrades cleanly (no crash)
- JSON output is machine-parseable
- No merge-behavior changes introduced

## Outcome
<!-- Filled after implementation -->
