# Platform-8b: Repo-Owned Remote Audit Trail

**ID:** SP-4-06
**Date:** 2026-03-24
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Platform-8b
**Status:** ready
**Owner:** author-a

---

## Problem Statement

The governing plan requires: "Every inbound and outbound remote exchange must
be durably recorded in repo-owned state." Today, Telegram messages flow through
the Claude Code Channels framework into the orchestrator session and outbound
replies flow through MCP tool calls (`mcp__plugin_telegram_telegram__reply`).
Neither path writes to any repo-owned audit surface. The only record lives in
Telegram's servers and the ephemeral Claude session log.

Platform-8b closes this gap by introducing a durable JSONL audit log that
captures every remote exchange direction, with enough metadata for
cross-session traceability and incident forensics.

## Inputs

- `plans/agent_ops/4_remote_channel/plan.md` -- Phase 4 plan (Platform-8b slice)
- `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` -- SP-4-01 scope lock
- Issue #1324 -- repo-owned audit trail requirement
- `src/bid_euchre/ops/message_bus.py` -- existing JSONL audit trail pattern
- `src/bid_euchre/ops/events.py` -- durable event log pattern
- `.claude/tmux/steward-session.sh` -- Telegram channel wiring (orchestrator-only)

## Assumptions

- The Telegram plugin is the only remote channel in v1 (Discord deferred)
- Only the orchestrator pane has `--channels` enabled; author lanes are tmux-only
- Claude Code Channels framework does not expose hook points for
  pre/post message interception — audit must be implemented at the
  application layer
- Inbound messages arrive as `<channel source="telegram" ...>` XML tags
  in the orchestrator conversation context
- Outbound messages are sent via MCP tool calls
  (`mcp__plugin_telegram_telegram__reply`)
- The existing `message_bus.py` JSONL+flock pattern is proven and reusable

## Dependencies

- Platform-8a COMPLETE (Telegram transport proven) ✅
- SP-4-05 COMPLETE (lifecycle reactivity proven) ✅
- Existing JSONL audit trail pattern in `message_bus.py` (reusable)

## Seam Analysis

### Where remote exchanges happen

The Telegram plugin mediates all remote communication. Every exchange falls
into one of these categories:

| Direction | Category | How it enters the system | Current record |
|-----------|----------|--------------------------|----------------|
| **Inbound** | Operator message | `<channel source="telegram" chat_id="..." message_id="..." user="..." ts="...">` tag injected into orchestrator conversation | Ephemeral session context only |
| **Outbound** | Orchestrator reply | `mcp__plugin_telegram_telegram__reply` tool call (chat_id, body, optional files, optional reply_to) | Telegram server-side only |
| **Outbound** | Alert notification | Same `reply` tool call, triggered by monitor/scheduler | Telegram server-side only |
| **Outbound** | Permission relay prompt | Framework-managed (tool approval forwarded to Telegram); operator responds in-channel | Framework-managed, no repo-owned record |
| **Outbound** | Reaction | `mcp__plugin_telegram_telegram__react` tool call (chat_id, message_id, emoji) | Telegram server-side only |
| **Outbound** | Edit | `mcp__plugin_telegram_telegram__edit_message` tool call | Telegram server-side only |
| **Inbound** | Attachment fetch | `mcp__plugin_telegram_telegram__download_attachment` tool call (file_id → local path) | Ephemeral local file only |

### Code verification (2026-03-24)

The following code paths were read to verify the seam analysis:

1. **`src/bid_euchre/ops/message_bus.py`** — `_append_jsonl()` (line 283):
   confirmed flock+JSONL pattern is `fcntl.flock(LOCK_EX)` → append → `flock(LOCK_UN)`.
   Uses a dedicated `.lock` file (not the data file) for safe concurrent writes.
   This is the pattern to reuse for `audit_trail.py`.

2. **`src/bid_euchre/ops/events.py`** — `append_event()` (line 77): same
   flock+JSONL pattern with dedicated lock file. Validates event types against
   a frozen set. Audit trail should follow this validation pattern.

3. **`src/bid_euchre/ops/__init__.py`** — no Telegram references anywhere in
   `src/bid_euchre/ops/`. The audit trail module will be the first ops module
   with remote-channel awareness. Module docstring listing confirms the export
   pattern: one line in the module docstring, no eager imports.

4. **`.claude/tmux/steward-session.sh`** — line 335 confirms orchestrator-only
   channel flag: `--channels plugin:telegram@claude-plugins-official`. Author
   lanes never receive `--channels`, confirming SP-4-01 assumption.

5. **Telegram MCP tool surface** — verified from system prompt that 4 tools
   exist: `reply`, `react`, `edit_message`, `download_attachment`. All 4 are
   now captured in the seam table above.

