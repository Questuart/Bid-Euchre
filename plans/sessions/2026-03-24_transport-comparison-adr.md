# Transport Comparison Architecture Decision Record

> **ADR for #1289:** Reassess messaging transport consolidation after native
> inbox bridge proves out.
>
> **Status:** ACCEPTED
> **Date:** 2026-03-24
> **Author:** author-a (SP-4-07, Deliverable 4)
> **Context:** #1289, #1571, SP-4-07 sub-plan

---

## Decision

**Keep each transport in its proven role; do not consolidate to a single
transport layer.** The five transports serve distinct purposes and have
non-overlapping strengths. Attempting to force one transport into all roles
would create fragility without simplification.

| Transport | Recommended Role | Status |
|-----------|-----------------|--------|
| Custom message bus | Durable coordination and audit backbone | **Keep (canonical)** |
| Claude native SendMessage/inboxes | Optional conversational signal source; import-bridge to bus | **Keep (optional)** |
| Claude Channels (Telegram) | Remote/live-session push to orchestrator | **Keep (preferred remote adapter)** |
| Hooks (Pre/PostToolUse) | Local enforcement, surfacing, and guardrails | **Keep (local enforcement)** |
| tmux nudges (send-keys) | Best-effort pane wake-up and task injection | **Keep (fallback only)** |

---

## Context

The steward platform evolved five distinct transport mechanisms through
Platform phases 3–8. Issue #1289 asked whether to consolidate, and three
options were proposed: migrate toward native, keep the bridge, or consolidate
on the custom bus only.

The 2026-03-24 overnight autonomous run (43+ PRs shipped) and proving runs
(SP-4-05, SP-4-06) generated real operational evidence:

