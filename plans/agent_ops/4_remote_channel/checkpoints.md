# Remote Channel Checkpoints

**Phase:** 4 (`4_remote_channel`)
**Status:** IN_PROGRESS
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-23 by author-scratch (register SP-4-02)

---

### Step 0 — Scope lock and sub-plan registration

**Status:** COMPLETE
**Description:** Create SP-4-01 sub-plan for Platform-8 scope lock, register in
sub-plan registry, and update checkpoints. Docs-only — no code changes.
**Depends on:** Phase 3 COMPLETE
**Done when:**
- SP-4-01 sub-plan exists at `sub/2026-03-23_platform-8-scope-lock.md`
- Sub-plan registered in `plans/agent_ops/sub_plan_registry.md`
- Checkpoints updated with Step 0 entry and session log

### Step 1 — Platform-8a: Configure Telegram plugin and prove core capabilities

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Phase 4 scope lock and sub-plan registration | COMPLETE | 2026-03-23 | author-scratch | SP-4-01 created and registered. |
| Step 1: Platform-8a preflight and Telegram transport skeleton | PENDING | -- | -- | Verify channel prerequisites, transport choice, kill switch shape, and fallback path. |
| Step 2: Platform-8b repo-owned remote audit trail, kill switch, and operator fallback | PENDING | -- | -- | Every inbound/outbound exchange durably logged before wider proving use. |
| Step 3: Platform-9a idle-attention alerts and acknowledgement loop | PENDING | -- | -- | Prove one useful alert path with dedupe, rate limiting, and ack behavior. |
| Step 4: Platform-9b away-from-desk queue-moving proving run | PENDING | -- | -- | Demonstrate status, reroute, review request, and blocker inspection through `orchestrator`. |
| Step 5: Platform-9c first hardening pass and Phase 4 handoff | PENDING | -- | -- | Fix real proving-run issues, update docs, and record known gaps. |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-4-01 | `sub/2026-03-23_platform-8-scope-lock.md` | completed | Step 0 |
| SP-4-02 | `sub/2026-03-23_remote-ops-preflight-hardening.md` | in_progress | Pre-Platform-8 |

## Blockers

- [x] ~~SP-3-05 dual-domain steward layout transition~~ — COMPLETE (2026-03-23).
  Dual-domain layout shipped in pre-proving hardening session (PRs #1281–#1294).
  Proving run passed 2026-03-23. Phase 4 scope lock is unblocked.

## Session Log

| Date | Summary |
|------|---------|
| 2026-03-23 | Phase 4 plan and checkpoints created. Official Claude Code Channels discovery (v2.1.80+) reduces Platform-8a scope from "build transport skeleton" to "configure official Telegram plugin." Permission relay and sender gating are framework-provided. Audit trail deferred to hardening (Platform-14). |
| 2026-03-23 | SP-3-05 blocker cleared. Dual-domain layout shipped (PRs #1281–#1294), proving run passed. 4-window tiled layout canonical, 12 worker lanes active across platform/browser-game/flex pools. |
| 2026-03-23 | Step 0 (scope lock): SP-4-01 sub-plan created and registered. Key decisions: free-form messages allowed, no remote command grammar, orchestrator is single ingress, author lanes remain tmux-only. Platform-8b audit trail tracked in issue #1324. Phase status moved from PENDING to IN_PROGRESS. |
| 2026-03-23 | SP-4-02 registered and committed. Preflight hardening plan covers 6 steps: lifecycle proving, operational cleanup, stall recovery, scope enforcement, reset/clear validation, and auto-dispatch. Gated rollout order (Steps 1-2 first, then 3-4 parallel, then 5-6). |