**Verification conclusion:** All assumptions confirmed. No additional seams
discovered. The interception strategy is sound.

### Interception strategy

Since the Claude Code Channels framework does not expose middleware hooks,
audit logging must happen at the **application layer** — i.e., in the
orchestrator's tool-use patterns, not in the transport.

**Inbound interception:** A PostToolUse hook or explicit orchestrator
discipline that logs every received `<channel>` tag before acting on it.
Alternatively, a thin helper function called by the orchestrator at the start
of every Telegram-sourced turn.

**Outbound interception:** A wrapper module that exposes `audit_reply()`,
`audit_react()`, `audit_edit()` functions. The orchestrator calls these
instead of raw MCP tool calls. Each wrapper logs the exchange, then delegates
to the underlying MCP tool.

**Attachment fetch interception:** `download_attachment` returns a local file
path. The audit trail should log the fetch event (file_id, resulting path) but
does not need to hash the file content in v1 (already noted in Known Gaps).

**Permission relay:** Framework-managed and opaque. The sub-plan acknowledges
this gap and defers structured capture to a future hardening pass. The audit
log can record a `permission_relay_observed` event when the orchestrator
detects that a permission prompt was forwarded.

## Log Schema

### Storage

```
.claude/runtime/audit_trail/
    remote_exchanges.jsonl    # Append-only audit log
    .remote_exchanges.lock    # flock file
```

### Record fields (minimum)

| Field | Type | Description |
|-------|------|-------------|
| `exchange_id` | `str` | UUID4 for this audit record |
| `timestamp` | `str` | ISO 8601 UTC timestamp |
| `direction` | `str` | `"inbound"` or `"outbound"` |
| `channel_source` | `str` | `"telegram"` (extensible to `"discord"` later) |
| `sender_identity` | `str` | User ID for inbound; `"orchestrator"` for outbound |
| `exchange_type` | `str` | `"message"`, `"reply"`, `"react"`, `"edit"`, `"download_attachment"`, `"permission_relay_observed"` |
| `content_hash` | `str` | SHA-256 hex digest of message content |
| `content_preview` | `str` | First 200 chars of content (truncated, no secrets) |
| `chat_id` | `str` | Telegram chat ID |
| `message_id` | `str \| None` | Telegram message ID (if available) |
| `metadata` | `dict` | Additional fields (reply_to, file paths, emoji, etc.) |

### Design decisions

- **Content hash + preview, not full content:** Avoids storing potentially
  large messages or sensitive content in the audit log. The hash enables
  correlation with Telegram's server-side record. The preview enables
  quick forensic triage.
- **Reuse flock pattern:** Same `fcntl.flock` locking as `message_bus.py`
  for concurrent-write safety.
- **Separate from message bus:** The audit trail is a different concern
  (external channel forensics) from the lane-to-lane communication bus.
  Keeping them separate avoids polluting the bus with high-frequency
  Telegram traffic and keeps the audit schema purpose-built.
- **No event emission in v1:** Audit writes are append-only JSONL. Event
  emission (`events.py`) can be added in a hardening pass if dashboard
  integration is needed.

## File Scope

| File | Action | Description |
|------|--------|-------------|
| `src/bid_euchre/ops/audit_trail.py` | NEW | Core audit trail writer: `AuditRecord` dataclass, `append_record()`, `read_records()`, `audit_reply()` / `audit_react()` / `audit_edit()` wrappers |
| `tests/unit/test_audit_trail.py` | NEW | Unit tests for record serialization, append, read, filtering, content hashing |
| `src/bid_euchre/ops/__init__.py` | MODIFY | Export `audit_trail` module |

### Files NOT in scope (later PRs)

| File | Why deferred |
|------|-------------|
| Orchestrator prompts / skills | Inbound/outbound seam wiring is orchestrator-discipline work, not library code. Wired after core writer is proven. |
| `.claude/hooks/*` | PostToolUse hook for inbound logging is an option but may be wired in a hardening pass. |
| `src/bid_euchre/ops/dashboard.py` | Dashboard audit-trail view is optional and deferred to Platform-9c. |
| `src/bid_euchre/ops/monitor.py` | Audit trail health checks (e.g., "no inbound records in 24h") deferred to Platform-9c. |

## Micro-PR Decomposition

### PR 1: Core audit trail writer + unit tests

**Scope:** `src/bid_euchre/ops/audit_trail.py`, `tests/unit/test_audit_trail.py`, `src/bid_euchre/ops/__init__.py`

