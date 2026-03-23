# Operator Hardening — Control Surface Unification

**Date:** 2026-03-23
**Status:** IN_PROGRESS
**Context:** Post-Phase-3 pre-proving fix session. Two messaging systems discovered, review completion signaling unreliable.

## Problem

1. Review completion relies on prompt-level agent behavior — the review lane displayed findings but never sent them to the operator-visible bus.
2. Two parallel messaging systems exist:
   - Claude native (`SendMessage`) → `~/.claude/teams/default/inboxes/<lane>.json`
   - Repo-owned custom bus (`ops.py message send`) → `.claude/runtime/message_bus/inbox/<lane>.jsonl`
3. Dashboard/monitor/operator workflows watch the custom bus only, creating an observability split.

## Governing Constraints

### Review completion
- Do NOT create a manual `ops.py review-submit` as the primary review path
- The canonical review path already exists: `post-pr-review.sh` → `review_driver.py` → `review_queue.write_verdict()`
- A manual path would be a competing review truth unless it writes through the same verdict API

### Task start
- Do NOT infer "task started" from `git checkout -b` or first Edit/Write
- Task acceptance should be tied to packet pickup in `/start-task` via explicit CLI command

### Messaging
- Do NOT drop the custom bus or ban Claude native SendMessage
- Custom bus remains canonical operator/audit surface
- Native messages are bridged/imported into the custom bus

## Implementation

### PR 1: Lifecycle guarantees [author-b]

**1. Review verdict → orchestrator notification bridge**
- When a terminal review verdict is written (`passed`, `blocked`, `failed`), emit a structured bus message to the orchestrator automatically
- Preferred seam: `review_queue.write_verdict()` or immediately after final verdict writes in `review_driver.py` / `review_lane_runner.py`
- Message: to_lane=orchestrator, includes PR number, reviewed SHA, verdict status, finding count, `source_transport=review_verdict_bridge`
- Do NOT create a separate competing review storage path

**2. Task acceptance command**
- Add `ops.py task accept PACKET_ID --lane LANE`
- Atomically: ack inbox assignment, send "task received" to orchestrator, emit task-start event
- Idempotent (safe to call twice)
- Update `/start-task` SKILL.md to use this as first lifecycle step

**Files:** `src/bid_euchre/ops/review_queue.py`, `scripts/internal/review_lane_runner.py`, `scripts/internal/review_driver.py`, `scripts/internal/ops.py`, `.claude/skills/start-task/SKILL.md`
**Tests:** `tests/unit/test_review_queue.py`, `test_review_lane_runner.py`, `test_review_driver.py`, `test_ops_cli.py`

### PR 2: Native inbox bridge [author-c, blocked by PR 1]

**3. Native inbox bridge/importer**
- Read `~/.claude/teams/default/inboxes/<lane>.json`
- Import native messages into repo-owned message bus with `source_transport=claude_native`
- Dedupe using content hash or stable native identifier
- Safe to rerun repeatedly (idempotent)
- Add `ops.py inbox --include-native` for operator visibility during rollout
- Long-term: dashboard/monitor operate from unified custom bus surface

**Files:** `src/bid_euchre/ops/message_bus.py`, `scripts/internal/ops.py`, `tests/unit/test_ops_message_bus.py`

## Related Issues

| # | Title | Relationship |
|---|-------|-------------|
| #1285 | `read_inbox` `now` parameter for test sleeps | Test quality |
| #1288 | Codex comment ingestion activation | Future review channels |
| #1289 | Transport consolidation reassessment | Follow-up: revisit after bridge proves out |
| #1290 | Context clearing for agent lanes on new work | Dispatch UX |
| #1291 | Pre-merge guard false-positive on tmux send-keys | Bug fix |
| #1292 | Task complete CLI for manual packet lifecycle | Complements task accept |

## Validation

- Terminal review verdict writes produce an orchestrator-visible bus message
- `/start-task <packet_id>` causes one canonical task-accept signal without relying on git/edit hooks
- Imported native review messages visible via `ops.py inbox` on the custom bus
- Duplicate bridge runs do not duplicate messages
- Dashboard/monitor no longer miss review outcomes from Claude native SendMessage

Commands:
```bash
uv run pytest -q tests/unit/test_review_queue.py tests/unit/test_review_lane_runner.py tests/unit/test_review_driver.py
uv run pytest -q tests/unit/test_ops_message_bus.py tests/unit/test_ops_cli.py
make check-quiet
```

## Outcome

<!-- Fill after implementation -->
