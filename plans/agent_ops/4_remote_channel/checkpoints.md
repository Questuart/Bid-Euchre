# Remote Channel Checkpoints

**Phase:** 4 (`4_remote_channel`)
**Status:** IN_PROGRESS
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-25 by flex-c (SP-4-07 in_progress; Step 3 IN_PROGRESS with 13+ PRs shipped including controller live wiring, proving runs 1/3/4 passed)

---

### Step 0 — Scope lock and sub-plan registration

**Status:** COMPLETE
**Description:** Create SP-4-01 sub-plan for Platform-8 scope lock, register in
sub-plan registry, and update checkpoints. Docs-only — no code changes.
**Depends on:** Phase 3 COMPLETE
**Done when:**
- SP-4-01 sub-plan exists at `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md`
- Sub-plan registered in `plans/agent_ops/sub_plan_registry.md`
- Checkpoints updated with Step 0 entry and session log

### Step 1 — Platform-8a: Configure Telegram plugin and prove core capabilities

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Phase 4 scope lock and sub-plan registration | COMPLETE | 2026-03-23 | author-scratch | SP-4-01 created and registered. |
| Step 1: Platform-8a preflight and Telegram transport skeleton | COMPLETE | 2026-03-24 | flex-b | SP-4-04 all steps proven. PRs #1436, #1451, #1452 merged. Pairing confirmed (user 8122530898), messages flow both ways, kill switch verified. |
| Step 2: Platform-8b repo-owned remote audit trail and runtime wiring | IN_PROGRESS | 2026-03-24 | author-a + orchestrator | SP-4-06 shipped the audit library, but issue #1573 correctly reopens the slice: runtime callers, controller integration, and real inbound/outbound proving are still pending. PR #1616 fixed Telegram inbound (#1615) — ops lane moved to detached worktree to stop competing bun processes from consuming `getUpdates`. Inbound now proven working (test message confirmed 2026-03-24). |
| Step 3: SP-4-07 controller-first control plane and transport evaluation | IN_PROGRESS | 2026-03-24 | author-a + author-b + flex-c | PRs: #1618 (stabilization gate), #1633 (controller projection), #1650 (transport ADR), #1699 (controller wired into monitor cycle), #1701 (permission stall detection), #1703 (urgent TTL exemption), #1704 (fleet idle shutoff), #1707 (controller integration tests), #1708 (SKILL.md edit permission), #1712 (persistence/dedup proving), #1714 (false-stall regression proving), #1715 (outbound audit PostToolUse hook), #1718 (unread-alert replay proving). PR #1643 (audit runtime wiring) closed. Proving runs 1, 3, 4 passed. Remaining: PR 3 hook surfacing (UserPromptSubmit/PreToolUse guardrails), real remote loop proving run. |
| Step 4: Platform-9a idle-attention alerts and acknowledgement loop | BLOCKED | -- | -- | Blocked on Step 3 completion (hook surfacing and real remote loop proving). Controller-backed state now live (#1699). |
| Step 5: Platform-9b away-from-desk queue-moving proving run | BLOCKED | -- | -- | Blocked on Platform-9a plus controller-backed remote delivery. |
| Step 6: Platform-9c first hardening pass and Phase 4 handoff | BLOCKED | -- | -- | Fix real proving-run issues, update docs, and record known gaps. |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-4-01 | `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` | completed | Step 0 |
| SP-4-02 | `plans/agent_ops/4_remote_channel/sub/2026-03-23_remote-ops-preflight-hardening.md` | completed | Pre-Platform-8 |
| SP-4-03 | `plans/agent_ops/4_remote_channel/sub/2026-03-23_token-economy-observability-and-dashboard.md` | completed | Pre-Platform-8 |
| SP-4-04 | `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8a-telegram-transport.md` | completed | Step 1 |
| SP-4-05 | `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md` | completed | Pre-Platform-8 |
| SP-4-06 | `plans/agent_ops/4_remote_channel/sub/2026-03-24_platform-8b-audit-trail.md` | completed (library only) | Step 2 |
| SP-4-07 | `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md` | in_progress | Step 3 |

### Shared Surface Ownership

SP-4-02, SP-4-03, SP-4-04, and SP-4-05 all touch overlapping files. Ownership is
declared here to prevent merge conflicts and scope drift during parallel
implementation.

| File | Primary Owner | Secondary Owner(s) | Serialization Rule |
|------|---------------|---------------------|-------------------|
| `scripts/internal/ops.py` | SP-4-05 | SP-4-02, SP-4-03, SP-4-04 | SP-4-02 and SP-4-03 are already complete; SP-4-05 owns any new actionable lifecycle views or helper wiring; SP-4-04 may add channel status CLI only after SP-4-05 lands |
| `src/bid_euchre/ops/dashboard.py` | SP-4-03 | SP-4-02, SP-4-05, SP-4-04 | SP-4-02 and SP-4-03 are complete; SP-4-05 may add lifecycle projections but should avoid broad dashboard redesign; SP-4-04 channel status indicator remains optional |
| `src/bid_euchre/ops/monitor.py` | SP-4-05 | SP-4-02, SP-4-04 | SP-4-02 is complete; SP-4-05 owns typed lifecycle findings, persistent loop behavior, and routine-state reconciliation; SP-4-04 channel health check remains deferred to Platform-9c |
| `src/bid_euchre/ops/message_bus.py` | SP-4-05 | SP-4-02, SP-4-04 | SP-4-02 is complete; SP-4-05 owns sender dedupe and actionable operator read flow; SP-4-04 should not change bus semantics in Platform-8a |
| `.claude/hooks/post-merge-notify.sh` | SP-4-05 | — | SP-4-05 owns merge-completion helper extraction and hook parity fixes |
| `.claude/tmux/steward-session.sh` | SP-4-04 | — | SP-4-04 adds `--channels plugin:telegram@claude-plugins-official` flag and channel env vars; no other SP modifies the launcher |

## Blockers

- [x] ~~SP-3-05 dual-domain steward layout transition~~ — COMPLETE (2026-03-23).
  Dual-domain layout shipped in pre-proving hardening session (PRs #1281–#1294).
  Proving run passed 2026-03-23. Phase 4 scope lock is unblocked.
- [x] ~~SP-4-04 Steps 3-5~~ — COMPLETE (2026-03-24). All user-side Telegram
  preflight done. Pairing confirmed (user 8122530898), permission relay proven
  (messages flow both ways through orchestrator), kill switch verified
  (STEWARD_TELEGRAM_ENABLED env var override + auto-detect via `claude plugins list`).

## Session Log

| Date | Summary |
|------|---------|
| 2026-03-23 | Phase 4 plan and checkpoints created. Official Claude Code Channels discovery (v2.1.80+) reduces Platform-8a scope from "build transport skeleton" to "configure official Telegram plugin." Permission relay and sender gating are framework-provided. Audit trail deferred to hardening (Platform-14). |
| 2026-03-23 | SP-3-05 blocker cleared. Dual-domain layout shipped (PRs #1281–#1294), proving run passed. 4-window tiled layout canonical, 12 worker lanes active across platform/browser-game/flex pools. |
| 2026-03-23 | Step 0 (scope lock): SP-4-01 sub-plan created and registered. Key decisions: free-form messages allowed, no remote command grammar, orchestrator is single ingress, author lanes remain tmux-only. Platform-8b audit trail tracked in issue #1324. Phase status moved from PENDING to IN_PROGRESS. |
| 2026-03-23 | SP-4-02 registered and committed. Preflight hardening plan covers 6 steps: lifecycle proving, operational cleanup, stall recovery, scope enforcement, reset/clear validation, and auto-dispatch. Gated rollout order (Steps 1-2 first, then 3-4 parallel, then 5-6). |
| 2026-03-23 | SP-4-03 registered. Token economy observability alongside SP-4-02. Covers usage import, lane attribution, CLI/dashboard views, and baseline anti-pattern report. Overlaps SP-4-02 in `scripts/internal/ops.py` and dashboard — serialize shared surfaces during implementation. Codex review surfaced 3 plan-quality findings (boundary exception, malformed telemetry, attribution key) for orchestrator to address. |
| 2026-03-23 | SP-4-04 registered (flex-a). Platform-8a Telegram transport sub-plan: 6 steps covering preflight, plugin config, pairing proof, permission relay proof, kill switch proof, and registry integration. Steps 3-5 parallelizable after Step 2. Key constraint: orchestrator-only ingress, no audit trail (deferred to Platform-9c). |
| 2026-03-23 | SP-4-03 completed (author-a). Baseline token economy report produced at `plans/sessions/2026-03-23_token-economy-baseline.md`. Key findings: 52.4% shipped-token rate, 10.9K tokens/commit, 71% zero-commit session rate. Top 3 waste patterns: abandoned-work churn (42.9% of tokens), wrong-approach retry (60 friction events), high-error session tax (16.8% of tokens). Pre-steward data only (2026-02-03 to 2026-03-14); per-lane attribution requires post-steward follow-up. |
| 2026-03-23 | SP-4-04 Step 2 (author-a): Telegram config added to tmux launcher. `STEWARD_TELEGRAM_ENABLED` env var (default 0) controls kill switch. When enabled, appends `--channels telegram` to orchestrator pane only. `STEWARD_CHANNELS` exported for orchestrator. Author lanes remain tmux-only. |
| 2026-03-23 | Governance reconciliation (author-scratch): Fixed sub_plan_registry.md vs checkpoints.md disagreement — SP-4-03 updated to `completed` (baseline report done; live dashboard integration partial, follow-up needed), SP-4-04 updated to `in_progress` with owner `flex-a`. SP-4-04 Steps 3-5 marked BLOCKED on user-side Telegram preflight. |
| 2026-03-24 | SP-4-04 COMPLETE (flex-b). Telegram transport proven end-to-end. All 5 core steps done: preflight (claude >=2.1.80, plugin installed), plugin config (PRs #1436, #1451, #1452), pairing proof (user 8122530898), permission relay (messages flow both ways through orchestrator), kill switch (STEWARD_TELEGRAM_ENABLED env var override + auto-detect). Step 6 (registry integration) deferred — optional dashboard indicator, not blocking. Phase Step 1 (Platform-8a) marked COMPLETE. |
| 2026-03-24 | SP-4-02 COMPLETE (flex-a assessment). All 6 steps materially done: lifecycle proven (#1286, #1293, #1304, #1362), backlog cleaned (#1383), stall recovery (#1340, #1368, #1434), scope enforcement (#1375, #1395, #1400), reset/clear validated (#1350, #1369, #1373, #1386, #1389, #1411, #1425), auto-dispatch (#1374, #1387). Total: ~20 PRs (vs estimated 5-9). All exit criteria met. |
| 2026-03-24 | SP-4-05 registered. Reactive control-loop hardening reframes the observability gap as a local lifecycle-control problem, not just a bus-delivery bug. Scope covers durable packet->PR linkage, shared merge-completion helpers, typed lifecycle findings in `monitor.py`, persistent ops-loop behavior, and sender-side inbox-noise reduction. This is now the primary pre-Platform-8 control-plane slice; Telegram host/plugin preflight may continue in parallel, but remote proving should not claim local reactivity until SP-4-05 passes a proving run. |
| 2026-03-24 | `cmux` decision recorded: no active steward dependency. Current user-level `cmux` hooks are causing tmux-pane noise (`#1485`, `#1488`) without adding control-plane value. Phase 4 treats `cmux` as an optional later UX/presentation upgrade only. Immediate action is to bypass or disable `cmux` hooks for steward sessions, not to build deeper `cmux` integration. |
| 2026-03-24 | SP-4-05 Step 0 COMPLETE (flex-c, PR #1500). cmux hooks disabled for steward sessions via session guard in `~/.claude/hooks/cmux-notify.sh`. cmux `claude-hook` binary is unmodifiable (known limitation, documented). Closes #1485, keeps #1488 open for future revisit. |
| 2026-03-24 | SP-4-05 COMPLETE (brws-author-d assessment). All 7 steps verified: Step 0 cmux guard (PR #1500), Steps 1-2 completion unification (PRs #1491, #1474), Step 3 typed reconciler (PR #1490), Step 4 persistent loop (SP-3-08 #1287 + #1490), Step 5 inbox hygiene (PRs #1507, #1486), Step 6 lifecycle proven through fleet operation (10+ PRs processed across all pools with hook fast path, auto-merge fallback, and stall detection all exercised). All exit criteria met. Issue #1502 verified resolved on main (PR #1500 superseded stale-base clobber from #1496). Issue #1503 findings addressed by PR #1511. |
| 2026-03-24 | SP-4-05 Step 6 formal proving run PASSED (flex-b). Executed 3 isolated scenarios from the test plan (PR #1512): (1) Local merge hook fast path — PR #1515, packet 107ce27f717c auto-completed by hook, sentinel + bus message confirmed; (2) Monitor fallback — packet 08a24f95c8b0 auto-completed by `check_merged_dispatches()` on next monitor cycle; (3) Stall detection — 5-cycle test with mock probes, re-nudge at cycle 3 (WARN), escalation at cycle 4+ (HIGH). Cross-cycle state persistence verified. Results at `sp4-05-step6-proving-run-results.md`. |
| 2026-03-24 | SP-4-06 proposed (author-a). Platform-8b audit trail sub-plan created at `plans/agent_ops/4_remote_channel/sub/2026-03-24_platform-8b-audit-trail.md`. Seam analysis: inbound via `<channel>` tags, outbound via MCP tool calls (`reply`/`react`/`edit`). Interception at application layer (wrappers + helpers), not transport layer. 4-PR decomposition: core writer + unit tests, outbound wrappers, inbound helper, integration tests. File scope: `src/bid_euchre/ops/audit_trail.py` (new), `tests/unit/test_audit_trail.py` (new). Step 2 marked IN_PROGRESS. |
| 2026-03-24 | SP-4-06 COMPLETE (author-a). All 4 PRs shipped: PR 1 core writer (#1532), PR 2 outbound wrappers (#1536), PR 3 inbound helper + channel tag parser (#1541), PR 4 integration tests. Integration test suite covers: full round-trip conversations (4 tests), concurrent writers with flock safety (3 tests), large-volume 1000+ record throughput (4 tests), mixed direction filtering (9 tests). 20 integration tests total, all passing. Step 2 marked COMPLETE. |
| 2026-03-24 | Phase 4 reconciled after control-plane / transport review. Issue #1573 is accepted: SP-4-06 completed the Platform-8b audit library, but runtime callers and real controller-backed proving are still missing. Step 2 reopened as IN_PROGRESS. New SP-4-07 drafted to add a repo-owned controller projection, hook-fed local enforcement, Platform-8b runtime wiring, and a comparative decision matrix for custom bus vs native `SendMessage` vs Claude Channels (`#1289`). |
| 2026-03-24 | Telegram inbound fix: PR #1616 moved ops lane to detached worktree (`Bid-Euchre-steward-ops`), mirroring the review lane pattern. Root cause: ops lane and orchestrator both ran in `$MAIN_DIR`, spawning competing bun MCP server instances that raced on `getUpdates`. Ops bun consumed inbound messages before they reached the orchestrator. Fix confirmed — test message delivered successfully. Closes #1615, unblocks real inbound proving for Platform-8b runtime wiring. |
| 2026-03-24 | SP-4-07 IN_PROGRESS (author-a + author-b). Three PRs shipped or in-flight: PR #1618 stabilization gate (merged — TTL expiry, escalation dedup, stall guard), PR #1633 controller projection module (merged — SP-4-07 PR 2), PR #1643 audit runtime wiring (open — SP-4-07 PR 4, wires audit trail into runtime paths and controller). Step 3 moved from PENDING to IN_PROGRESS. |
| 2026-03-25 | SP-4-07 major progress reconciliation (flex-c). 10 additional PRs merged since last update: #1699 (controller wired into monitor cycle — controller now live), #1701 (permission stall detection), #1703 (urgent TTL exemption), #1704 (fleet idle auto-shutoff), #1707 (11 controller integration tests), #1708 (SKILL.md edit permission), #1712 (proving run 3: persistence/dedup/clear — 7 tests passed), #1714 (proving run 4: false-stall regression — 6 tests passed), #1715 (outbound audit wired into PostToolUse hook), #1718 (proving run 1: unread-alert replay — 10 tests passed). PR #1643 closed. 4 of 6 exit criteria now met. Remaining: PR 3 (hook surfacing/guardrails) and proving run 5 (real remote loop). |