**Delivers:**
- `AuditRecord` frozen dataclass with all schema fields
- `append_record(record, audit_dir)` — JSONL append with flock
- `read_records(audit_dir, *, direction=None, channel_source=None, since=None, limit=None)` — filtered read
- `content_hash(text)` — SHA-256 hex digest helper
- `content_preview(text, max_len=200)` — truncation helper
- Unit tests covering: serialization round-trip, append + read, filtering by direction/channel/time, content hash determinism, concurrent-write safety (flock), empty-log edge case

**Validation:**
```bash
uv run python -m pytest tests/unit/test_audit_trail.py -v
make check-quiet
```

**Exit criteria:**
- All unit tests pass
- `make check-quiet` green
- `ruff check` and `ruff format` clean

### PR 2: Outbound audit wrappers

**Scope:** `src/bid_euchre/ops/audit_trail.py` (extend), `tests/unit/test_audit_trail.py` (extend)

**Delivers:**
- `audit_reply(chat_id, body, reply_to=None, files=None, audit_dir=None)` — logs outbound reply record, returns the record
- `audit_react(chat_id, message_id, emoji, audit_dir=None)` — logs outbound react record
- `audit_edit(chat_id, message_id, body, audit_dir=None)` — logs outbound edit record
- Each wrapper creates an `AuditRecord` with appropriate `exchange_type` and `direction="outbound"`, appends it, and returns the record for callers to inspect

**Validation:**
```bash
uv run python -m pytest tests/unit/test_audit_trail.py -v
make check-quiet
```

### PR 3: Inbound audit helper

**Scope:** `src/bid_euchre/ops/audit_trail.py` (extend), `tests/unit/test_audit_trail.py` (extend)

**Delivers:**
- `audit_inbound(chat_id, message_id, user, content, channel_source="telegram", ts=None, metadata=None, audit_dir=None)` — logs inbound message record
- Parsing helper `parse_channel_tag(tag_text)` that extracts attributes from `<channel source="telegram" ...>` XML tags
- Unit tests for inbound logging and tag parsing

**Validation:**
```bash
uv run python -m pytest tests/unit/test_audit_trail.py -v
make check-quiet
```

### PR 4: Integration tests + seam wiring documentation

**Scope:** `tests/integration/test_audit_trail_integration.py` (NEW), docs updates

**Delivers:**
- Integration tests: full round-trip (inbound + outbound sequence), concurrent writers, large-volume append performance
- Documentation of how to wire the audit trail into the orchestrator workflow (seam wiring guide)
- Update Phase 4 checkpoints to reflect Platform-8b progress

**Validation:**
```bash
uv run python -m pytest tests/integration/test_audit_trail_integration.py -v
make check-quiet
```

## Exit Criteria

- [ ] `AuditRecord` dataclass and JSONL writer/reader are implemented and tested
- [ ] Outbound wrappers (`audit_reply`, `audit_react`, `audit_edit`) are implemented and tested
- [ ] Inbound helper (`audit_inbound`, `parse_channel_tag`) is implemented and tested
- [ ] Integration tests verify full round-trip and concurrent-write safety
- [ ] All tests pass (`make check-quiet` green)
- [ ] No changes to existing bus, monitor, or dashboard modules
- [ ] Seam wiring documentation describes how orchestrator uses the audit trail
- [ ] Phase 4 checkpoints updated (Step 2 progressed toward COMPLETE)

## Known Gaps (deferred to Platform-9c hardening)

- **Permission relay audit:** Framework-managed, no interception point available. Capture as `permission_relay_observed` when detected, but completeness is not guaranteed.
- **Dashboard view:** No dashboard panel for audit trail in v1. Add in hardening.
- **Monitor health check:** "No inbound in N hours" watchdog deferred.
- **Retention/rotation:** JSONL file grows unbounded in v1. Add rotation in hardening.
- **Alert audit:** Outbound alerts are logged as regular `reply` records. Distinguishing alerts from conversational replies requires orchestrator metadata enrichment.
- **Attachment content:** File attachments are logged by path/filename only; content is not hashed or stored.

## Validation

- [ ] Sub-plan follows template structure
- [ ] Registered in sub-plan registry
- [ ] Checkpoints updated with Step 2 IN_PROGRESS
- [ ] `git diff --stat` shows only declared scope files

## Planned Outputs

- `plans/agent_ops/4_remote_channel/sub/2026-03-24_platform-8b-audit-trail.md` -- this sub-plan
- Updated `plans/agent_ops/sub_plan_registry.md` with SP-4-06 entry
- Updated `plans/agent_ops/4_remote_channel/checkpoints.md` with Step 2 IN_PROGRESS

## Observed Outputs

_(To be filled after implementation)_

## Outcome

_(To be filled after implementation)_
