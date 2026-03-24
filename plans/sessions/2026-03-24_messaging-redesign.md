# Messaging System Redesign

> Design document for #1571: holistic messaging system re-evaluation.
> **Status:** DRAFT
> **Author:** author-scratch
> **Date:** 2026-03-24
> **Scope:** Design only — no implementation code.

## Context

The overnight autonomous run (2026-03-24c) proved the messaging bus is
mechanically reliable: ops sent 25+ `supervisor_alert` messages, author
lanes sent completion messages, and JSONL+flock persistence worked
correctly. The failure was architectural: the orchestrator never read its
inbox, so the entire alert pipeline was write-only.

Three stalled PRs (#1556, #1560, #1561) sat with merge conflicts for
7 hours because the orchestrator had no mechanism to receive or be
interrupted by the ops monitor's HIGH-severity findings.

### Current Architecture

```
src/bid_euchre/ops/message_bus.py  (1484 lines)
```

| Property | Current Behavior |
|----------|-----------------|
| Transport | Append-only JSONL per lane (`inbox/<lane_id>.jsonl`) |
| Delivery | Pull only — `read_inbox()` must be called explicitly |
| Priority | Field exists (`low/normal/high/urgent`) but no processing distinction |
| Ack tracking | `pending→delivered→acked→resolved` lifecycle, but no escalation on non-ack |
| Dedup | Content-based dedup on `(to, from, type, summary)` |
| Compaction | Auto-compact at 200 raw lines; tiered retention (4h handled, 1h terminal) |
| Expiry | TTL-based auto-expire on read (default 24h) |
| Cross-worktree | Via `shared_bus_root()` from `git --git-common-dir` |

### Message Types

```python
VALID_MESSAGE_TYPES = {
    "assignment", "ack", "progress", "blocker",
    "completion", "escalation", "recovery", "supervisor_alert",
}
```

### Status Transitions

```
pending → {delivered, acked, expired, dead_lettered}
delivered → {acked, expired, dead_lettered}
acked → {resolved}
resolved, expired, dead_lettered → (terminal)
```

**Known bug:** `_expire_stale_on_read()` tries to expire already-acked
messages, hitting the `acked→expired` transition guard (ValueError).
This crashed `task accept` during this session. Fix: skip messages in
`acked` status during TTL expiry checks.

---

## Design Question 1: Push vs Pull

### Current Behavior

Pure pull. The orchestrator must explicitly call:
```bash
uv run python scripts/internal/ops.py inbox --lane orchestrator
```
Nothing forces, triggers, or reminds the orchestrator to do this.

### Options

| Option | Mechanism | Tradeoffs |
|--------|-----------|-----------|
| **A. tmux send-keys interrupt** | Ops sends `tmux send-keys -t orchestrator "/check-inbox"` after HIGH alert | + Immediate delivery, reuses existing tmux infra. − Can corrupt in-flight prompts; race conditions with active generation. |
| **B. Sentinel file + hook** | Write `.claude/runtime/interrupt_orchestrator` file; a `PreToolUse` or cron hook checks for it | + Non-invasive (no prompt injection). + Works during generation pauses. − Requires a hook or cron polling (adds latency). |
| **C. System-reminder injection** | Not possible — no API to inject `<system-reminder>` into another session | N/A — platform constraint |
| **D. Mandatory inbox poll in every monitoring cycle** | Orchestrator's `/check-in` skill and `/run-fleet` skill include inbox read as step 1 | + Zero new infrastructure. + Contractual (skill text is authoritative). − Only works if orchestrator actually runs check-in cycles. Overnight showed it didn't. |
| **E. Cron-based inbox poll** | `CronCreate` a recurring job in the orchestrator pane that reads inbox | + Guaranteed cadence even if orchestrator forgets. + Self-contained. − Cron jobs survive `/clear` (#1580). − Adds token cost per poll. |

### Recommendation: D + E (belt and suspenders)

**Primary (D):** Update `/run-fleet` and `/check-in` skills to mandate inbox
polling as the **first** action in every monitoring cycle. This is zero-cost
and makes the contract explicit.

**Backup (E):** On orchestrator boot, create a cron job that polls the inbox
every 5 minutes. If there are pending P0 messages, the cron handler surfaces
them in the orchestrator's context. This catches the case where the
orchestrator gets absorbed in a long task and skips check-in cycles.

**Not recommended:** Option A (tmux injection) is too fragile — it can
corrupt active prompts and has no way to know if the orchestrator is
mid-generation. Option B adds unnecessary infrastructure when cron already
exists.

### Dependencies

- #1580: `/clear` must kill cron jobs — otherwise the inbox poll cron survives
  lane shutdown and wastes tokens on a parked orchestrator.

---

## Design Question 2: Priority Tiers

### Current Behavior

The `priority` field exists on every `BusMessage` with values
`low/normal/high/urgent`, but `read_inbox()` treats all messages equally.
There is no sorting, filtering, or differential processing based on priority.

### Proposed Tier Model

| Tier | Priority Values | Processing | Examples |
|------|----------------|------------|----------|
| **P0 (interrupt)** | `urgent` | Process immediately; trigger push notification (Q1 backup cron) | Lane crash, merge blocker, stuck CI for >30min |
| **P1 (next-cycle)** | `high` | Process before any new dispatch in the current cycle | supervisor_alert with HIGH findings, completion messages, review verdicts |
| **P2 (batch)** | `normal`, `low` | Process when convenient; compact aggressively | Routine progress acks, info-only monitor findings |

### Implementation Sketch

```python
# In read_inbox() or a new priority_read():
def read_inbox_prioritized(lane_id, ...):
    msgs = read_inbox(lane_id, status="pending", ...)
    p0 = [m for m in msgs if m["priority"] == "urgent"]
    p1 = [m for m in msgs if m["priority"] == "high"]
    p2 = [m for m in msgs if m["priority"] in ("normal", "low")]
    return p0, p1, p2
```

### Recommendation

Add `read_inbox_prioritized()` as a convenience wrapper. Don't change
`read_inbox()` itself (backward compatibility). The orchestrator's inbox
poll (Q1) calls the prioritized version and processes P0 before P1 before P2.

### Mapping: Message Type → Default Priority

| Message Type | Default Priority | Rationale |
|-------------|-----------------|-----------|
| `supervisor_alert` (with HIGH findings) | `high` (P1) | Already set by `monitor.py` |
| `supervisor_alert` (no HIGH findings) | `normal` (P2) | Info-only, batch |
| `completion` | `high` (P1) | Unblocks dispatch |
| `blocker` | `urgent` (P0) | Requires immediate attention |
| `escalation` | `urgent` (P0) | Auto-generated from unacked P1 |
| `recovery` | `high` (P1) | Resolution of a prior alert |
| `assignment` | `normal` (P2) | Already handled by task dispatch |
| `ack` | `low` (P2) | Informational only |
| `progress` | `low` (P2) | Informational only |

### Dependencies

None — this is an additive change to message_bus.py.

---

## Design Question 3: Bilateral Acknowledgement

### Current Behavior

Messages have ack lifecycle (`pending→acked→resolved`) but:
- **Senders don't check** whether recipients acked their messages.
- **No timeout** on pending messages (except 24h TTL expiry).
- **No escalation** when messages go unacknowledged.

The ops monitor sends alerts and forgets about them. It has no feedback loop
to detect that the orchestrator is ignoring its output.

### Proposed Ack Protocol

```
Sender (ops)                              Recipient (orchestrator)
    |                                           |
    |--- supervisor_alert (P1, pending) ------->|
    |                                           |
    |   [recipient reads inbox]                 |
    |                                           |--- ack_message() --->
    |                                           |
    |<-- ack event (via events.jsonl) ----------|
    |                                           |
    |   [sender queries ack status]             |
    |                                           |
    |   IF unacked after 2 cycles:              |
    |--- escalation (P0, urgent) -------------->|
    |                                           |
    |   IF still unacked after 2 more cycles:   |
    |--- [autonomous corrective action] --------|
```

### Ack Tracking Mechanism

**Option A: Sender polls recipient inbox**
The sender calls `read_inbox(recipient, message_id=X)` to check status.
- Pro: No new infrastructure.
- Con: Cross-lane inbox reads feel like a violation of encapsulation.

**Option B: Ack-back message**
When recipient acks, a reverse `ack` message is auto-sent to the sender.
- Pro: Clean separation — sender only reads its own inbox.
- Con: Doubles message volume; more complex lifecycle.

**Option C: Shared ack ledger**
A separate `ack_ledger.jsonl` file tracks `(message_id, acked_at, acked_by)`.
- Pro: Single source of truth for ack status across all lanes.
- Con: New file, new locking, new API surface.

### Recommendation: Option A (sender polls) with escalation helper

Add a helper function:

```python
def check_ack_status(
    message_id: str,
    recipient_lane: str,
    bus_root: Path | None = None,
) -> str:
    """Check if a message was acked by the recipient.
    Returns: 'pending', 'acked', 'resolved', 'expired', etc.
    """
```

Add an escalation helper to the monitor:

```python
def escalate_unacked(
    lane_id: str,  # sender lane
    target_lane: str,  # recipient lane
    max_age_minutes: int = 10,
    bus_root: Path | None = None,
) -> list[str]:
    """Find unacked messages older than max_age_minutes, send escalation."""
```

Cross-lane inbox reads are already possible (same `shared_bus_root`), so
Option A requires no new infrastructure. The escalation helper wraps the
pattern: find my unacked outbound messages → check recipient's inbox →
send escalation for anything past the SLA.

### SLA Thresholds

| Priority | Ack SLA | Escalation Action |
|----------|---------|-------------------|
| P0 (urgent) | 5 min | Re-send as P0 + tmux nudge |
| P1 (high) | 10 min | Escalate to P0 |
| P2 (normal) | 30 min | Log warning, no escalation |
| P2 (low) | Never | No escalation |

### Dependencies

- Q1 (Push vs Pull): Escalation to P0 may trigger the backup cron interrupt.
- Q6 (Feedback Loop): The escalation helper is the core of the feedback loop.

---

## Design Question 4: Orchestrator Contract

### Current Behavior

No formal obligation. The orchestrator's `/run-fleet` skill mentions
"triage inbox" as step 4 of the initialization sequence, but:
- Nothing enforces this.
- The skill text is advisory, not mechanically checked.
- During the overnight run, the orchestrator skipped inbox checks entirely
  for 7+ hours.

### Proposed Contract

**Hard rules (enforceable):**

1. **Every dispatch cycle MUST begin with inbox poll.**
   The `/run-fleet` skill's dispatch loop must call `read_inbox_prioritized()`
   before evaluating any dispatch candidates. P0 messages block dispatch
   until handled.

2. **P0 messages block new dispatches.**
   If `read_inbox_prioritized()` returns any P0 messages, the orchestrator
   must process them before dispatching new work. This is the "stop and fix"
   rule.

3. **Cron inbox poll (backup).**
   On boot, create a 5-minute cron that reads the inbox. If P0/P1 messages
   are pending, surface them in context. This catches the case where the
   orchestrator is stuck in a long operation and isn't running dispatch cycles.

**Soft rules (advisory):**

4. **Ack within SLA.**
   The orchestrator should ack messages within the SLA thresholds (Q3).
   Failure to ack triggers escalation from the sender, which is self-correcting.

5. **Session-start inbox scan.**
   When `/recovering-context` runs, it should include a check for unacked
   P0/P1 messages from the previous session.

### Enforcement Mechanism

The contract is enforced through two complementary mechanisms:

- **Skill text** (primary): Update `/run-fleet` and `/check-in` to include
  inbox poll as mandatory step 1. Claude follows skill instructions.
- **Cron backup** (secondary): The 5-minute inbox poll cron ensures coverage
  even when the orchestrator deviates from the skill flow.

There is no hard programmatic enforcement (no hook that blocks dispatch on
unread inbox). The messaging system operates on trust + escalation rather
than mechanical gates. This is appropriate because:
- The orchestrator is a Claude session, not a programmatic pipeline.
- Mechanical gates would require hooks that interact with the session state,
  which is fragile.
- Escalation (Q3) provides a self-correcting feedback loop.

### Changes Required

| File | Change |
|------|--------|
| `.claude/skills/run-fleet/SKILL.md` | Add inbox poll as mandatory step 1 of every dispatch cycle |
| `.claude/skills/recovering-context/SKILL.md` | Add unacked P0/P1 inbox scan to session-start recovery |
| Orchestrator boot sequence | Add `CronCreate` for 5-min inbox poll |

### Dependencies

- Q1 (Push vs Pull): The cron backup is Option E from Q1.
- Q3 (Bilateral Ack): The ack SLA enforcement relies on Q3's escalation helper.

---

## Design Question 5: Cross-Session Durability

### Current Behavior

Messages persist in JSONL files across sessions (durable storage). However:
- **Session context is ephemeral.** After compaction or restart, the
  orchestrator loses awareness of unacked alerts.
- **MEMORY.md** does not track unacked messages.
- **`/recovering-context`** does not scan the inbox.
- **Compaction** aggressively purges: acked messages after 4h, terminal
  messages after 1h.

The result: messages survive restarts, but the orchestrator doesn't know
to look for them.

### Proposed Recovery Protocol

**On session start (via `/recovering-context`):**

```
1. Read MEMORY.md (existing)
2. Read inbox for pending P0/P1 messages (NEW)
3. If any exist:
   a. Surface them in context ("You have N unacked alerts from previous session")
   b. Process P0 messages before any other work
   c. Ack processed messages
4. Continue with normal recovery
```

**On compaction:**

Current tiered retention is acceptable for operational messages. But:
- **P0 messages should not expire.** Override TTL for `urgent` priority:
  set `ttl_seconds = None` (infinite) or a very long TTL (7 days).
- **Unacked P1 messages should have extended retention.** Increase
  `COMPACT_HANDLED_MAX_AGE_HOURS` for unacked `high` messages to 24h
  (vs current 4h for acked).

### Implementation Sketch

```python
# In _expire_stale_on_read(), skip urgent messages:
if rec.get("priority") == "urgent":
    continue  # P0 messages never auto-expire

# In compact_inbox(), use priority-aware retention:
if rec.get("priority") == "urgent" and rec.get("status") != "resolved":
    keep = True  # Always keep unresolved P0
elif rec.get("priority") == "high" and rec.get("status") == "pending":
    max_age = 24 * 3600  # 24h for unacked P1
```

### MEMORY.md Integration

After each session, if there are unacked P0/P1 messages, append a section
to MEMORY.md:

```markdown
### Unacked Alerts (carry-forward)
- [message_id] supervisor_alert from ops: "3 HIGH findings" (P1, pending since 14:30Z)
```

This ensures the next session's `/recovering-context` can find them even
without reading the inbox (belt and suspenders).

### Recommendation

1. Update `/recovering-context` to include inbox scan (primary).
2. Override TTL for P0 messages (prevent accidental expiry).
3. Extend retention for unacked P1 messages to 24h.
4. Add MEMORY.md carry-forward for unacked P0/P1 (secondary).

### Dependencies

- Q2 (Priority Tiers): Requires priority-aware retention to distinguish P0/P1/P2.
- Q4 (Orchestrator Contract): Session-start inbox scan is part of the contract.

---

## Design Question 6: Ops Monitor → Orchestrator Feedback Loop

### Current Behavior

One-way fire-and-forget:
```
ops → supervisor_alert → orchestrator inbox → (ignored)
ops → supervisor_alert → orchestrator inbox → (ignored)
ops → supervisor_alert → orchestrator inbox → (ignored)
... 25 times over 7 hours ...
```

The ops monitor has no feedback on whether the orchestrator received or
acted on its alerts. It keeps sending the same alert every cycle (3 min),
which creates inbox noise and wastes tokens, without any escalation.

### Proposed Feedback Loop

```
Cycle 1:  ops sends supervisor_alert (P1, high)
Cycle 2:  ops checks: was alert acked? No → increment stale counter
Cycle 3:  ops checks: stale_count >= 2 → ESCALATE
          ops sends escalation (P0, urgent) with parent_message_id
Cycle 4:  ops checks: was escalation acked? No → increment
Cycle 5:  ops checks: stale_count >= 2 → AUTONOMOUS ACTION
          ops takes corrective action (e.g., rebase stalled PRs)
```

### Escalation Tiers

| Stage | Trigger | Action |
|-------|---------|--------|
| **Alert** | Finding detected | Send `supervisor_alert` (P1) |
| **Escalation** | Alert unacked for 2 cycles (~6min) | Send `escalation` (P0), referencing the original alert via `parent_message_id` |
| **Autonomous action** | Escalation unacked for 2 more cycles (~6min) | Take safe corrective action without orchestrator approval |

### Safe Autonomous Actions

The ops monitor may take autonomous action only for a limited set of
well-defined, safe, and idempotent operations:

| Finding | Autonomous Action | Safety |
|---------|-------------------|--------|
| Merge conflict | `git fetch origin main && git rebase origin/main` in the affected worktree | Idempotent; worst case = rebase conflict, which is reported as new finding |
| Stale dispatched packet (>30min) | Transition packet to `failed`, free the lane | Idempotent; the lane can receive new work |
| CI failure on PR | Post a comment on the PR with the failure details | Idempotent; informational only |

Autonomous actions that are **NOT safe** without orchestrator approval:
- Closing PRs
- Force-pushing branches
- Deleting branches or worktrees
- Dispatching new work
- Modifying plan or checkpoint files

### Integration with Monitor Cycle

The existing `run_monitoring_cycle()` already sends findings to the bus.
Add a pre-send step that checks for unacked previous alerts:

```python
def run_monitoring_cycle(...):
    # NEW: Check for unacked alerts from previous cycles
    unacked = check_unacked_alerts("ops", "orchestrator", max_age_minutes=6)
    if unacked:
        for msg_id in unacked:
            escalate_to_p0(msg_id)

    # Existing: collect findings
    findings = ...
    # Existing: send to bus
    _send_findings_to_bus(findings)
```

### Content Dedup Interaction

The existing `_content_dedup_key()` deduplicates on
`(to_lane, from_lane, message_type, summary)`. This means repeated
supervisor_alerts with the same summary are silently dropped. This is
**correct for alerts** (prevents inbox flooding) but **wrong for
escalations** (each escalation should be delivered even if the summary
is similar).

Fix: escalation messages should use `deduplicate=False` in `send_message()`,
or include the escalation round number in the summary to make the dedup
key unique.

### Recommendation

1. Add `check_ack_status()` and `escalate_unacked()` helpers to message_bus.py.
2. Integrate escalation check into `run_monitoring_cycle()` as a pre-send step.
3. Define the safe autonomous action list (above) and implement as a
   separate function (`autonomous_recovery()`).
4. Use `parent_message_id` to chain escalations to their original alerts
   for traceability.
5. Escalation messages use `deduplicate=False` or unique summaries.

### Dependencies

- Q3 (Bilateral Ack): `check_ack_status()` and `escalate_unacked()` are shared.
- Q2 (Priority Tiers): Escalation uses the P0 tier.
- Q1 (Push vs Pull): P0 escalations trigger the backup cron interrupt.

---

## Implementation Roadmap

### Phase 1: Foundation (3-4 PRs, ~1 session)

| PR | Scope | Depends On |
|----|-------|------------|
| **1a** | Fix `acked→expired` transition bug in `_expire_stale_on_read()` | None |
| **1b** | Add `read_inbox_prioritized()` to message_bus.py | None |
| **1c** | Add `check_ack_status()` + `escalate_unacked()` to message_bus.py | None |
| **1d** | Update `/run-fleet` + `/recovering-context` skills for inbox contract | None |

### Phase 2: Integration (2-3 PRs, ~1 session)

| PR | Scope | Depends On |
|----|-------|------------|
| **2a** | Priority-aware retention in compaction + P0 TTL override | 1b |
| **2b** | Escalation check in `run_monitoring_cycle()` pre-send step | 1b, 1c |
| **2c** | Orchestrator boot cron for inbox polling | 1d |

### Phase 3: Autonomous Recovery (1-2 PRs, ~1 session)

| PR | Scope | Depends On |
|----|-------|------------|
| **3a** | Safe autonomous actions for merge-conflict + stale-packet recovery | 2b |
| **3b** | Lane shutdown procedure (CronDelete before /clear) | #1580 |

### Phase 4: Testing & Validation (1-2 PRs)

| PR | Scope | Depends On |
|----|-------|------------|
| **4a** | Bilateral messaging smoke test (#1570) | 1b, 1c |
| **4b** | Escalation integration test (mock monitor cycles) | 2b |

### Estimated Total: 8-11 PRs across 3-4 sessions

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cron backup survives /clear and wastes tokens | High | Low | Fix #1580 first (Phase 3b) |
| Autonomous recovery takes unsafe action | Low | High | Whitelist-only actions; explicit "safe" flag |
| Escalation cascade (P1→P0→action before orchestrator can respond) | Medium | Medium | 6-min delay between tiers; orchestrator ack resets the timer |
| Priority-aware retention causes P0 inbox bloat | Low | Low | Cap P0 at 7-day TTL; resolve terminal states |
| Skill text changes don't enforce behavior | Medium | Medium | Cron backup is the mechanical safety net |

---

## Decisions NOT Made Here

These are explicitly deferred to implementation PRs:

1. **Exact cron interval** for orchestrator inbox poll (5min proposed, may tune).
2. **Whether to add a new message type** (`interrupt`) vs reusing `escalation`.
3. **Telegram integration** for P0 alerts — the Telegram channel (#1521) is
   unreliable; use it as a future enhancement, not a dependency.
4. **Dashboard integration** — priority inbox status in the ops dashboard
   would be useful but is out of scope for the messaging redesign.

---

## Related Issues

| Issue | Relationship |
|-------|-------------|
| #1568 | Merge-conflict stall detection — motivating failure |
| #1569 | Orchestrator inbox polling gap — root cause |
| #1570 | Bilateral messaging tests — validation for Q3/Q6 |
| #1571 | This design doc's parent issue |
| #1572 | Idle auto-shutoff — related to cron lifecycle |
| #1580 | /clear doesn't kill crons — dependency for Phase 3b |

## Outcome

_To be filled after implementation._
