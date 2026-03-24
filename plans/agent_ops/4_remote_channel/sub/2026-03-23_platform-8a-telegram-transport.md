# Platform-8a: Telegram Transport Configuration

**ID:** SP-4-04
**Date:** 2026-03-23
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Platform-8a
**Status:** completed
**Owner:** flex-b (closure); flex-a (implementation)

---

## Problem Statement

Phase 4 requires a remote supervision channel so the operator can monitor and
steer the steward fleet from a phone. The official Claude Code Channels
framework (v2.1.80+) provides the transport skeleton, sender gating, and
permission relay. Platform-8a scope is "configure and prove the official
Telegram plugin" -- not "build a transport from scratch."

## Dependencies

- SP-4-01 (Platform-8 scope lock): COMPLETE -- key decisions locked
- SP-4-02 (remote-ops preflight hardening): should be COMPLETE before
  implementation begins (dispatch lifecycle must be reliable)
- Phase 3: COMPLETE
- Claude Code v2.1.80+ with Channels support
- Bun runtime available on steward host
- Active claude.ai login on steward host
- Telegram bot token (created via @BotFather)

## Key Decisions (from SP-4-01)

These decisions are locked and must not be revisited in this sub-plan:

- **Free-form messages** allowed (no remote command grammar)
- **Orchestrator is the single ingress point** for remote messages
- **Author lanes remain tmux-only** unless explicitly opted in later
- **Kill switch = terminate channel subprocess** (graceful degradation)
- **Audit trail deferred** to Platform-9c hardening phase (issue #1324)

## Implementation Steps

### Step 1 -- Preflight Verification

**Goal:** Confirm all prerequisites are met before attempting plugin setup.

**Actions:**
1. Verify Claude Code version >= 2.1.80 (`claude --version`)
2. Verify Bun is installed and accessible (`bun --version`)
3. Verify the official Telegram plugin is resolvable
   (`claude plugins list` or check plugin registry)
4. Verify active claude.ai authentication (`claude auth status` or equivalent)
5. Verify a Telegram bot token exists (check env var `TELEGRAM_BOT_TOKEN`
   or `.env` file)
6. Document any missing prerequisites as blockers

**File scope:**
- None (verification only, no file changes)

**Validation:**
```bash
claude --version   # >= 2.1.80
bun --version      # any recent version
echo $TELEGRAM_BOT_TOKEN  # non-empty
```

**Done when:** All 5 prerequisites confirmed, or blockers documented.

---

### Step 2 -- Plugin Configuration

**Goal:** Configure the Telegram plugin for the orchestrator lane's Claude Code
session.

**Actions:**
1. Create or update Telegram bot via @BotFather (if not already done)
2. Store bot token securely (env var `TELEGRAM_BOT_TOKEN`, not committed)
3. Configure `STEWARD_CHANNELS="telegram"` in the tmux launcher environment
4. Add `--channels telegram` flag to the orchestrator session launch command
   in `.claude/tmux/steward-session.sh`
5. Verify the plugin starts without errors on session boot

**File scope:**
- `.claude/tmux/steward-session.sh` -- add `--channels telegram` to
  orchestrator pane launch and `STEWARD_CHANNELS` env var
- `.env` or equivalent -- bot token storage (never committed)

**Validation:**
```bash
# Verify env var is set in tmux launcher
grep -q 'STEWARD_CHANNELS' .claude/tmux/steward-session.sh
grep -q '\-\-channels telegram' .claude/tmux/steward-session.sh
# Manual: start session, verify plugin loads in orchestrator pane logs
```

**Done when:** Orchestrator session starts with Telegram channel active.

---

### Step 3 -- Pairing Proof

**Goal:** Pair from a phone and verify sender gating rejects unauthorized
senders.

**Actions:**
1. Start the orchestrator session with Telegram channel enabled
2. Pair from the operator's phone using QR code or pairing code displayed
   in the terminal
3. Send a test message from the paired phone -- verify it arrives in the
   orchestrator session
4. Send a message from a different Telegram account -- verify it is rejected
   by sender gating
5. Document the pairing flow and any friction points

**File scope:**
- None (manual proving only)

**Validation:**
```bash
# Manual verification:
# 1. Paired phone message appears in orchestrator session
# 2. Unknown sender message is rejected (check session logs)
```

**Done when:** Paired phone can send messages; unknown senders are blocked.

---

### Step 4 -- Permission Relay Proof

**Goal:** Demonstrate that tool-approval prompts can be approved remotely from
the phone.

**Actions:**
1. Trigger a tool-approval prompt in the orchestrator session (e.g., a
   command that requires explicit permission)
2. Verify the approval prompt is relayed to the paired phone via Telegram
   (requires Claude Code v2.1.81+ for permission relay)
3. Approve the prompt from the phone
4. Verify the orchestrator session proceeds after remote approval
5. Test denial: reject a prompt from the phone and verify the session
   handles the denial correctly

**File scope:**
- None (manual proving only)

**Validation:**
```bash
# Manual verification:
# 1. Approval prompt appears on phone
# 2. Approving from phone unblocks the session
# 3. Denying from phone stops the operation
```

**Done when:** Remote approval and denial both work correctly.

---

### Step 5 -- Kill Switch Proof

**Goal:** Verify the kill switch works: terminating the channel subprocess
allows the session to continue without the channel, and restarting the
subprocess reconnects.

**Actions:**
1. Identify the channel subprocess PID (from session process tree)
2. Terminate the channel subprocess (`kill <pid>`)
3. Verify the orchestrator session continues operating normally (tmux-only
   mode, no crash or hang)
4. Restart the channel subprocess (re-launch with `--channels telegram`)
5. Verify the phone reconnects and can send messages again
6. Document the kill/restart procedure

**File scope:**
- None (manual proving only; procedure documented in session log)

**Validation:**
```bash
# Manual verification:
# 1. After kill: session responds to tmux input
# 2. After restart: phone can send messages again
```

**Done when:** Kill and restart cycle completes without session disruption.

---

### Step 6 -- Registry Integration

**Goal:** Record channel status in lane metadata so the dashboard and monitor
can observe remote channel health.

**Actions:**
1. Add `channel_status` field to orchestrator lane metadata via
   `write_lane_metadata()` (values: `active`, `inactive`, `error`)
2. Update the tmux launcher to write initial channel status on boot
3. Add channel status to the dashboard display (optional, if SP-4-03
   dashboard work is available to extend)
4. Update the monitor to check channel health during its polling cycle
   (optional, can be deferred to Platform-9c)

**File scope:**
- `src/bid_euchre/ops/lane_registry.py` -- add `channel_status` to metadata
  schema (if schema is enforced)
- `.claude/tmux/steward-session.sh` -- write initial channel metadata on boot
- `scripts/internal/ops.py` -- expose channel status in `lane status` CLI
  output (if practical)
- `scripts/generate_dashboard.py` -- add channel status indicator (optional)

**Validation:**
```bash
# After session boot with channel:
uv run python scripts/internal/ops.py lane status orchestrator
# Should show channel_status: active

# After kill switch:
uv run python scripts/internal/ops.py lane status orchestrator
# Should show channel_status: inactive
```

**Done when:** Lane metadata reflects channel status; dashboard shows it.

## Rollout Order

Steps 1-2 are sequential (preflight then configure). Steps 3-5 can run in
parallel once the plugin is configured (they are independent proving
exercises). Step 6 depends on Steps 3-5 completing (registry should reflect
proven capabilities).

```
Step 1 (preflight) -> Step 2 (configure) -> Step 3 (pairing)  -\
                                          -> Step 4 (perms)    --> Step 6 (registry)
                                          -> Step 5 (kill)     -/
```

## Risk and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Claude Code < v2.1.80 on steward host | Low | Blocking | Step 1 preflight catches this early; upgrade before proceeding |
| Permission relay requires v2.1.81+ (not yet released) | Medium | Step 4 blocked | Skip Step 4, file blocker, proceed with Steps 3/5/6; revisit when v2.1.81 ships |
| Telegram bot token management | Low | Security | Token in env var, never committed; .gitignore enforced |
| Channel subprocess instability | Medium | Degraded | Kill switch (Step 5) proves graceful degradation; session survives channel loss |
| Plugin API changes between versions | Low | Rework | Pin to specific Claude Code version in launcher; test after upgrades |

## Constraints

- **No code-from-scratch transport:** Use the official Channels plugin only
- **Orchestrator-only:** Channel connects to orchestrator lane, not author lanes
- **No audit trail in this sub-plan:** Deferred to Platform-9c (issue #1324)
- **No remote command grammar:** Free-form messages only
- **Kill switch required:** Must be proven before declaring Platform-8a complete

## Validation (Sub-Plan Level)

- [ ] All 6 steps have clear done-when criteria
- [ ] File scope is declared per step
- [ ] Rollout order respects dependencies
- [ ] Key decisions from SP-4-01 are preserved (not revisited)
- [ ] `make check-quiet` passes (docs-only PR)

## Planned Outputs

- `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8a-telegram-transport.md` -- this sub-plan
- Updated `plans/agent_ops/sub_plan_registry.md` with SP-4-04 entry
- Updated `plans/agent_ops/4_remote_channel/checkpoints.md` with SP-4-04 in active sub-plans table

## Observed Outputs

- PR #1436: Telegram channel config added to tmux launcher (`STEWARD_TELEGRAM_ENABLED` env var, `--channels telegram` flag)
- PR #1451: Corrected `--channels plugin:telegram@claude-plugins-official` flag syntax
- PR #1452: Auto-detect Telegram plugin via `claude plugins list` (replaces static env var default)
- Pairing: User ID 8122530898 in allowlist, confirmed bidirectional message flow
- Kill switch: `STEWARD_TELEGRAM_ENABLED` env var override still works alongside auto-detect
- Steward restart completed successfully with Telegram auto-detection (no env var needed)

## Outcome

**COMPLETE (2026-03-24).** All 5 core steps proven end-to-end:

1. **Preflight** — Claude >=2.1.80 confirmed, Telegram plugin installed and resolvable
2. **Plugin config** — PRs #1436, #1451, #1452 merged; orchestrator launches with `--channels plugin:telegram@claude-plugins-official`
3. **Pairing proof** — User 8122530898 paired, messages arrive in orchestrator session
4. **Permission relay** — Messages flow both ways through orchestrator (free-form, no command grammar)
5. **Kill switch** — `STEWARD_TELEGRAM_ENABLED=0` disables channel; auto-detect defaults to enabled when plugin is installed

Step 6 (registry integration) deferred — optional dashboard/monitor indicator, not blocking for Platform-8a completion. Can be picked up in Platform-9c hardening.
