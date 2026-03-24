# Next Session Handoff — Browser Phase 4 + Platform-8b

**Date:** 2026-03-24
**Status:** READY FOR NEXT SESSION
**Primary tracks:** Browser Game Phase 4 data pipeline, Phase 4 Platform-8b remote audit trail

---

## Current State

### Browser lane

- The Phase 3 browser product is materially shipped in code on `main`:
  - `web/templates/game.html`
  - `web/templates/landing.html`
  - `web/templates/partials/*`
  - `web/static/style.css`
  - `web/static/game.js`
  - route wiring in `web/routes.py`
- Browser route and resume behavior are implemented and covered in the hosted-play
  route suite, but the local workspace cannot currently collect that suite because
  hosted deps are not fully installed.
- Browser planning metadata is behind the actual shipped code:
  - `plans/browser_game/3_frontend_product/checkpoints.md` still shows Steps 1 and 3
    `IN_PROGRESS`, Steps 4 and 5 `PENDING`
  - `plans/browser_game/4_data_pipeline/checkpoints.md` still treats Phase 4 as fully
    pending from a 2026-03-14 baseline
  - `plans/browser_game/sub_plan_registry.md` still shows `SP-3-02` and `SP-4-01`
    as `proposed`

### Platform lane

- Local control-loop hardening is complete:
  - `SP-4-05` is complete
  - `Platform-8a` Telegram setup/proving is complete
- The old `SP-4-05` session handoff is now stale and should be treated as
  architecture history only, not as the next dispatch brief.
- The next governed Phase 4 platform slice is:
  - `Platform-8b` repo-owned remote audit trail (`#1324`)
- Remote proving through Telegram should follow `Platform-8b`, not replace it.

### Runtime state

- `uv run python scripts/internal/ops.py --json status` currently reports stale
  lanes and warnings, but no active packets.
- `uv run python scripts/internal/ops.py --json dashboard` currently reports a
  large unacked inbox backlog.
- Start the next session with a cleanup/reset pass before new platform proving.

---

## Recommended Session Order

### Track 1 (PRIMARY): Browser Game Phase 4 — Data Pipeline

This is the best primary implementation track for the next session.

#### Step 0: Closure and verification pass first

Spend the first 20-30 minutes on these exact tasks:

1. Sync hosted/dev dependencies so browser route tests are runnable.
2. Rerun the hosted-play browser test suite:
   - `uv run python -m pytest -q tests/unit/hosted_play/test_routes.py`
   - `uv run python -m pytest -q tests/unit/hosted_play/test_engine.py tests/unit/hosted_play/test_partials.py`
3. Update browser planning metadata so the durable repo state matches shipped code:
   - `plans/browser_game/3_frontend_product/checkpoints.md`
   - `plans/browser_game/4_data_pipeline/checkpoints.md`
   - `plans/browser_game/sub_plan_registry.md`

#### Browser note on current test status

- In this workspace, route-test collection currently fails with:
  - `ModuleNotFoundError: starlette`
- The non-route browser tests do run:
  - `tests/unit/hosted_play/test_engine.py`
  - `tests/unit/hosted_play/test_partials.py`
  - result: 62 tests passed

#### Step 1: Start Phase 4 implementation

After the closure pass, move directly into `SP-4-01` export/replay work.

Recommended implementation order:

1. Add `web/export.py`
2. Add `tests/unit/hosted_play/test_export.py`
3. Implement and lock tests for:
   - `decision_to_jsonl()`
   - `export_decisions()`
4. Add `validate_replay()` once the exported decision schema is test-locked
5. Add the CLI wrapper last:
   - `scripts/internal/export_hosted_decisions.py`

Why this order:

- It locks the replay/export contract in tests before CLI work expands scope.
- It uses the now-fixed decision rows and redeal persistence as the data baseline.

### Track 2 (SECONDARY): Phase 4 Platform lane — Platform-8b remote audit trail

This is the correct next platform slice for the next session.

#### Step 0: Platform cleanup/reset

Before new platform implementation:

1. Restart the steward session cleanly
2. Run:
   - `uv run python scripts/internal/ops.py lane refresh --all-idle`
3. Compact or purge handled inbox noise if needed
4. Verify stale execution-surface warnings are either cleared or intentionally ignored

#### Step 1: Start Platform-8b, not more SP-4-05 work

Do **not** spend platform lanes on more local control-loop work unless a fresh
runtime issue proves otherwise.

The next platform implementation target is:

- `#1324` — repo-owned audit trail for remote channel exchanges

Recommended first actions:

1. Create/register the next Phase 4 platform sub-plan for `Platform-8b`
   (expected next ID: `SP-4-06`)
2. Scope the slice around durable logging for every remote exchange:
   - inbound operator -> orchestrator
   - outbound orchestrator -> operator
   - alerts
   - permission-relay prompts
3. Log, at minimum:
   - timestamp
   - direction
   - channel source
   - sender identity
   - content or content hash

#### Step 2: Defer remote proving until after Platform-8b

Telegram away-from-desk proving is still valuable, but it should be treated as
the next user-smoke-test-gated step after the audit trail lands.

That means:

- do `Platform-8b` first
- then move to idle-attention alerts / acknowledgement loop
- then do away-from-desk queue-moving proving

### Track 3 (TERTIARY): Deferred platform follow-ups

Only use idle platform/scratch capacity here after Tracks 1-2 are unblocked:

- `#1337` — live dashboard auto-refresh
- `#1289` — transport consolidation reassessment
- `#1288` — comment-ingestion bridge activation
- small convention follow-ups:
  - `#1505`
  - `#1514`
  - `#1520`

---

## What To Read At Session Start

### Browser

- `plans/browser_game/governing_plan.md`
- `plans/browser_game/3_frontend_product/checkpoints.md`
- `plans/browser_game/4_data_pipeline/checkpoints.md`
- `plans/browser_game/4_data_pipeline/sub/2026-03-14_export_replay.md`
- `plans/browser_game/sub_plan_registry.md`

### Platform

- `plans/agent_ops/4_remote_channel/plan.md`
- `plans/agent_ops/4_remote_channel/checkpoints.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
- `plans/sessions/2026-03-24_sp4-05-reactive-control-loop-handoff.md`
  - read for architecture decisions only, not as the next dispatch brief

---

## Validations

### Browser

- `uv run python -m pytest -q tests/unit/hosted_play/test_routes.py`
- `uv run python -m pytest -q tests/unit/hosted_play/test_engine.py tests/unit/hosted_play/test_partials.py`
- `uv run python -m pytest -q tests/unit/hosted_play/test_export.py`

### Platform

- `uv run python scripts/internal/ops.py --json status`
- `uv run python scripts/internal/ops.py --json dashboard`

---

## Key Decisions For The Next Session

- Browser Phase 4 is the best primary implementation target.
- The browser lane should begin by reconciling planning metadata to shipped code.
- Platform should not return to `SP-4-05`; that slice is complete.
- The next governed platform slice is `Platform-8b` / `#1324`.
- Telegram away-from-desk proving is not the first next platform task.
- Ignore unrelated untracked `.claude/*` repo state unless it directly interferes.