- The custom bus reliably persisted 100+ messages across 12 lanes over 8+ hours
- The orchestrator never manually polled its inbox, proving pure-pull is
  insufficient for urgent state (#1571)
- Telegram inbound was proven working (PR #1616 fixed the competing-bun issue)
- tmux nudges successfully triggered `/start-task` across all 12 worker lanes
- Hooks (post-merge-notify, pre-merge-review-guard) provided zero-latency
  local enforcement without relying on any transport layer

---

## Comparative Evaluation

### Evaluation Criteria

| # | Criterion | Weight | Definition |
|---|-----------|--------|------------|
| 1 | Latency to surface urgent state | High | How quickly can a P0 alert reach the recipient |
| 2 | Durability / replayability | High | Does the message survive restarts, compaction, and auditing |
| 3 | Structured metadata support | Medium | Can the transport carry typed fields (severity, task_id, etc.) |
| 4 | Ack / clear compatibility | Medium | Can the recipient acknowledge and the sender verify receipt |
| 5 | Auditability | High | Is there a durable, queryable record of all exchanges |
| 6 | Operator usability | Medium | Can a human or remote operator interact naturally |
| 7 | Implementation / maintenance cost | Low | Effort to build and keep working |

### Transport Comparison Matrix

| Criterion | Custom Bus | Native SendMessage | Claude Channels | Hooks | tmux Nudges |
|-----------|-----------|-------------------|----------------|-------|-------------|
| **Latency** | ❌ Pull-only; no push | ❌ Pull-only; no push | ✅ Sub-second push to orchestrator session | ✅ Zero-latency (fires synchronously in-process) | ⚠️ ~1s; best-effort (may corrupt in-flight prompt) |
| **Durability** | ✅ JSONL + flock; survives restarts; queryable | ⚠️ JSON file; format undocumented; may change between Claude versions | ❌ Ephemeral; no durable record unless repo-owned audit layer captures it | ⚠️ Stateless; fires once per tool use; no persistence | ❌ Fire-and-forget; no persistence or retry |
| **Structured metadata** | ✅ Full: type, priority, severity, task_id, from/to, timestamps, TTL | ⚠️ Limited: from, summary, text only; no typed fields | ⚠️ Plain text messages; structured data must be encoded in message body | ✅ Full programmatic access to repo state; can read any structured artifact | ❌ Raw string injection; no structure |
| **Ack / clear** | ✅ Full lifecycle: pending→delivered→acked→resolved→expired | ❌ No ack mechanism; read status unknown | ❌ No native ack; must layer ack protocol on top | ⚠️ Implicit (hook ran = state was checked); no explicit ack protocol | ❌ No ack; no delivery confirmation |
| **Auditability** | ✅ Global `messages.jsonl` audit trail; per-lane inboxes; content-hash dedup | ⚠️ `~/.claude/teams/default/inboxes/<lane>.json` exists but is opaque; format may change | ⚠️ Only if repo-owned `audit_trail.py` captures exchanges (SP-4-06) | ⚠️ Hook execution is not logged by default; must emit events explicitly | ❌ No audit trail; `send-keys` is invisible |
| **Operator usability** | ⚠️ CLI only (`ops.py inbox`); not natural for humans; good for agents | ⚠️ Invisible to operator; used implicitly by Claude sessions | ✅ Natural for humans (Telegram chat); good for mobile/remote | ❌ Invisible to operator; purely mechanical | ❌ Invisible; only visible as typed text in tmux pane |
| **Impl/maint cost** | ✅ Stable (1500+ LOC, mature); well-tested; low ongoing cost | ✅ Zero cost (built into Claude Code); bridge is 80 LOC | ⚠️ Plugin dependency; bun subprocess; competing-process bugs (#1615); auto-detect logic | ✅ Bash scripts; simple; stable pattern | ✅ 3 LOC (`tmux send-keys`); trivial |

### Summary Scores

| Transport | Strengths | Weaknesses |
|-----------|-----------|------------|
| **Custom bus** | Durability, ack lifecycle, audit, structured metadata | No push capability; pure pull |
| **Native SendMessage** | Zero implementation cost; cross-session visibility | Opaque format; no ack; limited metadata; may change between versions |
| **Claude Channels** | Sub-second push; natural operator UX; remote access | Ephemeral without audit layer; plugin reliability (#1521); no structured metadata |
| **Hooks** | Zero-latency local enforcement; full repo state access | Stateless; no persistence; invisible to operators; per-tool-use only |
| **tmux Nudges** | Simple pane wake-up; works for task injection | Fragile; no ack; no audit; can corrupt in-flight prompts |

---

## Role Assignments

Based on the evidence, each transport has one primary role where it excels
and no other transport can substitute:

### 1. Custom Message Bus → Durable Coordination Backbone

**Role:** All structured lane-to-lane communication, task lifecycle
coordination, and operational audit.

**Evidence:**
- Handled 100+ messages across 12 lanes in the overnight run with zero data loss
- JSONL + flock pattern proven reliable under concurrent writes (SP-4-06 integration tests)
- Full ack lifecycle (pending→delivered→acked→resolved→expired) enables receipt tracking; the write-only gap (#1571) is addressed by the controller projection + hook surfacing layer (see § Answering #1571)
- Content-hash dedup prevents duplicates across imports
- Cross-worktree visibility via `shared_bus_root()` works across all 16 panes

**Consumed by:** Orchestrator, ops monitor, author lanes (via CLI),
controller projection (SP-4-07 Deliverable 1)

**Not suitable for:** Real-time push/interrupt, remote/mobile operator access

### 2. Claude Channels (Telegram) → Preferred Remote Push Adapter

**Role:** Remote operator access and live-session push delivery to the
orchestrator.

**Evidence:**
- Telegram inbound proven working (PR #1616; user 8122530898 paired and tested)
- Sub-second delivery when bun subprocess is healthy
- Natural UX for human operators on mobile
- Permission relay (orchestrator as single ingress) works as designed

**Constraint:** All inbound Channel messages must be captured by the
repo-owned audit trail (`audit_trail.py`) before being acted on.
Channels are adapters on top of repo-owned state, not sources of truth.

**Not suitable for:** Lane-to-lane coordination (only orchestrator has the
channel), durable audit (ephemeral without repo layer), structured metadata

**Known risks:** Plugin reliability (#1521), competing-bun-process bugs
(#1615), auto-detect fragility in worktree contexts

### 3. Hooks → Local Enforcement and Surfacing

**Role:** Synchronous, zero-latency guardrails and context injection at
tool-use boundaries.

**Evidence:**
- `pre-merge-review-guard.sh` blocks unsafe merges without any transport
  dependency
- `post-merge-notify.sh` fires task-completion lifecycle on a best-effort basis (env-var lookup may miss lane identity)
- `session-sync-worktree.sh` keeps worktrees fresh on session start
- Hook latency is zero (in-process); no polling, no queue

**Architecture:** Hooks should read the controller projection
(`fleet_status.json`) produced by the controller module (SP-4-07
Deliverable 1). They enforce state that is already computed — they do
not compute it themselves.

**Not suitable for:** Cross-session communication, remote delivery,
persistent state management

### 4. tmux Nudges → Best-Effort Pane Wake-Up

**Role:** Inject `/start-task <packet_id>` into dormant author-lane panes
to trigger task consumption.

**Evidence:**
- `dispatch_to_worker()` + `nudge_pane()` successfully woke all 12 worker
  lanes during the proving run
- The nudge payload is a Claude Code slash-command, not arbitrary text
- Delivery is best-effort; the durable task packet is the source of truth

**Constraint:** Nudges must never be the only delivery mechanism. The
durable task packet + inbox message exist independently. If the nudge
fails, the lane can discover its task via `task list` on next check-in.

**Not suitable for:** Reliable delivery, any state management, orchestrator
interrupts (risk of corrupting in-flight generation)

### 5. Native SendMessage / Inboxes → Optional Import Source

**Role:** Capture cross-session messages that Claude Code itself may
generate via `SendMessage`, and import them into the repo-owned bus for
unified visibility.

**Evidence:**
- `import_native_inbox()` works idempotently with content-hash dedup (80 LOC)
- Format is undocumented and has changed between Claude Code versions
- No ack mechanism; no structured metadata; no escalation capability
- The overnight run did not use native messaging for any operational purpose

**Decision:** Native inboxes remain an optional import source. They are
not promoted to canonical workflow truth. The bridge (`import_native_inbox`)
stays as a convenience layer. If Claude Code's native messaging gains
richer semantics (TTL, ack, structured metadata) in a future version,
this decision should be revisited.

**Not suitable for:** Primary coordination, urgent alerts, any workflow
where ack/escalation matters

---

## Answering the #1289 Options

Issue #1289 proposed three options for transport consolidation:

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **A. Migrate toward native** | **Reject** | Native inboxes lack ack lifecycle, structured metadata, and escalation. The format is undocumented and unstable. Migration would lose the operational capabilities the platform depends on. |
| **B. Keep bridge permanently** | **Accept** | The bridge is 80 LOC, idempotent, and low-maintenance. It provides unified visibility without coupling to native format changes. The custom bus remains canonical; native is imported. |
| **C. Consolidate on custom bus only** | **Reject (partial)** | The custom bus is already canonical for structured coordination. But suppressing native messaging entirely would fight built-in Claude behavior. The import bridge is cheaper than suppression. |

**Recommended disposition for #1289:** Close with "Option B — keep bridge
permanently" as the decision. The transport comparison matrix above provides
the evidence.

---

## Answering #1571 (Messaging Re-Evaluation)

Issue #1571 identified that the messaging system is write-only in practice
because the orchestrator never reads its inbox.

**This ADR's answer:** The solution is not a transport change. It is a
control-plane change:

1. **Controller projection** (SP-4-07 Deliverable 1) derives actionable
   state from all sources including the message bus
2. **Hook-based surfacing** (SP-4-07 Deliverable 2) injects unresolved
   urgent state into the orchestrator's context at tool-use boundaries
3. **The custom bus stays pull-based** — but the controller + hooks make
   pull happen automatically, closing the "never reads inbox" gap

This keeps transport simple while making consumption reliable.

---

## Interaction Model

```
                     ┌─────────────────────┐
                     │  Controller Module   │
                     │ (fleet_status.json)  │
                     └────────┬────────────┘
                              │ reads
          ┌───────────┬───────┼───────┬─────────────┐
          ▼           ▼       ▼       ▼             ▼
   ┌──────────┐ ┌─────────┐ ┌────┐ ┌────────┐ ┌──────────┐
   │Custom Bus│ │ Monitor │ │Task│ │ Review │ │  Audit   │
   │(messages)│ │(findings)│ │Pkts│ │Verdicts│ │(remote)  │
   └──────────┘ └─────────┘ └────┘ └────────┘ └──────────┘

   Controller projection consumed by:
          │
          ├── Hooks (local enforcement, context injection)
          ├── Dashboard (operator visibility)
          ├── Channels (remote push to operator)
          └── tmux nudges (best-effort lane wake-up)
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Telegram plugin unreliable (#1521) | Keep tmux nudges as fallback; audit trail captures missed messages |
| Native inbox format changes between Claude versions | Bridge imports are idempotent; format changes cause import failures (logged), not data loss |
| Hook overhead grows with controller state | Controller projection is a single JSON file read; hooks remain O(1) |
| Custom bus JSONL grows unboundedly | Auto-compaction at 200 lines; tiered retention (4h handled, 1h terminal) already implemented |
| Multiple transports increase operator cognitive load | Controller projection unifies all sources into one actionable view; operators read `fleet_status.json`, not individual transports |

---

## Outcome

This ADR closes #1289 (transport consolidation) with Option B (keep bridge
permanently). It narrows #1571 (messaging re-evaluation) to a control-plane
problem, not a transport problem.

The five transports remain in their proven roles. No consolidation is needed
because each transport serves a distinct purpose with non-overlapping strengths.
The controller projection (SP-4-07 Deliverable 1) is the unifying layer that
makes transport choice subordinate to control-plane truth.
