# Platform-9a Final Wiring — Dispatch Package

**Date:** 2026-04-01
**Analyst:** analyst-a (packet `5f7b140b0f80`)
**Issue:** #1826
**Sub-plan:** SP-4-08 (`plans/agent_ops/4_remote_channel/sub/2026-03-25_platform-9a-idle-attention-alerts.md`)
**Checkpoints:** Step 4 IN_PROGRESS

---

## Executive Summary

Platform-9a has all library-level components shipped (push evaluator, Telegram
adapter, ack parser, controller mutation, unit/integration tests). Three exit
criteria remain open — all share the same root cause: **MCP tools can only be
called by the AI agent in a conversation, not by hooks or scripts.** The Python
code correctly produces push payloads and ack confirmations, but the "last mile"
delivery to Telegram requires the orchestrator to act.

Two code PRs close the gap. One human proving step validates the loop.

## Current State Assessment

### What's Shipped

| Component | Location | Status | Evidence |
|-----------|----------|--------|----------|
| Alert push evaluator | `src/bid_euchre/ops/telegram_push.py` | Done | PRs #1781, #1795 |
| Push state dedup/backoff | `src/bid_euchre/ops/telegram_push.py` | Done | PR #1795 |
| Monitor cycle integration | `src/bid_euchre/ops/monitor.py:1929` | Done | PR #1944 |
| CLI push output | `scripts/internal/ops.py:2395` | Done | Prints `📢 Alert push prepared` |
| Remote ack parser | `src/bid_euchre/ops/remote_ack.py` | Done | PR #1777 |
| Controller mutation | `src/bid_euchre/ops/monitor.py:2011` | Done | `process_inbound_ack()` |
| Inbound hook wiring | `.claude/hooks/inbound-channel-audit.py:97` | Done | PR #1969 |
| Outbound audit | `.claude/hooks/post-telegram-audit.sh` | Done | PR #1715 |
| Unit tests | `tests/unit/test_ops_*`, `test_inbound_channel_audit.py` | Done | ~40 tests |
| Integration tests | `tests/integration/test_remote_ack_loop.py` | Done | PR #1820 |
| Competing-receiver fix | `.claude/hooks/post-telegram-audit.sh` (lane guard) | Done | PR #1971 |
| Skill doc (check-in Phase 2c) | `.claude/skills/check-in/SKILL.md:162-203` | Done | Outbound pattern documented |

### What's Missing (3 Exit Criteria)

| Exit Criterion | Gap | Root Cause |
|----------------|-----|------------|
| **E3 — Outbound push delivery** | Monitor prints push payload but no mechanism ensures the orchestrator calls `mcp__plugin_telegram_telegram__reply()` | Skill-doc-only instruction; no `additionalContext` injection |
| **E4/E7 — Inbound ack confirmation reply** | Hook mutates controller state + injects `additionalContext`, but orchestrator must act on it to send confirmation | `additionalContext` delivery unproven in live path |
| **E9 — Live round-trip** | Cannot prove until E3 delivery works | Depends on E3 + E4/E7 |

## Architecture Constraint

```
┌─────────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Python code         │     │  Hook system  │     │  AI Agent       │
│  (monitor, ack)      │────▶│  (bash/py)    │────▶│  (orchestrator) │
│                      │     │              │     │                 │
│  CAN: evaluate,      │     │  CAN: inject  │     │  CAN: call MCP  │
│  mutate state,       │     │  additional-  │     │  tools (reply)  │
│  format messages     │     │  Context      │     │                 │
│                      │     │              │     │                 │
│  CANNOT: call MCP    │     │  CANNOT: call │     │  MUST: parse    │
│  tools               │     │  MCP tools    │     │  context, act   │
└─────────────────────┘     └──────────────┘     └─────────────────┘
```

