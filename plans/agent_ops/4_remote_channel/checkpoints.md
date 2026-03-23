# Phase 4 — Remote Operator Channels — Checkpoints

**Phase:** 4 (`4_remote_channel`)
**Status:** IN_PROGRESS
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase plan:** `plans/agent_ops/4_remote_channel/plan.md`

## Steps

### Step 0 — Scope lock and sub-plan registration

**Status:** COMPLETE
**Description:** Create SP-4-01 sub-plan for Platform-8 scope lock, register in
sub-plan registry, and update checkpoints. Docs-only — no code changes.
**Depends on:** Phase 3 COMPLETE
**Done when:**
- SP-4-01 sub-plan exists at `4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md`
- Sub-plan registered in `sub_plan_registry.md`
- Checkpoints updated with Step 0 entry and session log

### Step 1 — Platform-8a: Configure Telegram plugin and prove core capabilities

**Status:** PENDING
**Description:** Configure official Telegram plugin, prove pairing, sender
gating, permission relay, and kill switch in the steward environment.
**Depends on:** Phase 3 COMPLETE
**Done when:**
- Telegram plugin pairs with steward session
- Sender gating rejects unknown senders
- Permission relay enables remote tool approval
- Kill switch terminates channel without session disruption
- Lane registry records channel status

### Step 2 — Platform-9: Prove idle-attention alerts with dedupe and ack

**Status:** PENDING
**Description:** Prove idle-attention alerts with dedupe and ack through the
configured Telegram channel. Audit trail deferred to hardening (Platform-14).
**Depends on:** Step 1
**Done when:**
- Idle-attention alerts fire after 5-minute threshold
- Alerts are deduplicated and rate-limited
- Acknowledgement or bounded reply recorded in durable coordination state

### Step 3 — Batch E pass gate

**Status:** PENDING
**Description:** Verify Batch E pass gate criteria from the governing plan.
**Depends on:** Steps 1 and 2
**Done when:**
- One real away-from-keyboard idle-attention flow reaches Telegram successfully
- Acknowledgements and bounded replies are recorded durably
- Dedupe/backoff prevents noisy alert spam in a proving run

## Blockers

(none)

## Session Log

| Date | Summary |
|------|---------|
| 2026-03-23 | Phase 4 plan and checkpoints created. Official Claude Code Channels discovery (v2.1.80+) reduces Platform-8a scope from "build transport skeleton" to "configure official Telegram plugin." Permission relay and sender gating are framework-provided. Audit trail deferred to hardening (Platform-14). |
| 2026-03-23 | Step 0 (scope lock): SP-4-01 sub-plan created and registered. Key decisions: free-form messages allowed, no remote command grammar, orchestrator is single ingress, author lanes remain tmux-only. Platform-8b audit trail tracked in issue #1324. Phase status moved from PENDING to IN_PROGRESS. |
