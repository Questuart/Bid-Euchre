# Platform-8 Scope Lock

**ID:** SP-4-01
**Date:** 2026-03-23
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Platform-8
**Status:** completed
**Owner:** author-scratch

---

## Inputs

- `plans/agent_ops/4_remote_channel/plan.md` -- Phase 4 plan with discovery notes
- `plans/agent_ops/4_remote_channel/checkpoints.md` -- Phase 4 progress tracking
- Claude Code Channels reference: <https://code.claude.com/docs/en/channels-reference>
- Official Telegram plugin: <https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram>

## Assumptions

- Claude Code v2.1.80+ is available (or will be before Step 1 execution begins)
- The official Telegram plugin provides pairing, sender gating, and permission relay
- Bun runtime is available for plugin execution
- Active claude.ai login is available on the steward host

## Dependencies

- Phase 3 COMPLETE (satisfied)
- No sub-plan dependencies within Phase 4 (this is the first action)

## Plan

### Platform-8a: Configure Official Telegram Plugin

The official Channels framework (v2.1.80+) provides the transport skeleton,
sender gating, and permission relay. Platform-8a scope is reduced from
"build transport skeleton" to "configure and prove the official plugin."

**Steps (mapped to checkpoints Step 1):**

1. **Preflight verification** -- confirm Claude Code version >= 2.1.80,
   Bun availability, plugin resolvability, and auth prerequisites
2. **Plugin configuration** -- set up Telegram bot token, configure
   `STEWARD_CHANNELS="telegram"` in tmux launcher, add `--channels telegram`
   flag to session launch
3. **Pairing proof** -- pair from phone via QR/pairing code, verify sender
   gating rejects unknown senders
4. **Permission relay proof** -- trigger a tool-approval prompt, approve
   remotely from phone (v2.1.81+ for permission relay)
5. **Kill switch proof** -- terminate channel subprocess, verify session
   continues without channel, reconnect by restarting subprocess
6. **Registry integration** -- record channel status in lane metadata via
   `write_lane_metadata`

**Key decisions:**
- Free-form messages allowed (no remote command grammar)
- Orchestrator is the single ingress point for remote messages
- Author lanes remain tmux-only unless explicitly opted in
- Kill switch = terminate channel subprocess (graceful degradation)

### Platform-8b: Audit Trail -- DEFERRED

Audit trail is deferred to Platform-9c hardening phase (tracked in issue #1324).

**Rationale:**
- v1 relies on session logs + Telegram chat history
- Repo-owned structured audit trail adds value for cross-session analysis
  but is not blocking for the v1 remote supervision use case
- Hardening phase is the natural home for structured logging improvements

## Files Changed

- `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` -- NEW: this sub-plan
- `plans/agent_ops/sub_plan_registry.md` -- register SP-4-01
- `plans/agent_ops/4_remote_channel/checkpoints.md` -- add Step 0, update session log

## Validation

- [x] Sub-plan follows template structure
- [x] Registered in sub-plan registry
- [x] Checkpoints updated with Step 0 (scope lock) entry
- [x] `make check-quiet` passes

## Planned Outputs

- `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` -- this sub-plan
- Updated `plans/agent_ops/sub_plan_registry.md` with SP-4-01 entry
- Updated `plans/agent_ops/4_remote_channel/checkpoints.md` with Step 0

## Observed Outputs

- Sub-plan created at planned path
- Registry updated with SP-4-01 (completed)
- Checkpoints updated with Step 0 COMPLETE, session log entry added

## Outcome

- Status: completed
- PR: (this PR)
- Deviations from plan: none
- Issues discovered: none
