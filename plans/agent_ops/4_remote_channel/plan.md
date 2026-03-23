# Phase 4 — Remote Operator Channels

**Status:** PENDING (scope lock not yet entered)
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Slices:** Platform-8 (Remote Operator Channel), Platform-9 (Idle Attention Flow)
**Depends on:** Phase 3 (COMPLETE)

## Discovery: Official Claude Code Channels

> **Reference:** <https://code.claude.com/docs/en/channels-reference>

Claude Code v2.1.80+ ships a Channels feature (research preview) with pre-built
Telegram and Discord plugins. Key capabilities:

| Capability | Description |
|------------|-------------|
| **Pairing** | Phone pairs to running Claude session via QR code / pairing code |
| **Sender gating** | Only the paired account can send messages to the session |
| **Reply tools** | Structured reply/approval surfaces in Telegram/Discord |
| **Permission relay** | Remote tool-approval from phone — approve/deny tool calls without terminal access |
| **Kill switch** | Terminate the channel subprocess to disconnect immediately |

This discovery significantly reduces Platform-8 scope: the transport skeleton,
sender gating, and permission relay are provided by the framework rather than
built from scratch.

### Prerequisites

- Claude Code v2.1.80+ (`claude --version`)
- Active claude.ai login (`claude auth status`)
- `--channels telegram` flag in session launch
- Bun runtime (for official Telegram plugin)

## Platform-8a — Telegram Plugin Configuration and Proving

**Scope (updated from "build transport skeleton"):** Configure the official
Telegram plugin, prove pairing + sender gating + permission relay + kill switch
in the steward environment.

### Steps

1. **Preflight verification** — confirm Claude Code version, Bun availability,
   plugin resolvability, and auth prerequisites
2. **Plugin configuration** — set up Telegram bot token, configure
   `STEWARD_CHANNELS="telegram"` in tmux launcher
3. **Pairing proof** — pair from phone, verify sender gating rejects unknown
   senders
4. **Permission relay proof** — trigger a tool-approval prompt, approve remotely
   from phone
5. **Kill switch proof** — terminate channel subprocess, verify session continues
   without channel
6. **Registry integration** — record channel status in lane metadata via
   `write_lane_metadata`

### Done when

- Telegram plugin pairs successfully with the steward session
- Sender gating rejects messages from non-paired accounts
- Permission relay enables remote tool approval
- Kill switch terminates channel cleanly without affecting the session
- Lane registry records channel health status

## Platform-8b — Audit Trail (Deferred to Hardening)

> **Known gap:** v1 relies on session logs + Telegram chat history for audit
> trail. A repo-owned audit trail (structured log of all channel
> messages/approvals) is deferred to Platform-14 (hardening phase).

This is a conscious deferral, not a missing requirement. The rationale:

- Session logs capture all tool approvals and their outcomes
- Telegram chat history preserves the operator-side conversation
- A repo-owned structured audit trail adds value for cross-session analysis
  but is not blocking for the v1 remote supervision use case
- Hardening phase (Platform-14) is the natural home for structured logging
  and operational observability improvements

## Platform-9 — Idle Attention Flow

**Scope:** Prove idle-attention alerts with dedupe and ack through the
configured Telegram channel.

### Steps

1. **Idle detection** — ops supervisor detects lanes awaiting user attention
   for >5 minutes
2. **Alert routing** — summarized alert sent through Telegram channel
3. **Dedupe and backoff** — prevent duplicate alerts for the same idle event
4. **Acknowledgement handling** — operator ack via Telegram reply is recorded
   in durable coordination state
5. **Bounded reply mapping** — Telegram replies map to bounded inbound commands
   (inspect, reroute, pause, summarize)

### Done when

- Idle-attention alerts fire after 5-minute threshold
- Alerts are deduplicated and rate-limited
- Acknowledgements and bounded replies are recorded durably

## Phase 4 Operating Model

### Permission Relay in v1

Permission relay enables remote tool approval from phone. This is a key
Platform-8 feature that was not anticipated in the original plan but is
provided by the official Channels framework.

In the v1 operating model:
- Orchestrator and ops lanes receive `--channels telegram` by default
- Author lanes remain tmux-only unless explicitly opted in
- Permission relay is available on channel-enabled lanes
- The operator can approve/deny tool calls from Telegram without terminal access

### Channel Lifecycle

```
Session start
  -> preflight check (version, auth, plugin)
  -> if pass: launch with --channels telegram
  -> if fail: fall back to tmux-only (no degradation)

During operation:
  -> pairing on first connect
  -> sender gating on all inbound messages
  -> permission relay on tool-approval prompts
  -> idle alerts on 5-minute attention threshold

Kill switch:
  -> terminate channel subprocess
  -> session continues without channel
  -> reconnect by restarting channel subprocess
```
