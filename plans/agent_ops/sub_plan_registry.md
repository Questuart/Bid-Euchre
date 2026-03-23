# Sub-Plan Registry — Agentic Orchestration Platform

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-23 by author-scratch (register SP-4-02)

---

## Registry

| ID | Title | Parent Section | Status | Owner | File | Created | Completed |
|----|-------|----------------|--------|-------|------|---------|-----------|
| SP-0-01 | Phase 0 bridge hardening for Platform-1 entry | Phase 0 dependencies; entry criteria; `Platform-1` done-when | superseded | Codex | `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform-entry-hardening.md` | 2026-03-20 | 2026-03-20 |
| SP-0-02 | Platform-1 prep PR handoff | Phase 0 dependencies and `Platform-1` handoff boundary | completed | Opus | `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform1-prep-pr-handoff.md` | 2026-03-20 | 2026-03-21 (PR #1218) |
| SP-1-01 | Platform-1 lane registry foundation | Phase 1 Platform-1 implementation | completed | author-b | `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform1-lane-registry-foundation.md` | 2026-03-21 | 2026-03-21 |
| SP-1-02 | Platform-2 orchestrator intake | Phase 1 Platform-2 implementation | completed | author-b | `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform2-orchestrator-intake.md` | 2026-03-21 | 2026-03-21 |
| SP-1-03 | Platform-3 communication bus v1 | Phase 1 Platform-3 implementation | completed | author-b | `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform3-communication-bus.md` | 2026-03-21 | 2026-03-21 (PR #1225) |
| SP-2-01 | Platform-4 dashboard-first layout | Phase 2 Platform-4 implementation | completed | author-b | `plans/agent_ops/2_visible_operating_model/sub/2026-03-21_platform4-dashboard-layout.md` | 2026-03-21 | 2026-03-21 |
| SP-2-02 | Platform-5 canonical prompts and skills | Phase 2 Platform-5 implementation | completed | author-a | `plans/agent_ops/2_visible_operating_model/sub/2026-03-21_platform5-canonical-prompts-and-skills.md` | 2026-03-21 | 2026-03-22 (PR #1234) |
| SP-2-03 | Agent frontmatter hardening | Phase 2 post-Batch-C follow-up (Amendment A3) | completed | author-b | `plans/agent_ops/2_visible_operating_model/sub/2026-03-22_agent-frontmatter-hardening.md` | 2026-03-22 | 2026-03-22 (PR #1239) |
| SP-3-02 | Platform-7 worker pool manager | Phase 3 Platform-7 implementation | completed | author-d | `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_platform7-worker-pool-manager.md` | 2026-03-22 | 2026-03-22 (PR #1250, #1252) |
| SP-3-03 | BD-004 v1 pane delivery adapter | Phase 3 BD-004 exit gate fix | completed | author-a | `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_bd004-v1-pane-delivery.md` | 2026-03-22 | 2026-03-22 (PR #1263) |
| SP-3-04 | Phase 3 closeout and transition entry | Phase 3 durable state reconciliation | completed | author-scratch | `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_phase3-closeout-and-transition-entry.md` | 2026-03-22 | 2026-03-22 |
| SP-3-05 | Dual-domain steward layout transition | Post-Phase-3 transition package before Platform-8 | completed | orchestrator | `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_dual-domain-steward-layout-transition.md` | 2026-03-22 | 2026-03-23 (PRs #1281–#1294, proving run passed) |
| SP-3-06 | Task dispatch CLI and execution-surface hardening | Post-Phase-3 transition: CLI dispatch, execution-surface rules | completed | orchestrator | _(no sub-plan file — single-PR scope)_ | 2026-03-23 | 2026-03-23 (PR #1275) |
| SP-3-07 | Bidirectional message bus across all steward lanes | Post-Phase-3 transition: message bus wiring for 16-lane layout | completed | orchestrator | _(no sub-plan file — single-PR scope)_ | 2026-03-23 | 2026-03-23 (PR #1276) |
| SP-3-08 | Monitoring cycle with session-start auto-launch | Post-Phase-3 transition: ops monitoring cycle and auto-launch | completed | orchestrator | _(no sub-plan file — single-PR scope)_ | 2026-03-23 | 2026-03-23 (PR #1277) |
| SP-4-01 | Platform-8 scope lock | Phase 4, Platform-8 scope lock and sub-plan registration | completed | author-scratch | `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` | 2026-03-23 | 2026-03-23 |
| SP-4-02 | Remote-ops preflight hardening | Phase 4, Pre-Platform-8 operational hardening | in_progress | orchestrator | `plans/agent_ops/4_remote_channel/sub/2026-03-23_remote-ops-preflight-hardening.md` | 2026-03-23 | — |

## Status Summary

| Status | Count |
|--------|-------|
| proposed | 0 |
| in_progress | 1 |
| blocked | 0 |
| completed | 14 |
| abandoned | 0 |
| superseded | 1 |

## Conventions

- **ID format:** `SP-<phase>-<seq>` where `<phase>` is the phase number and
  `<seq>` is a zero-padded sequence within that phase.
- **File location:** `plans/agent_ops/<phase>/sub/YYYY-MM-DD_<slug>.md`
- **Updates:** Update this registry whenever a sub-plan changes status.
