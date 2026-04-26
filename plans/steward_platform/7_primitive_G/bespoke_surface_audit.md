# Sidecar: Primitive G Bespoke-Surface Audit

**Date:** 2026-04-24
**Author:** steward-analyst (analyst-a)
**Task packet:** `40438a52afaa` (reshape of parked `d70a297dbe6a`)
**Type:** Sidecar tactical audit — complement to `plans/steward_platform/7_primitive_G/shaping.md` (PR #2784)
**Reshape context:** `plans/sessions/2026-04-24_g1_packet_scope_escalation.md` (Option A chosen)
**Status:** COMPLETE. Closes the 4 gaps identified in escalation §3.2 without duplicating PR #2784's strategic frame.

---

## §0. Relationship to PR #2784 shaping.md

PR #2784's `shaping.md` is the **packet-scoped execution plan** — 14 packets (G-A1…G-E3) across 6 tracks, each with scope/upstream gates/verification surface/rollback/effort. It is the authoritative dispatcher for Phase 0 work.

This sidecar is the **surface-scoped inventory audit** — the same bespoke-system perimeter viewed along a different axis (surface → substitution decision → confidence + rationale) with measured counts, the proving-run design, and the methodology-preservation split made explicit as a standalone section.

**Do not read this doc as an alternative to `shaping.md`.** Where the two
overlap, `shaping.md` is authoritative for packet scope and dispatch sequence.
Where this doc adds (§1 inventory table; §3 proving-run design; §4 methodology
preservation), `shaping.md` is silent and this doc is authoritative.

Cross-references from this doc to `shaping.md` are by section number; the
packet IDs (G-A1 … G-E3) and the §9 Pattern-10 surface table live in
`shaping.md` and are cited here rather than re-derived.

---

## §1. Bespoke-surface inventory table

Shrinking-stakes order: highest LOC × call-site × test-coverage weight first. "LOC" is `wc -l` on 2026-04-24 origin/main. "Call sites (code)" counts occurrences in `src/**` + `scripts/**` + `.claude/hooks/**` only (excludes plan/session markdown to avoid citation-noise inflation). "Tests" counts dedicated `tests/**` files whose name references the surface.

Confidence vocabulary:
- **H** — source-grounded decision (plugin_source_evaluation.md §2-§5 or rework_spec.md §3 disposition).
- **M** — rework_spec.md disposition + indirect source signal.
- **L** — disposition exists but substrate availability or surface overlap is under-verified on origin/main.

| Surface | LOC | Call sites (code) | Tests (files) | Native candidate | Confidence | Rationale |
|---|---|---|---|---|---|---|
| `scripts/internal/ops.py` (monolithic CLI dispatcher) | 5628 | — (entry-point) | 1 (`test_ops_cli.py`) + many via subcommands | Thin some subcommands (dashboard, task) over native task-system + per-tool MCP override | M | rework_spec §4 "Modify; thin some subcommands". B.8 ADR boundary (`task_queue.py` kept bespoke) limits thin-out to output-shape surfaces, not the packet contract. |
| `src/bid_euchre/ops/token_economy.py` | 3103 | 3 | 2 (`test_token_economy.py`, `test_ops_token_economy.py`) | `/usage` + `/cost` native overlap + `ops/adapters/token_economy_adapter.py` (ADR 003 seed) | H | rework_spec §3 row "Modify substrate; bespoke debt remains". 22 hard-blocks inventoried by Primitive F Packet 11 handoff. G-C1 target (shaping §5.1). |
| `src/bid_euchre/ops/monitor.py` | 2372 | 19 | 2 (`test_ops_monitor.py`, `test_ops_monitor_*`) | Native Monitor tool + TeammateIdle subscription | M | rework_spec §3 row "Trim hard". Monitor tool is Tier S per `claude_code_changelog_implications.md`. Multi-file simplification; aligns with Primitive A (observability) scope. |
| `src/bid_euchre/ops/worker_pool.py` | 2260 | 10 | 4 (`test_ops_worker_pool.py` + 3 related) | Partial — TeammateIdle for availability; worktree migration cascades; keep dispatch + round-robin bespoke | M | rework_spec §3 row "Trim moderate". B.8 (Agent Teams) explicitly **does not** substitute for worker_pool: teams are flat, no pool concept (plugin_source_evaluation §3.3). |
| `src/bid_euchre/ops/message_bus.py` | 1935 | 7 | 4 (`test_ops_message_bus.py` + integration files) | Keep bespoke core; HTTP hooks for external; `SendMessage` as supplemental intra-session channel | H | ADR B8: `SendMessage` is "strictly a subset" of bus (session-ephemeral; no durability; no cross-restart). rework_spec §3 row "Modify; keep core". |
| `scripts/internal/review_driver.py` | 1817 | — (entry-point) | 2 (`test_review_driver.py` + `test_review_lane_runner.py`) | Keep + cherry-pick validator-subagent pass (ADR 005); do NOT replace | H | plugin_source_eval §2.6: wholesale adoption requires retrofitting 9 distinct pieces (verdict/merge-guard/scope-lock/auto-fix/status/etc.) — more work than status quo. |
| `src/bid_euchre/ops/status.py` | 1828 | 6 | 2 (`test_ops_status.py` + heartbeat variant) | Modify substrate — session metadata + session title hooks | M | rework_spec §3 row "Modify substrate". No full substitution candidate. |
| `src/bid_euchre/ops/index.py` | 1414 | — | 1 | Consolidate candidate with `memory.py` (shared project memory) | M | rework_spec §3 row "Consolidate candidate". ADR 010 rejected mcp-memory-service wholesale — no vector-DB alternative. |
| `src/bid_euchre/ops/learning.py` | 1316 | 4 | 1 | Modify; integrate with B.12 improvement-mechanism evaluation | L | rework_spec §3 row "Modify; integrate". No native substitute; B.12 is the meta-mechanism. |
| `src/bid_euchre/ops/attention.py` | 1284 | 3 | 1 (`test_ops_attention.py`) | Trim — conditional hooks + PermissionDenied/StopFailure subscriptions | M | rework_spec §3 row "Trim moderate". |
| `src/bid_euchre/ops/worktrees.py` | 1133 | 9 | 1 (`test_ops_worktrees.py`) | Native WorktreeCreate/Remove + declarative `worktrees.yaml` — ~80% LOC reduction | H (disposition) / L (availability) | rework_spec §3 row "Trim hard ~80%". G-B1 target (shaping §4.1). **Substrate-gated**: defers to Phase 1 if WorktreeCreate/Remove is unstable on fleet version. |
| `src/bid_euchre/ops/supervisor.py` | 1007 | — | — | Evaluate Agent Teams team-lead overlap (ADR B8) | L | rework_spec §3 row "Keep; evaluate". ADR B8 already ruled "keep bespoke" at packet level; supervisor.py overlap narrower. |
| `src/bid_euchre/ops/dashboard.py` (heartbeat classifier only) | ~200 of 982 | 1 (heartbeat block) | 1 (`test_ops_dashboard.py`) | TeammateIdle subscription (retire classifier block only; keep dashboard core) | H | rework_spec §3 "Retire". Partial-file surgery per G-B2 (shaping §4.2). |
| `src/bid_euchre/ops/control_plane.py` | 978 | 1 | 1 (`test_ops_control_plane.py`) | Modify; expand event sources (ConfigChange hook) | L | rework_spec §3 row "Modify; expand event sources". |
| `src/bid_euchre/ops/task_queue.py` | 969 | 18 (src/scripts) | 2 (`test_ops_task_queue.py` + others) | KEEP BESPOKE — do not migrate to Agent Teams native tasks (ADR B8) | H | plugin_source_eval §3.3: native tasks lack `scope_declared`, domain routing, lane affinity, routing metadata; teammates die with lead session. 6 extensions required to substitute. |
| `src/bid_euchre/ops/reviews.py` | 945 | — | 1 (`test_ops_reviews.py`) | Modify; evaluate `/autofix-pr` + code-review plugin overlap (ADR 005) | L | rework_spec §3 row "Modify; evaluate". |
| `src/bid_euchre/ops/snapshots.py` | 710 | — | 1 | Consolidate candidate with `audit_trail.py` | L | rework_spec §3 row "Consolidate candidate". |
| `src/bid_euchre/ops/review_queue.py` | 693 | 2 (+test files) | 1 (`test_review_queue.py`) | Keep; evaluate code-review plugin integration (ADR 005) | M | ADR 005 "retain review_driver.py as sole orchestrator". Queue is steward-specific (SHA-bound verdict + merge-guard). |
| `src/bid_euchre/ops/audit_trail.py` | 690 | — | 1 | Modify; keep (first-class `${CLAUDE_SESSION_ID}` + `last_assistant_message`) | M | rework_spec §3 row "Modify; keep". Substrate-enhancement, not substitution. |
| `src/bid_euchre/ops/watchdogs.py` | 682 | 2 | 1 (`test_ops_watchdogs.py`) | Keep (steward-specific watchdog timers) | H | rework_spec §3 row "Keep". No native analog. |
| `.claude/tmux/steward-session.sh` | 656 | — (entry-point) | 1 (`test_steward_session.py`) | Setup hook + declarative `.claude/config/lanes.yaml` (G-A3) | H (disposition) / L (availability) | G-A3 substrate-gated (shaping §3.3). Defers to Phase 1 if Setup hook unstable. |
| `src/bid_euchre/ops/skill_promotion.py` | 633 | — | 1 (`test_ops_skill_promotion.py`) | Modify; extend distribution (plugin executables on PATH) | L | rework_spec §3 row "Modify; extend distribution". |
| `src/bid_euchre/ops/recovery.py` | 605 | — | — | Keep (steward-specific recovery protocols) | H | rework_spec §3 row "Keep". No native analog. |
| `src/bid_euchre/ops/idle_detector.py` | 519 | 1 | — | **RETIRE** in favor of TeammateIdle | H | rework_spec §3 row "Trim/retire". G-B2 target (shaping §4.2 scope). |
| `src/bid_euchre/ops/memory.py` | 517 | — | 1 | Modify substrate (shared project memory + auto memory supplementary) | M | rework_spec §3 row "Modify substrate". ADR 010 rejected wholesale mcp-memory-service. |
| `src/bid_euchre/ops/scheduler.py` | 497 | — | 1 (`test_ops_scheduler.py`) | Trim moderate (Monitor + conditional hooks) | L | rework_spec §3 row "Trim moderate". |
| `src/bid_euchre/ops/orchestrator_brief.py` | 485 | 1 | 1 (`test_ops_orchestrator_brief.py`) | Keep (steward-specific brief assembly) | H | Per orchestrator-v1.1 prompt policy (deterministic bridge). |
| `src/bid_euchre/ops/context_safety.py` | 448 | — | — | Keep (steward-specific context guardrails) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/ci.py` | 428 | — | — | Keep (CI integration is steward-specific) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/compaction.py` | 418 | — | — | Modify; evaluate native PreCompact | M | rework_spec §3 row. PreCompact hook is Tier S (April 2026 update). |
| `src/bid_euchre/ops/fs_boundary.py` | 393 | — | — | Keep (steward-specific filesystem protection) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/scope.py` | 391 | 1 | — | Keep (scope-lock semantics; steward-specific) | H | Per B8 ADR — native Task has no scope field. |
| `src/bid_euchre/ops/session_postmortem.py` | 383 | — | 1 | Keep (bespoke postmortem analysis) | H | No native substitute. |
| `src/bid_euchre/ops/repairs.py` | 379 | — | — | Keep (bespoke repair catalog) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/lane_heartbeat.py` | 374 | 4 (src/scripts) | 2 (`test_lane_heartbeat.py`, `test_lane_heartbeat_hook.py`) | **RETIRE** in favor of TeammateIdle | H | rework_spec §3 row "Retire". G-B2 target. Overlap with `dashboard.py` classifier. |
| `src/bid_euchre/ops/retries.py` | 335 | — | — | Keep (steward-specific retry semantics) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/telegram_push.py` | 330 | — | 1 (`test_telegram_*`) | Modify; evaluate absorption via native remote sessions (Track 2.4) | L | rework_spec §3 row — keep through Phase 0. |
| `src/bid_euchre/ops/alert_push.py` | 328 | — | — | Keep (steward-specific alerting; no native analog) | H | rework_spec §3 row "Keep". |
| `src/bid_euchre/ops/away_mode.py` | 313 | — | 1 (`test_away_mode_integration.py`) | Evaluate absorption into native remote sessions (Phase 0 defer) | L | rework_spec §3 row — keep through Phase 0. |
| `src/bid_euchre/ops/events.py` | 294 | — | — | **REWRITE** per `melodic-software/claude-code-observability` dispatcher pattern; §9.7 IDs native | H | ADR 007 + plugin_source_eval §4.6. Primitive A scope, not Primitive G. Listed here for completeness — G does NOT own this migration. |
| `src/bid_euchre/ops/queue_priority.py` | 263 | — | — | Keep; evaluate native task priority via B8 | L | rework_spec §3 row. |
| `src/bid_euchre/ops/remote_ack.py` | 256 | — | — | Modify; evaluate absorption via remote sessions (Phase 1 cutover) | L | rework_spec §3 row — keep through Phase 0. |
| `src/bid_euchre/ops/effort_policy.py` | 153 | 2 | 1 (`test_effort_policy.py`) | Keep bespoke (B.10 policy consumer) | H | `.claude/rules/effort_policy.md` is the canonical source; this file is its loader. |
| `src/bid_euchre/ops/telegram_filter.py` | 149 | — | — | Evaluate for absorption via native channels | L | rework_spec §3 row "Evaluate". |
| `src/bid_euchre/ops/__init__.py` | 102 | — | — | Keep | H | Package index; no migration. |
| `.claude/hooks/**` (37 `.sh` + `.py` hooks) | 3304 (total) | — | 8 (`test_*_hook.py`) | Mixed: (a) Retire lane-heartbeat-post-tool per G-B2; (b) Replace event-synthesis hooks with native lifecycle subscriptions; (c) Hooks POSTing to local services → HTTP hooks; (d) Keep review-pipeline hooks (post-pr-review.sh + pre-merge-review-guard.sh) | M | rework_spec §5. ADR 004 files at Phase 0 close with per-hook disposition (native-lifecycle / conditional / HTTP / bespoke). |
| `.claude/skills/**` (44 SKILL dirs) | — (skill text, not LOC-measurable cleanly) | — | 1 (`test_read_ops_brief_skill.py` — single skill) | Monitoring 6→2 consolidation (G-F2); Playtest 4→2; Loop/schedule/away 3→1 evaluated; retain most others | M | rework_spec §6. Net −8 retirements + ~6 new draft 6/7 additions (net flat count; operational-clarity win). |
| `.claude/rules/prompt_policy/**` (analyst/author/orchestrator/common, 4 files) | 297 | — | — | Keep bespoke (B.3 registry; no native equivalent) | H | B.3 Version/Trigger/Expected-effect/Rollback schema is steward-authored. No native substitute. |
| `.claude/rules/effort_policy.md` | 137 | 2 (code via loader) | 1 (`test_effort_policy.py`) | Keep bespoke (B.10 policy) | H | archetype × task_type matrix is steward-specific; no native analog. |
| `.claude/rules/tool_risk_registry.md` | 225 | — (lint only) | — | Keep bespoke (B.6 dual-envelope registry) | H | Dual-envelope classification is steward-specific (ADR 006). Lint enforcement via `agent_readability_lint.py`. |
| `.claude/lane_models.json` | 25 | 2 (shell loader + `scripts/internal/lane_models.py`) | 2 (`TestLaneModelsJson`, `TestLaneModelsLoader` in `test_steward_session.py`) | Keep bespoke (permission-model tier map); layer Setup hook formalization via G-A3 | H | ADR 006 + `.claude/rules/80_permission_model.md`. No native equivalent for per-lane model-tier pinning. |

**Totals (for Primitive G audit boundary):**
- `src/bid_euchre/ops/**`: 42 modules, **33 294 LOC**.
- `scripts/internal/**` surfaces cited: 2 files (`ops.py` + `review_driver.py`), **7 445 LOC**.
- `.claude/hooks/**`: 37 shell + Python files, **3 304 LOC**.
- `.claude/skills/**`: 44 SKILL directories (SKILL.md is prose; consolidation measured in directories retired, not LOC).
- `.claude/rules/` policy/registry files: 6 files, **684 LOC**.
- `.claude/tmux/steward-session.sh` + `.claude/lane_models.json`: 681 LOC combined.

**Surfaces explicitly excluded from this audit** (outside G's scope per
`shaping.md` §1 scope-in/scope-out):
- `src/bid_euchre/core/`, `src/bid_euchre/strategy/`, `src/bid_euchre/sim/` — Bid-Euchre domain code.
- `tests/**` — test suite; test coverage recorded per-row but migration is author-lane concern.
- `docs/**` — documentation; Primitive G adjacency only.
- `plans/agent_ops/**` — legacy plan tree; G-E1/E2/E3 retire-notes handle these (shaping.md §8).
- `src/bid_euchre/ops/adapters/**` — Platform-10 adapter boundary; kept + extended per rework_spec §3 row.

---

## §2. Per-surface substitution candidates

**Read order:** substitutions are organized by (a) substrate-gated (WorktreeCreate / TeammateIdle / Setup hook; defer to Phase 1 if substrate unstable), (b) substrate-available-now (`--system-prompt-file` / `/usage` / `/cost` / SendMessage / lifecycle hooks), (c) keep-bespoke (scope-lock, packet contract, durable bus, prompt-policy registry, tool-risk registry).

Each row below names the bespoke surface, the proposed native substitute, the source-grounded confidence signal, and the packet that executes the migration (citing `shaping.md` §N). **This doc does not re-derive the packet sequence**; it distills the substitution rationale per surface.

### §2.1 Substrate-gated substitutions (Phase 0 defer-path documented)

| Surface | Native candidate | Confidence signal (source-grounded) | Execution packet | Substrate-gate |
|---|---|---|---|---|
| `ops/worktrees.py` ~80% trim | Native WorktreeCreate/Remove + declarative `worktrees.yaml` (replaces `PROTECTED_WORKTREES` literal + most creation/removal functions); keep adapter-boundary shim for steward error translation | `claude_code_changelog_implications.md` §2 Tier S lists WorktreeCreate/Remove as substrate-gated native feature; rework_spec §3 row 1 "Trim hard ~80%"; largest LOC reduction in G catalog | G-B1 (shaping §4.1) | WorktreeCreate/Remove stable on fleet version |
| `ops/lane_heartbeat.py` RETIRE + `ops/idle_detector.py` RETIRE + `dashboard.py` heartbeat classifier block RETIRE + `.claude/hooks/lane-heartbeat-post-tool.sh` RETIRE | Native TeammateIdle subscription emitting `lane_idle` / `lane_resumed` events via Primitive A dispatcher | `claude_code_changelog_implications.md` §2 Tier S lists TeammateIdle; plugin_source_eval §3.2 + §4.2 document TeammateIdle hook inputs (`teammate_name`, `team_name`); rework_spec §3 rows "Retire" | G-B2 (shaping §4.2) | TeammateIdle native substrate stable on fleet version |
| `.claude/tmux/steward-session.sh` imperative → declarative | Setup hook + `.claude/config/lanes.yaml` declarative config; shell preserved only for worktree-creation/attach glue | rework_spec §2 row 12 + §5 hooks table; `claude_code_changelog_implications.md` Setup hook is Tier S | G-A3 (shaping §3.3) | Setup hook substrate stable on fleet version |

**Defer-path discipline.** If a substrate gate is closed at dispatch time, the corresponding packet **defers to Phase 1** rather than forcing a partial migration. `shaping.md` §11 "Surprise finding" and §13.2 risks 1–3 document this coupling. Deferral is recorded in MEMORY.md + the packet disposition; G Phase 0 Readiness tolerates partial-satisfaction on substrate-gated packets per `governing_plan.md` §5-G.

### §2.2 Substrate-available-now substitutions (no Phase 0 gate)

| Surface | Native candidate | Confidence signal (source-grounded) | Execution packet |
|---|---|---|---|
| `.claude/tmux/steward-session.sh` per-lane launch args | `--system-prompt-file .claude/system_prompts/<archetype>.md` on every `$CLAUDE_BIN` invocation + `scripts/internal/review_lane_runner.py::invoke_review` argv | PR #2779 (B.9a pilot) empirically verified via 4-probe protocol; `--system-prompt-file` available on all fleet versions ≥ 4.0 | G-A2 (shaping §3.2) |
| `ops/token_economy.py` 22 hard-blocks | Native `/usage` + `/cost` overlap where coverage exists; adapter-boundary reads for residual Bid-Euchre-literal surfaces via `ops/core/` adapter (Platform-10 pattern) | Primitive F Packet 11 handoff; ADR 003 seed documents which surfaces F-forward kept native vs. which stayed bespoke | G-C1 (shaping §5.1) |
| `ops/events.py` full rewrite | Dispatcher pattern from `melodic-software/claude-code-observability` plugin with §9.7 first-class IDs native (project_id, cell_id, lane_id, trace_id, incident_fingerprint, prompt_policy_version) — NOT a fork, reimplementation in steward's codebase | plugin_source_eval §4.6 + ADR 007; source-grounded 80% event-class coverage, 40% first-class-ID coverage → adopt pattern, author §9.7 IDs native | Primitive A (NOT Primitive G) |
| `ops/message_bus.py` external-push shim | HTTP hooks replacing shell-glue POSTs to local services (ADR 004 category) | rework_spec §5 hooks row "Hooks POSTing to local services → Replace with HTTP hooks" | Part of ADR 004 hook catalog; author-lane packet TBD |
| `.claude/hooks/**` event-synthesis hooks | Native lifecycle hooks (`SessionStart`, `SessionEnd`, `PreCompact`, `PostToolUse`, `SubagentStart`/`Stop`, `TaskCreated`/`TaskCompleted`, `PermissionRequest`) | plugin_source_eval §4.2 + `claude_code_changelog_implications.md` §2 Tier S | ADR 004 (hook catalog) |
| Orchestrator↔lane intra-session ping | `SendMessage` as **supplemental** channel; steward message bus remains authoritative for durable / cross-restart semantics | plugin_source_eval §3.3 + §3.6 + ADR B8 | Phase-1+ per ADR B8; NOT Primitive G scope |

### §2.3 Keep-bespoke surfaces (substitution rejected with source-grounded rationale)

These are **load-bearing bespoke surfaces** whose methodology is orthogonal to Claude Code substrate evolution. They persist as explicit keep-decisions; migration attempts are rejected with a cited source-grounded rationale.

| Surface | Proposed substitute | Why rejected (source-grounded) | Reference |
|---|---|---|---|
| `ops/task_queue.py` packet contract | Agent Teams native task system | Native tasks lack `scope_declared`, domain routing, lane affinity, `task_type`/`complexity_estimate`/`model_hint`/`effort_hint` metadata; teammates die with lead session; no session-resumption. 6 extensions required → cheaper to keep bespoke | plugin_source_eval §3.3 + §3.5; ADR B8 |
| `ops/message_bus.py` durable-across-restart core | `SendMessage` / `broadcast` | `SendMessage` is "strictly a subset" of steward bus — session-ephemeral, no expiration, no read/expired reconciliation, no message-type taxonomy (ack / task_received / completion / blocker / progress), no priority, no cross-session replay | plugin_source_eval §3.3; ADR B8 |
| `scripts/internal/review_driver.py` review orchestrator | Official `anthropics/claude-code/plugins/code-review` | Wholesale adoption requires retrofitting 9 capabilities: Codex-CLI reviewer + SHA-bound verdict + status-context publication + merge-guard integration + precheck pattern detection + auto-fix commit loop + scope-drift detection + follow-up issue creation + label taxonomy — more work than status quo | plugin_source_eval §2.5 + §2.6; ADR 005 |
| `ops/memory.py` + `knowledge/**` curated markdown | `mcp-memory-service` (vector DB + autonomous consolidation) | Autonomous "dream-inspired" consolidation silently mutates memory outside git; heavy dependency (ChromaDB / SQLite-vec / Cloudflare); all §9.7 first-class IDs absent; storage outside git conflicts with rules/deferred/30_data_contract.md commit policy | plugin_source_eval §5.6 + §5.9; ADR 010 |
| `.claude/rules/prompt_policy/**` (B.3 registry) | No native substitute | Version / Trigger / Expected-effect / Rollback schema is steward-authored; no native prompt-policy registry exists in Claude Code substrate | B.3 §4.2 governing plan |
| `.claude/rules/effort_policy.md` (B.10 table) | No native substitute | archetype × task_type × effort_tier matrix is steward dispatch-time input; no native equivalent | effort_policy.md header; B.10 |
| `.claude/rules/tool_risk_registry.md` (B.6 table) | No native substitute | Dual-envelope (auto-mode vs. bypass) classification is ADR 006–derived steward discipline; no native registry | ADR 006; B.6 |
| `ops/scope.py` scope-lock enforcement | Native task `scope_declared` | Native tasks have no scope field (plugin_source_eval §3.3) | ADR B8 |
| `ops/worker_pool.py` round-robin + lane-affinity dispatch | Agent Teams flat team structure | Teams are flat (one team per session; no nested teams; no pool concept) | plugin_source_eval §3.3 |

---

## §3. Proving-run design

**Gap closure.** PR #2784 `shaping.md` §10 covers **rollback validation** (forward → revert → observe pre-merge behavior restored; paste both outputs). It does **not** cover **parallel-run mechanism-evaluation** — measuring the per-surface token-cost delta and behavioral equivalence between bespoke and native substrates in a shared observation window. This section defines that methodology.

### §3.1 Pattern: parallel-run with measured token-cost delta

For each substrate-available-now or substrate-gated substitution (§2.1 + §2.2), **the native migration ships behind a feature flag** during a proving-run window. The flag (`STEWARD_NATIVE_<SURFACE>=1`) gates which path the lane exercises. The observation window runs both paths on representative input:

1. **Cohort A (bespoke, control):** proving-run subset of the fleet with flag off. Records per-task token usage + behavioral outputs.
2. **Cohort B (native, candidate):** disjoint proving-run subset with flag on. Records the same metrics.
3. **Paired sampling where possible:** for surfaces whose input set is enumerable (e.g., `ops/worktrees.py` enumeration calls), run both paths on the **same** input set (A first, then B) and record paired deltas.
4. **Window length:** 1 calendar week minimum, 2 weeks target. Short enough to keep proving-run cost bounded; long enough to capture day-of-week variation in lane workload.

### §3.2 Measurement: token-cost delta + behavioral-equivalence delta

Two deltas are measured per surface per window:

**Token-cost delta** (primary):
- Source: `src/bid_euchre/ops/token_economy.py` rollups (PR #2725 lane × model × effort shape).
- Per-task metric: input tokens + output tokens + cache-read / cache-write tokens, aggregated per (lane, task_id).
- Window statistic: mean delta, bootstrap 95% CI, paired t-test where cohort is paired.
- **Pass:** Cohort B mean < Cohort A mean (lower tokens under native) at p < 0.05 OR the bootstrap 95% CI excludes 0 on the negative side.
- **Warn:** CI spans 0 but |mean delta| < 5% (noise-level equivalence; either choice defensible).
- **Fail:** Cohort B mean > Cohort A mean at p < 0.05 (native costs more) — **stop-loss trigger, see §3.3**.

**Behavioral-equivalence delta** (secondary; gate-critical):
- Source: surface-specific output capture (e.g., `ops/worktrees.py` enumeration output; `lane_heartbeat.py` idle-list output; `ops/events.py` event record shape).
- Per-call comparison: diff Cohort A output against Cohort B output on the same input. Some surfaces will have natural timing differences (timestamps); normalize before compare.
- Window statistic: equivalence rate = fraction of calls whose normalized output matches exactly + fraction that match up to documented-diff tolerances.
- **Pass:** Equivalence rate ≥ 99% OR divergences are all documented-expected (e.g., native TeammateIdle has finer-grained timing than bespoke heartbeat, but idle-state transitions match).
- **Warn:** Equivalence rate 95%-99% with divergence-class reviewed and accepted by operator.
- **Fail:** Equivalence rate < 95% — **stop-loss trigger, see §3.3**.

### §3.3 Stop-loss trip wires (per-surface)

For each substrate migration, the proving-run trips the stop-loss if any of the following fire inside the observation window:

| Stop-loss # | Trip condition | Action |
|---|---|---|
| 1 | Token-cost delta: Cohort B > Cohort A at p < 0.05 (native costs more) | Revert flag on; Cohort B lanes return to bespoke path; file follow-up issue documenting the per-surface finding; the migration is **not promoted** until the cost regression is explained |
| 2 | Behavioral-equivalence delta < 95% | Immediate flag-off; diff the first 10 divergences; classify (native bug / steward assumption violation / input-set mismatch); file issue if any class is novel; pause the migration |
| 3 | Availability regression: native substrate throws ≥ N errors (N = 5 in a 24-hr window; configurable per surface) | Immediate flag-off; **substrate-gate closes**; the packet defers to Phase 1 per `shaping.md` §11 surprise-finding discipline; MEMORY.md note |
| 4 | Proving-run window exhausted without passing on either delta | Operator reviews the findings; decides whether to extend the window, accept Warn-tier equivalence, or reject the migration |

**Stop-loss is per-surface, not fleet-wide.** A WorktreeCreate availability failure does not trip the TeammateIdle migration; failures are scoped by the feature flag.

### §3.4 Per-surface proving-run slots

Not every surface warrants its own full 1-week observation window. The recommended cohort assignment:

| Surface | Proving discipline | Minimum window | Reason |
|---|---|---|---|
| `ops/worktrees.py` native migration (G-B1) | Full parallel-run; paired sampling on enumeration calls | 2 weeks | Largest LOC surgery; highest-impact availability concern |
| Heartbeat retirement → TeammateIdle (G-B2) | Full parallel-run; unpaired cohort | 2 weeks | Idle-state is the fleet's liveness signal; equivalence is safety-critical |
| `--system-prompt-file` rollout (G-A2) | Already empirically validated via PR #2779 B.9a pilot Probes 1-4; **no additional proving-run required** | n/a | Pilot is the proving-run surrogate |
| Setup hook adoption (G-A3) | Full parallel-run on argv-comparison golden file | 1 week | Declarative substitution; golden-file comparison + ≥1 boot-smoke per cohort |
| Token-economy native `/usage`+`/cost` (G-C1) | Golden-file rollup preservation + `audit_portability.py` hard-block count | 1 week | F Packet 11 consumer contract is the equivalence gate |
| `ops/events.py` dispatcher migration (Primitive A) | Full parallel-run; NOT G's responsibility — listed for cross-reference | 2 weeks | A owns this; cited for §9.7 ID correctness |
| Skills consolidation (G-F2) | Per-retired-skill acceptance-command re-run from consolidated target | 1 week operator observation | No fleet-wide flag; skill-by-skill; operator-gated |
| HTTP hook migration (ADR 004 subset) | Parallel-run with dry-hook-path logging | 1 week per hook batch | Low-risk; replaceable one hook at a time |

Windows run sequentially (not concurrent) for substrate-gated surfaces to isolate attribution of regressions.

### §3.5 Proving-run data artifacts

Per surface, the proving-run produces 4 committed artifacts in the PR body:

1. **Cohort-A baseline rollup** — JSON or CSV pasted in PR body; 1-week token-cost aggregate by (lane, task_id).
2. **Cohort-B candidate rollup** — same shape.
3. **Delta statistic** — mean + 95% CI + p-value + equivalence rate, with the paired / unpaired test used.
4. **Divergence log** (if behavioral-equivalence delta < 100%) — the raw diff records classified into (expected / unexpected) buckets.

These travel with the packet's PR body so the review verdict is reproducible.

### §3.6 Why this is not rollback-smoke

PR #2784 `shaping.md` §10 already requires rollback-smoke per packet (forward → revert → observe pre-merge behavior restored). That's a **binary** gate on reversibility. The proving-run design here is **quantitative** — it measures whether the migration is **net-positive** (lower token cost + equivalent behavior) before promotion, not merely whether it is reversible after promotion. The two are complementary:

- **Rollback-smoke** (§10 shaping): does `git revert` restore the pre-migration state? — required for all reversible packets, binary outcome.
- **Proving-run** (this §3): does the native path cost less than the bespoke path at equivalent behavior? — required for native-substitution packets, quantitative outcome.

A packet that passes rollback-smoke but fails the proving-run is still revertable — but should be reverted rather than promoted. A packet that passes both is a net-positive adoption.

### §3.7 Pattern-8 observability hook

Per governing-plan §10.9 Pattern 8 (Observable-by-default): every proving-run writes a `proving_run_cohort_sample` event to the A dispatcher with fields `(surface, cohort, lane_id, task_id, token_cost, behavioral_divergence_bool, window_id)`. The aggregation into §3.2 delta statistics is deterministic from the event stream; no out-of-band measurement is authoritative. This also makes §3.3 stop-loss trip-wires testable via canary scenarios (Primitive H) — the canary can assert the trip-wire fires when synthetic events cross the threshold.

---

## §4. Methodology preservation (PORTABLE vs SUBSTRATE-REPLACEABLE)

**Gap closure.** PR #2784 `shaping.md` §11 "Phase 2 Decision Inputs — Portability readiness" touches the methodology-preservation split in a paragraph. This section lifts it to a first-class standalone artifact section so the operator-legible distinction (what survives a substrate change vs. what is substrate-specific) is not buried inside a Phase-2 decision subsection.

### §4.1 The split

| Axis | Definition | Example (steward) | Why this matters |
|---|---|---|---|
| **PORTABLE** | Methodology that travels with steward **independent of Claude Code substrate**. Re-implementable in any multi-agent platform (OpenAI Assistants API, future SDKs, self-hosted orchestrators). Describes *intent* and *invariants*, not *mechanics*. | Scope-lock discipline; packet-contract fields; §9.7 first-class IDs; Pattern 10 verification-surface; Pattern 7 rollback-path; B.3 prompt-policy registry schema; B.6 tool-risk dual-envelope table; B.10 effort-policy matrix; archetype system-prompt shape (B.9a); Pattern 9 load-bearing-ownership lint | A second-cell deployment (or a fleet on a different substrate) inherits these as **authoring conventions**, not software; they don't depend on WorktreeCreate existing or Claude Code's settings.json shape |
| **SUBSTRATE-REPLACEABLE** | Mechanics that currently run as steward-authored bespoke code but **have a native Claude Code substitute** (or soon will); migration is a substrate-choice, not a methodology choice. | Worktree creation/removal mechanics (native WorktreeCreate); idle detection (TeammateIdle); lifecycle event emission (native hooks); within-session messaging (SendMessage); launch-argv composition (Setup hook); permission-model gating (auto-mode classifier); token-cost accounting for native Claude Code calls (`/usage` + `/cost`) | Migration is a cost-vs-benefit decision (proving-run §3 measures it) without loss of methodology. Native mechanics are portable **by construction** because they travel with Claude Code. Bespoke mechanics are portable via **authoring conventions** (§4.2 below). |

### §4.2 Portable-by-convention catalog

These steward artifacts are **PORTABLE**. A second-cell or future-substrate adoption reproduces them via explicit authoring, not substrate absorption:

| Methodology artifact | Location | Why portable |
|---|---|---|
| Scope-lock (`scope_declared` on every packet) | `src/bid_euchre/ops/task_queue.py` + `src/bid_euchre/ops/scope.py` | Authoring convention: every packet names its file perimeter. Any task system can express this as a list field. |
| Packet contract (task_type, complexity_estimate, model_hint, effort_hint, metadata) | `src/bid_euchre/ops/task_queue.py` `VALID_EFFORT_HINTS` | Pure data-schema; not tied to Claude Code specifics. |
| §9.7 first-class IDs | `src/bid_euchre/ops/events.py` + event schema | Identifier taxonomy (project_id / cell_id / session_id / task_id / lane_id / trace_id / incident_fingerprint / prompt_policy_version / schema_version) is agnostic to emitter. |
| Pattern 10 verification-surface discipline | `plans/steward_platform/verification_contract/shaping.md` + per-plan Verification Plan sections | Shaping-doc authoring convention. Reproducible in any plan corpus. |
| Pattern 7 rollback-path discipline | Per-packet "Rollback path" subsection | Shaping-doc authoring convention. |
| Pattern 9 load-bearing-ownership lint | `scripts/internal/agent_readability_lint.py` `ownership` rule | Lint implementation is ~100 lines; reimplementable in any codebase. |
| B.3 prompt-policy registry schema (Version / Trigger / Expected effect / Rollback) | `.claude/rules/prompt_policy/<archetype>.md` files | Authoring convention; any system-prompt storage supports this header shape. |
| B.6 tool-risk dual-envelope registry | `.claude/rules/tool_risk_registry.md` | Classification table; agnostic to which runtime enforces it. |
| B.10 effort-policy archetype × task_type matrix | `.claude/rules/effort_policy.md` + `src/bid_euchre/ops/effort_policy.py` | Dispatch-time policy; pure data. |
| B.9a archetype system-prompt authoring shape | `plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` §3/§4.1 | Prompt-authoring convention (Role / Rules / Surfacing / Constraints / Named Skills / Tool Posture) is substrate-agnostic. |
| B.12 improvement-mechanism evaluation (net-positive/net-negative metric delta discipline) | `plans/steward_platform/2_primitive_B/shaping.md` §9 | Methodology; lint-checkable per version-bump. |
| Verification-surface canary scenarios (H.0 dogfood) | `plans/steward_platform/canary_scenarios/dogfood.md` | Self-exercising-discipline spec; replicable in any CI. |

**Portability promise.** A cell that adopts steward's governing plan inherits these without depending on any specific Claude Code feature. If Claude Code ships a breaking substrate change (or is replaced entirely), the PORTABLE layer survives and can be rewired to the new substrate via SUBSTRATE-REPLACEABLE adapters.

### §4.3 Substrate-replaceable catalog

These mechanics are currently bespoke but migrate to native without methodology loss. Each row lists the substitution and the packet that performs the migration:

| Mechanics | Current bespoke surface | Native substitute | Migration packet |
|---|---|---|---|
| Worktree creation/removal | `ops/worktrees.py` (1133 LOC) | WorktreeCreate / WorktreeRemove hooks | G-B1 |
| Idle detection | `ops/lane_heartbeat.py` (374 LOC) + `ops/idle_detector.py` (519 LOC) + dashboard classifier block | TeammateIdle subscription | G-B2 |
| Lifecycle event emission | `.claude/hooks/` custom event-synthesis hooks | Native lifecycle hooks (SessionStart / SessionEnd / PreCompact / PostToolUse / SubagentStart/Stop / TaskCreated / TaskCompleted / PermissionRequest) | ADR 004 |
| Launch-argv composition | `.claude/tmux/steward-session.sh` imperative (656 LOC) | Setup hook + `.claude/config/lanes.yaml` declarative | G-A3 |
| Per-lane system-prompt injection | Pre-`--system-prompt-file` bespoke launches | `--system-prompt-file <archetype.md>` on every launch | G-A2 |
| Token-cost accounting for native calls | Subset of `ops/token_economy.py` hard-blocks | `/usage` + `/cost` + adapter shim | G-C1 |
| Intra-session lead↔teammate ping | Minor `message_bus.py` use-cases | `SendMessage` supplemental channel | Phase-1+ per ADR B8 |
| Event dispatcher | `ops/events.py` bespoke shape | Dispatcher pattern from observability plugin + §9.7 IDs native | Primitive A (not G) |

### §4.4 What this split enables

- **Phase 2 second-cell readiness** (§11 shaping "Portability readiness" strongly improved): a new cell starts with the PORTABLE layer as authoring conventions + rewrites the SUBSTRATE-REPLACEABLE layer against its own substrate. Migration is layer-wise, not surface-wise.
- **Substrate-gate discipline** (§2.1 defer-path): if WorktreeCreate is unstable on the fleet version, G-B1 defers — but the PORTABLE layer (scope-lock, packet contract) is unaffected. Substrate churn is isolated to the REPLACEABLE layer.
- **ADR-documented rejection pattern** (§2.3): keep-bespoke decisions are rejections of substrate substitution for **methodology reasons** (native task system lacks scope field; native SendMessage is session-ephemeral). Every rejection is PORTABLE-layer-preserving by definition.
- **B.12 mechanism-change attribution** (governing plan §5-B): when a policy or mechanism changes, the net-positive/net-negative delta measurement targets the **PORTABLE layer** (mechanism effectiveness), independent of whether the SUBSTRATE-REPLACEABLE layer was concurrently migrated. This untangles "did the policy improve the fleet?" from "did the substrate migration change token costs?"

---

## §5. Coverage against escalation §3.2 gaps

| Gap from escalation §3.2 | Addressed here? | Section |
|---|---|---|
| Bespoke-surface inventory TABLE with columns `surface \| line_count \| call_site_count \| test_count \| native_candidate \| confidence \| rationale` | **Yes** | §1 |
| Dedicated methodology-preservation section separating PORTABLE vs SUBSTRATE-REPLACEABLE | **Yes** | §4 |
| Proving-run design (parallel-run + measured token-cost delta) | **Yes** | §3 |
| Broader bespoke-surface coverage (ops.py as a unit, review_driver.py, prompt_policy/** + effort_policy + tool_risk, steward-session.sh + lane_models.json) | **Yes** — all listed in §1 inventory with dispositions | §1 + §2 |

---

## §6. What this sidecar does NOT do (scope guard)

This sidecar does NOT:

- Edit `plans/steward_platform/7_primitive_G/shaping.md` (PR #2784 citation surface preserved).
- Re-do the G.1–G.N packet decomposition (shaping.md §§3–§8 is authoritative).
- Write code or modify any ops/hooks/skills files.
- File ADRs (ADR 005 / 007 / 010 / B8 / G10 already filed; ADR 003 / 004 / 001 / 006 on schedule per governing plan).
- Change governing-plan text.
- Issue a dispatch to any author lane.

All such actions route through the orchestrator per normal Primitive G dispatch cadence.

---

## §7. References

- `plans/steward_platform/7_primitive_G/shaping.md` (PR #2784) — packet-scoped execution plan; authoritative for dispatch sequence. Cited §§: §1 scope, §3.1–§3.3, §4.1–§4.2, §5.1, §6.1, §7.1–§7.4, §8.1–§8.3, §9 surface table, §10 rollback slice, §11 Phase 2 Decision Inputs, §12 Verification Plan.
- `plans/sessions/2026-04-24_g1_packet_scope_escalation.md` — reshape context (§3 gaps; §4 options; §5 recommendation).
- `plans/steward_platform/plugin_source_evaluation.md` — source-grounded evaluation of 4 native-substrate candidates; §2 code-review plugin; §3 Agent Teams; §4 observability plugin; §5 mcp-memory-service; §6 ADR seeds.
- `plans/steward_platform/0_hardening/sub/rework_spec.md` — per-surface dispositions catalog (§2 priority sequence; §3 ops catalog; §4 scripts; §5 hooks; §6 skills; §7 plans/docs; §8 worktrees).
- `plans/steward_platform/claude_code_changelog_implications.md` — Tier S native-feature inventory consumed by substrate-gate decisions.
- `plans/steward_platform/adrs/005-review-plugin-evaluation.md` — review-plugin rejection; cherry-pick validator-subagent pass.
- `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` — dispatcher pattern adoption; §9.7 IDs native.
- `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` — wholesale rejection; MCP interface reference only.
- `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` — task-queue bespoke retention; SendMessage supplemental.
- `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md` — orthogonal archetype-prompt ruling.
- `plans/steward_platform/governing_plan.md` §5-G (Primitive G scope); §10.9 Pattern 7 (rollback), Pattern 8 (observability), Pattern 9 (load-bearing ownership), Pattern 10 (verification surface); §15.2 (Phase 2 Decision Inputs schema).
- `.claude/rules/prompt_policy/analyst.md` — analyst-lane shaping obligation (this doc complies).
- `.claude/rules/effort_policy.md` — B.10 archetype × task_type matrix (PORTABLE artifact).
- `.claude/rules/tool_risk_registry.md` — B.6 dual-envelope registry (PORTABLE artifact).
- Task packet: `40438a52afaa` (reshape of `d70a297dbe6a`).

---

## Verification Plan

Per Pattern 10 + analyst prompt policy: every shaping-doc deliverable names a verification surface. This sidecar IS the deliverable of the G.1-reshape packet; its verification surface is:

| Deliverable (§N of this doc) | Class | Verification surface | Acceptance condition |
|---|---|---|---|
| §1 inventory table | shaping-data claim | `wc -l` spot-check on ≥3 rows of the LOC column against origin/main; grep-verify ≥3 `native_candidate` values against `rework_spec.md` §3 dispositions | 3/3 LOC values match ±5% (plausible sub-day drift); 3/3 dispositions match their rework_spec row |
| §2.1 substrate-gated substitutions | shaping decision table | grep-verify each packet citation (`shaping.md §3.3`, `§4.1`, `§4.2`) resolves to a real §§N row | 3/3 citations resolve |
| §2.2 substrate-available-now substitutions | shaping decision table | grep-verify each native-candidate reference against plugin_source_evaluation.md or rework_spec.md | 6/6 rows have a cited source |
| §2.3 keep-bespoke surfaces | shaping rejection table | grep-verify each rejection rationale against plugin_source_eval §N or ADR file | 9/9 rows have a cited source |
| §3 proving-run design | methodology spec | operator-review prompt: "Is the parallel-run + token-cost-delta + stop-loss trip-wire mechanism sufficient to block net-negative migrations before promotion?" | operator decision recorded (approve / revise / reject) |
| §3.3 stop-loss trip wires | mechanism spec | grep-verify each trip-condition references a measurement from §3.2 | 4/4 trip-conditions cite a §3.2 metric |
| §3.4 per-surface proving-run slots | allocation decision | operator-review prompt: "Are the window lengths (1 week / 2 weeks) adequate for the surface risk profiles?" | operator decision recorded |
| §4 methodology preservation | shaping framework | grep-verify §4.2 PORTABLE catalog against rules/registry files on origin/main; grep-verify §4.3 SUBSTRATE-REPLACEABLE catalog against §2 packet IDs | 11/11 PORTABLE rows resolve to real artifacts; 8/8 SUBSTRATE-REPLACEABLE rows cite a real migration packet |
| §5 coverage against escalation §3.2 gaps | gap-closure attestation | cross-read against `plans/sessions/2026-04-24_g1_packet_scope_escalation.md` §3.2 | 4/4 gaps named with a §N this-doc pointer |
| §6 scope-guard | negative attestation | `git diff origin/main…HEAD` on `plans/steward_platform/7_primitive_G/shaping.md` is empty; no code changes in `src/` or `scripts/internal/` or `.claude/` | `git diff --stat` confirms only 1 new file added at `plans/steward_platform/7_primitive_G/bespoke_surface_audit.md` |
| §7 references | citation completeness | `ls` / `gh` verify each cited path/PR exists | 100% resolve |
| This Verification Plan | lint | `scripts/internal/agent_readability_lint.py plans/steward_platform/7_primitive_G/bespoke_surface_audit.md` (once G1 script lands) | lint exits 0 on ownership / verification-contract rules |

**Pass = operator reads, the 4 §3.2 gaps are closed, PR #2784 citation surface is untouched (§6 scope-guard), and the sidecar ships as a Primitive G Phase 0 companion artifact.**

**Fail modes:**
- Any §1 inventory row whose `native_candidate` column contradicts a rework_spec.md §3 disposition without a cited re-derivation rationale.
- Any §2 decision that re-opens a closed ADR (ADR 005 / 007 / 010 / B8 / G10) rather than citing its conclusion.
- Any §3 proving-run discipline that measures only rollback (§10 shaping re-coverage) instead of the measured token-cost + behavioral-equivalence deltas.
- Any §4 methodology row classified PORTABLE but in fact substrate-dependent, or classified SUBSTRATE-REPLACEABLE but missing a cited migration packet.
- Any edit in `git diff` outside the single new file path (scope-guard violation).

---

**End of sidecar audit.**