The hook-based `additionalContext` injection is the strongest available
mechanism to prompt the orchestrator. It already works for E4/E7 inbound
acks (PR #1969). The same pattern should be applied to E3 outbound pushes.

## Gap Analysis: E3 — Outbound Push Delivery

### Current Path (Unreliable)

1. Orchestrator runs `/check-in` which runs `ops.py monitor`
2. CLI prints `📢 Alert push prepared (N items) → chat <chat_id>` + message to stdout
3. Check-in SKILL.md (Phase 2c, lines 180-203) tells orchestrator to parse stdout and call MCP
4. **Orchestrator may skip/miss this** — stdout parsing is unreliable in long output

### Recommended Fix: PostToolUse Hook Injection

Mirror the E4/E7 pattern: add a PostToolUse sub-hook that detects push output
and injects `additionalContext` with an explicit delivery instruction.

**Two changes needed:**

1. **`scripts/internal/ops.py`** — Add a machine-readable `PUSH_RELAY:` JSON
   line after the human-readable push output, so the hook can parse reliably:

   ```python
   if cycle_result.push_result is not None:
       pr = cycle_result.push_result
       print(
           f"\n📢 Alert push prepared ({len(pr.items_pushed)} items)"
           f" → chat {pr.chat_id}"
       )
       print(pr.message)
       # Machine-readable line for PostToolUse hook consumption
       import json as _json
       print(f"\nPUSH_RELAY:{_json.dumps({'chat_id': pr.chat_id, 'message': pr.message})}")
   ```

2. **`.claude/hooks/post-monitor-push-relay.sh`** (new) — Sub-hook that:
   - Greps `tool_response.stdout` for `PUSH_RELAY:` marker
   - Extracts the JSON payload (`chat_id`, `message`)
   - Outputs `additionalContext` with a structured delivery instruction

   ```
   TELEGRAM ALERT PUSH (chat_id=<id>):
   <message text>
   → DELIVER NOW: Call mcp__plugin_telegram_telegram__reply(chat_id="<id>", text="<msg>")
   ```

3. **`.claude/hooks/post-bash-dispatch.sh`** — Add the new sub-hook to the
   dispatch chain (after `post-task-event.sh`, before `post-merge-notify.sh`).

### Why Not Just Fix the Skill Doc?

The skill doc already documents the pattern (Phase 2c). The issue (#1826) proves
that skill-doc-only instructions are unreliable — the orchestrator doesn't
consistently parse monitor stdout for push payloads. The `additionalContext`
injection is a distinct channel that appears prominently in the conversation
regardless of output length.

## Gap Analysis: E4/E7 — Inbound Ack Confirmation Reply

### Current Path (Mostly Wired)

1. Telegram message arrives as `<channel source="telegram">` tag
2. `inbound-channel-audit.py` hook fires (UserPromptSubmit)
3. Hook calls `process_inbound_ack()` → **controller state mutated** (automated)
4. Hook injects `additionalContext`: `TELEGRAM ACK REPLY (chat_id=<id>): <reply_text>`
5. **Orchestrator must call `mcp__plugin_telegram_telegram__reply()`** (manual)

### Assessment

The critical state change (controller mutation) is **already automated** by the
hook (PR #1969). The confirmation reply requires the orchestrator to act on
`additionalContext`, which is the same mechanism proposed for E3.

**No new code is strictly required.** The gap is:
1. The `additionalContext` delivery path has never been proven in a live session
2. The orchestrator's check-in skill doesn't explicitly mention acting on
   `TELEGRAM ACK REPLY` context

### Recommended Hardening

Add an explicit instruction block to the check-in SKILL.md:

```markdown
### Inbound Ack Reply Delivery

When the `inbound-channel-audit.py` hook detects an ack command from
Telegram, it injects `additionalContext` containing:

    TELEGRAM ACK REPLY (chat_id=<id>):
    <confirmation text>
    → Reply to Telegram chat <id> with the above confirmation.

**Action:** Call `mcp__plugin_telegram_telegram__reply()` with the provided
chat_id and text. This confirms to the operator that their ack was processed.
```

This is a docs-only change that can be bundled with the E3 PR or done separately.

## Gap Analysis: E9 — Live Round-Trip Proving

### Prerequisites

- E3 PostToolUse hook is merged and deployed
- `STEWARD_TELEGRAM_ENABLED=1` in orchestrator environment
- `STEWARD_ALERT_PUSH_CHAT_ID` configured with operator's chat ID
- Telegram plugin active on orchestrator pane
- Fleet is idle (no meaningful events within threshold)

### Proving Protocol

| Step | Action | Expected Outcome | Verify |
|------|--------|------------------|--------|
| 1 | Ensure fleet is idle | `is_fleet_idle()` returns True | `ops.py fleet` shows idle status |
| 2 | Seed or wait for HIGH finding | Monitor produces a HIGH finding | `ops.py monitor` shows `📢 Alert push prepared` |
| 3 | Observe `additionalContext` injection | PostToolUse hook fires, orchestrator sees delivery instruction | Check hook output in conversation |
| 4 | Orchestrator calls MCP reply | Telegram message sent to operator's phone | Phone receives alert with item_id prefixes |
| 5 | Operator replies `ack <prefix>` | Phone sends message back | Telegram chat shows sent message |
| 6 | Hook processes inbound ack | Controller state mutated, `additionalContext` injected | `ops.py fleet` shows item as `acked` |
| 7 | Orchestrator sends confirmation | Confirmation reply sent via MCP | Phone receives "Acked item..." message |
| 8 | Verify audit trail | Both directions recorded | `cat .claude/runtime/audit_trail/remote_exchanges.jsonl \| tail -10` |

### Proving Commands

```bash
# Pre-flight
uv run python scripts/internal/ops.py fleet                    # Check fleet status
uv run python scripts/internal/ops.py monitor                  # Trigger push evaluation

# After ack (verify state change)
uv run python scripts/internal/ops.py fleet                    # Item should show acked
cat .claude/runtime/audit_trail/remote_exchanges.jsonl | tail -10  # Audit trail
```

## PR Decomposition

### PR-A: PostToolUse hook for outbound push relay (E3)

**Title:** `feat(ops): add PostToolUse hook for Telegram push relay (#1826)`

**Goal:** Ensure the orchestrator reliably delivers alert push payloads to
Telegram by injecting `additionalContext` from a PostToolUse hook, mirroring
the E4/E7 inbound ack pattern.

**Scope:**

| File | Action | Lines Changed |
|------|--------|---------------|
| `scripts/internal/ops.py` | Add `PUSH_RELAY:` JSON line after push output | ~3 lines |
| `.claude/hooks/post-monitor-push-relay.sh` | New sub-hook: detect push, inject context | ~50 lines |
| `.claude/hooks/post-bash-dispatch.sh` | Add `run_hook` call for new sub-hook | ~1 line |
| `.claude/skills/check-in/SKILL.md` | Add inbound ack reply delivery section | ~15 lines |

**Acceptance Criteria:**

- [ ] When `ops.py monitor` produces a push payload, the PostToolUse hook
      injects `additionalContext` with chat_id and message text
- [ ] The `PUSH_RELAY:` JSON line is parseable by the hook (no escaping issues
      with special characters in messages)
- [ ] When no push payload is produced, the hook exits silently (no noise)
- [ ] The hook is registered in `post-bash-dispatch.sh` dispatch chain
- [ ] Check-in SKILL.md documents the inbound ack reply delivery obligation
- [ ] `make check` passes

**Validation Commands:**

```bash
# Tier 1 — verify hook mechanics
# Manually test with a mock monitor output containing PUSH_RELAY line
echo '{"tool_input":{"command":"ops.py monitor"},"tool_response":{"stdout":"PUSH_RELAY:{\"chat_id\":\"123\",\"message\":\"test\"}"}}' \
  | .claude/hooks/post-monitor-push-relay.sh

# Tier 2 — full suite
make check-quiet
```

**Lane Assignment:** author-a or author-b (either can own this — no overlap
with active work)

### PR-B: (Optional) Prove E4/E7 inbound path without code changes

**Title:** `docs(ops): verify inbound ack wiring and update checkpoints (#1826)`

**Goal:** Prove the E4/E7 `additionalContext` injection works in a live
session. Update checkpoints.md with verification evidence.

**Scope:**

| File | Action |
|------|--------|
| `plans/agent_ops/4_remote_channel/checkpoints.md` | Update Step 4 with E4/E7 verification |

**This is a docs-only PR** — the code wiring is already done (PR #1969).
The proving can happen during E9 if preferred.

**Lane Assignment:** orchestrator (proving requires the orchestrator's live
Telegram session)

### E9: Human Proving (Not a PR)

**Owner:** Human operator + orchestrator lane
**Prerequisites:** PR-A merged
**Duration:** ~10 minutes
**Protocol:** See "Proving Protocol" table above

## Safe Parallelism Analysis

```
PR-A (hook + ops.py + skill doc)  ←── author-a or author-b
         │
         ▼
PR-B (checkpoints docs)          ←── orchestrator (optional, can merge with E9)
         │
         ▼
E9 (live round-trip proving)     ←── human operator
```

**PR-A is the only code PR.** It touches:
- `scripts/internal/ops.py` (3-line change in `cmd_monitor()`)
- `.claude/hooks/post-monitor-push-relay.sh` (new file)
- `.claude/hooks/post-bash-dispatch.sh` (1-line addition)
- `.claude/skills/check-in/SKILL.md` (15-line addition)

**No overlap with any other active author lane work.** The hooks directory
and ops.py monitor section are not touched by other in-flight PRs.

**PR-B can run in parallel with PR-A** (different file scope). But it's
optional — the proving evidence can instead be captured during E9.

## Risks and Scope Traps

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `additionalContext` not displayed prominently enough for orchestrator to act | Medium | Push/ack confirmation not delivered | Use CAPS and arrow markers in the injection text to make it visually prominent |
| Multi-line message with special chars breaks JSON in `PUSH_RELAY:` line | Low | Hook fails to parse push payload | Use Python `json.dumps()` which handles escaping; test with emoji-heavy messages |
| Hook adds latency to every Bash command | Low | Slower interactive experience | Hook exits in <10ms when no `PUSH_RELAY:` marker found (fast guard) |
| Stale `additionalContext` from previous cycle causes duplicate delivery | Low | Operator gets same alert twice | Check-in skill already documents skip condition for duplicate messages |
| E9 proving blocked by Telegram plugin not being active | Medium | Cannot complete final exit criterion | Verify plugin is active before proving: `claude plugins list` |

## Gaps Not Captured in #1826

1. **No automated E9 regression test.** After proving, there's no way to
   automatically re-prove the round-trip (it requires a human + phone). Consider
   adding a mock integration test that simulates the full flow without actual
   Telegram calls.

2. **`additionalContext` reliability is platform-dependent.** If Claude Code
   changes how `additionalContext` is displayed or prioritized, both E3 and
   E4/E7 could silently regress. This is an inherent platform risk with no
   mitigation other than periodic re-proving.

3. **Concurrent ack + push race.** If the operator sends an ack at the same
   moment a new push is being prepared, the controller mutation from the ack
   could race with `reconcile()`. The existing `merge_with_previous()` pattern
   should handle this, but it hasn't been tested under concurrent load.

4. **Check-in skill Phase 2c and the new hook overlap.** After PR-A ships,
   the orchestrator might get BOTH the stdout `📢 Alert push prepared` text
   AND the `additionalContext` injection, potentially triggering a double
   delivery. The hook instruction should note: "If you already delivered this
   alert based on stdout, skip the additionalContext instruction."

## Issue Update Recommendation

After PR-A merges, update #1826:
- Mark E3 as resolved (hook wired)
- Mark E4/E7 as resolved (PR #1969 + skill doc update)
- Note E9 as ready for human proving
- Keep issue open until E9 is proven

After E9 proving:
- Close #1826 with proving evidence
- Update SP-4-08 checkpoints to COMPLETE
- Update Phase 4 checkpoints Step 4 to COMPLETE
- Unblock Step 5 (Platform-9b) and Step 6 (Platform-9c)

## Orchestrator Handoff

**What shipped:** All library components for Platform-9a (push evaluator, ack
parser, controller mutation, tests, monitor wiring, inbound hook).

**What is in flight:** This dispatch package.

**What is blocked:** Steps 5 (Platform-9b) and 6 (Platform-9c) blocked on
E9 proving (#1826).

**Exact next safe slices:**
1. Dispatch PR-A to an author lane (scope: 4 files, ~70 lines changed)
2. After PR-A merges, attempt E9 proving with human operator
3. After E9 passes, close #1826 and unblock Steps 5/6

**Validation status:** All existing tests pass (`make check` green on main).

**Pending user smoke tests:** E9 round-trip proving (requires human + phone).

## Outcome

_(To be filled after implementation)_
