# Sub-Plan: Existing Steward System Rework Spec

**Date:** 2026-04-23
**Status:** PROPOSED — Phase 0 sub-plan under Primitive G (existing-debt closeout + native-substrate migration)
**Parent:** `plans/steward_platform/governing_plan.md` (when promoted; currently `governing_plan.draft7.md`) §5-G
**Companion:** `plans/steward_platform/claude_code_changelog_implications.md` (Tier S inventory)
**Purpose:** Per-surface tactical analysis of existing steward systems. Catalogues every ops-package module, hook, script, and skill with a disposition (keep / modify / consolidate / trim / delete) under native-substrate adoption. Phase 0 execution artifact — author lanes execute against this catalog.

---

## 1. How to use this doc

This sub-plan is a **dispositions catalog**, not a how-to. Each row
specifies: current state → target state → trigger feature → estimated
effort. Author lanes claim rows by opening sub-sub-plan PRs against the
disposition (e.g., "implement worktrees.py native migration per row 1").

**Read order for an agent loading this:**
1. §2 (highest-leverage rows — biggest LOC reductions or most native-substrate-blocking)
2. §3 (full ops package catalog)
3. §4 (scripts catalog)
4. §5 (hooks catalog)
5. §6 (skills catalog)
6. §7 (plans / docs cleanup)
7. §8 (worktrees filesystem cleanup)

---

## 2. Highest-leverage rows (priority sequence)

| # | Row | Reason |
|---|---|---|
| 1 | `ops/worktrees.py` → native WorktreeCreate/Remove + declarative isolation | Largest single LOC reduction; resolves portability debt concentration |
| 2 | Monitor / attention / dashboard → native Monitor + lifecycle hooks | Multi-file simplification; aligns with Primitive A scope |
| 3 | Hook conditionalization + lifecycle subscriptions | Reduces per-tool-call overhead; simplifies hook count meaningfully |
| 4 | Skills consolidation (monitoring 6→2; playtest 4→2) | Operational clarity; reduces skill-discovery noise |
| 5 | Token economy native /usage + /cost integration + read-tool baseline re-capture | Slice F decision improves on better-baselined data |
| 6 | Memory + index + snapshots evaluation for consolidation | Three files possibly collapsible to one or two; substrate is shared project memory |
| 7 | Plan fragmentation cleanup (agent_ops Phase 5 + session-plan archives) | Reduces "what's still active?" cognitive load |
| 8 | Hook HTTP migration | Cleaner integration surface for external services |
| 9 | `audit_portability.py` reframing | Becomes "native-adoption coverage" |
| 10 | Playtest skills consolidation (4→2 with computer use) | Operational simplification |
| 11 | `--system-prompt-file` rollout per lane | 4.7+ behavior improvement; high leverage low cost |
| 12 | Setup hook formalization of `steward-session.sh` | Bootstrap cleanup; declarative replaces imperative |

---

## 3. Ops package (`src/bid_euchre/ops/`)

| File | Disposition | Trigger feature | Effort | Owner ADR |
|---|---|---|---|---|
| `worktrees.py` | **Trim hard** (~80%) | WorktreeCreate/Remove + declarative isolation | High | (file when migration sub-sub-plan opens) |
| `monitor.py` | **Trim hard** | Monitor tool + TeammateIdle | Medium | — |
| `attention.py` | **Trim moderate** | Conditional hooks + PermissionDenied/StopFailure subscriptions | Medium | — |
| `dashboard.py` heartbeat classifier (#2743) | **Retire** | TeammateIdle | Low | — |
| `dashboard.py` core (lane status, CPU load, task completion) | **Modify** (per-tool MCP result-size override; session metadata enrichment) | MCP override; session title hooks | Low | — |
| `audit_trail.py` | **Modify; keep** | `${CLAUDE_SESSION_ID}` + `last_assistant_message` first-class | Low | — |
| `events.py` | **Modify; expand normalization** (becomes the native-event normalizer) | Native lifecycle hooks | Medium | — |
| `snapshots.py` | **Consolidate candidate** with `audit_trail.py` | (no native trigger; cleanup) | Low | — |
| `index.py` | **Consolidate candidate** with `memory.py` | Shared project memory | Low | — |
| `memory.py` | **Modify substrate** | Shared project memory across worktrees + auto memory supplementary | Medium | — |
| `message_bus.py` | **Modify; keep core** (HTTP hooks for external; native channels evaluation) | HTTP hooks; channels improvements | Medium | ADR 004 |
| `task_queue.py` | **Modify; partial native adoption** (B.8 evaluation) | Native task/dependency system | Medium | ADR (B.8) |
| `worker_pool.py` | **Trim moderate** | TeammateIdle for availability; worktree migration cascades | Medium | — |
| `scheduler.py` | **Trim moderate** | Monitor tool covers most; conditional hooks for triggers | Medium | — |
| `skill_promotion.py` | **Modify; extend distribution** | Plugin executables on PATH | Low | — |
| `telegram_filter.py` | **Evaluate** for absorption | Remote sessions / native channels | Low | — |
| `token_economy.py` (22 hard-blocks) | **Modify substrate; bespoke debt remains** | `/usage`, `/cost`, read-tool reductions, per-tool MCP override | High | ADR 003 |
| `control_plane.py` | **Modify; expand event sources** | ConfigChange hook | Low | — |
| `core/provider.py` + `core/interfaces.py` + `adapters/` | **Keep + extend** (Platform-10 foundation) | (extensibility pattern #1) | Low | — |
| `alert_push.py` | **Keep** (steward-specific alerting; no native analog) | — | Low | — |
| `away_mode.py` | **Evaluate** for absorption into native remote sessions (per G6/Track 2.4 keep through Phase 0) | Remote sessions (Tier S) | Low | — |
| `ci.py` | **Keep** (CI integration is steward-specific) | — | Low | — |
| `compaction.py` | **Modify; evaluate** native PreCompact blocking (April 2026 Claude Code update) | PreCompact hook | Low | — |
| `context_safety.py` | **Keep** (steward-specific context guardrails) | — | Low | — |
| `fs_boundary.py` | **Keep** (filesystem protection; steward-specific) | — | Low | — |
| `idle_detector.py` | **Trim/retire** in favor of TeammateIdle | TeammateIdle | Low | — |
| `lane_heartbeat.py` | **Retire** in favor of TeammateIdle (overlaps with `dashboard.py` heartbeat classifier) | TeammateIdle | Low | — |
| `learning.py` | **Modify; integrate** with B.12 improvement-mechanism evaluation | — | Medium | — |
| `queue_priority.py` | **Keep; evaluate** native task-system priority via B.8 ADR | Agent Teams task dependencies | Low | ADR B.8 |
| `recovery.py` | **Keep** (steward-specific recovery protocols) | — | Low | — |
| `remote_ack.py` | **Modify; evaluate** absorption via remote sessions (Track 2.4: keep through Phase 0; evaluate cutover in Phase 1) | Remote sessions | Low | — |
| `repairs.py` | **Keep** (bespoke repair catalog; steward-specific) | — | Low | — |
| `retries.py` | **Keep** (steward-specific retry semantics) | — | Low | — |
| `review_queue.py` | **Keep; evaluate** integration with official code-review plugin | Code-review plugin | Medium | ADR 005 |
| `reviews.py` | **Modify; evaluate** overlap with `/autofix-pr` + code-review plugin | `/autofix-pr`, code-review plugin | Medium | ADR 005 |
| `scope.py` | **Keep** (scope-lock enforcement; steward-specific semantics) | — | Low | — |
| `status.py` | **Modify substrate** (session metadata + session title hooks) | Session metadata hooks | Low | — |
| `supervisor.py` | **Keep; evaluate** Agent Teams team-lead overlap | Agent Teams | Medium | ADR B.8 |
| `telegram_push.py` | **Modify; evaluate** absorption via remote sessions (Track 2.4: keep through Phase 0) | Remote sessions | Low | — |
| `watchdogs.py` | **Keep** (steward-specific watchdog timers) | — | Low | — |

**G6 coverage note (draft 8):** All 42 ops modules now enumerated. Default disposition for "Keep" modules with no native analog and no consolidation partner: "Keep; review at Phase 1 close for native analog evolution." Re-evaluate dispositions after plugin source evaluation artifact (packet `a0cb1ca3a256`) lands and ADRs 005/007/010 + B.8 are filed at Phase 0 kickoff.

**G10/G13 `.claude/agents/` catalog (draft 8, new row under §3):**

| Directory | Disposition | Trigger feature | Effort |
|---|---|---|---|
| `.claude/agents/` (23 files: 19 lane files + 4 specialist reviewers + README) | **Consolidate to 8 archetypes per B.9** (orchestrator / ops / review / analyst / author / brws-author / flex / scratch). First-deliverable sub-sub-plan under Primitive G publishes the 19→8 mapping. Relationship to `.claude/system_prompts/<archetype>.md` resolved via ADR at Phase 0 kickoff (replacement / supplement / orthogonal per §5-B B.9). Specialist reviewer agents (architecture, correctness, coverage, plan-reviewer) stay as subagent archetypes, not lane archetypes. | `--system-prompt-file` (B.9) | Medium |

**G7 hook-file enumeration (draft 8 deferral note):** 34 concrete hook files under `.claude/hooks/` include: `alert-inject.{py,sh}`, `attention-broker-autostart.sh`, `compact-context.sh`, `fleet-check-autostart.sh`, `inbound-channel-audit.{py,sh}`, `inbox-completion-inject.{py,sh}`, `post-bash-dispatch.sh`, `post-merge-notify.sh`, `post-monitor-push-relay.sh`, `post-plan-review.sh`, `post-push-ci-check.sh`, `post-task-event.sh`, `post-telegram-audit.sh`, `post-tool-daemon-notify.sh`, `post-write-check.sh`, `pre-worktree-cleanup.sh`, `rule-loader.sh`, `scope-drift-guard.sh`, `session-sync-worktree.sh`, `urgent-state-guard.py`, `worktree-guard.sh`, `worktree-reminder.sh` (22 uncategorized-by-name), plus the category rows already in §5. ADR 004 (hook migration boundary) files at Phase 0 close with per-file disposition (native-lifecycle / conditional / HTTP / bespoke).

**G12 session-plan sweep script (draft 8):** `scripts/internal/sweep_session_plans.py` (~30 lines) enumerates 264 session plans, classifies by Outcome section (COMPLETED / ABANDONED / SUPERSEDED / open), archives non-open to `plans/sessions/_archive/` in one pass. Added to Primitive G sub-sub-plan list.

---

## 4. Scripts (`scripts/internal/`)

| Script | Disposition | Reasoning |
|---|---|---|
| `ops.py` | **Modify; thin some subcommands** | Some subcommands become thin wrappers over native task system if B.8 adopts; dashboard subcommand benefits from per-tool MCP override |
| `review_driver.py` | **Keep + evaluate `/autofix-pr` overlap** (ADR 005) | Bespoke loop has steward-specific semantics |
| `audit_portability.py` | **Modify; reframe target** | When worktrees.py migrates to native, the script's enumeration shrinks; reframe as "native-adoption coverage measurement" |
| `verify_issue_closure.py` | **Keep** | Tier-2 issue verification is steward-specific |
| `set_review_status.sh` | **Keep** | Small utility |
| `review_lane_runner.py` | **Keep + flag-update** | Auto-mode-aware per `--permission-mode auto` requirement |
| `compile_decision_inputs.py` (planned) | **New per draft 7** | F6 ownership |
| `agent_readability_lint.py` (planned) | **New per draft 7 G1** | Goal #16 enforcement |
| `archivist.py` (planned) | **New per draft 6** | Primitive D inflow + outflow |
| `changelog_review.py` (planned) | **New per draft 7** | Primitive D changelog mode + external-signal sources |

---

## 5. Hooks (`.claude/hooks/`)

Sprawling shell + Python set. Material consolidation potential.

| Hook category | Current | Target | Trigger feature |
|---|---|---|---|
| Pre-bash-dispatch | Unconditional shell | **Conditional hook** (scope to specific tool patterns) | Conditional hooks |
| Permission-denied logging | Unconditional shell | **Native `PermissionDenied` subscription** | PermissionDenied hook |
| Lane-heartbeat (recently rewritten as pure shell #2739) | Conditional pure shell | **Native `TeammateIdle` subscription** (replace) | TeammateIdle |
| Lane-id resolver (consolidated #2741) | Shell library | **Keep** (shared utility) | — |
| `post-pr-review.sh` / `post-pr-review-loop.sh` | Bespoke review pipeline | **Keep** (steward-specific) | — |
| `pre-merge-review-guard.sh` | Bespoke merge guard | **Keep** | — |
| `post-merge-review.sh` | Bespoke post-merge review | **Keep** | — |
| Custom event-synthesis hooks | Shell + Python | **Replace with native lifecycle subscriptions** | Lifecycle hooks |
| Hooks POSTing to local services | Shell-glue | **Replace with HTTP hooks** | HTTP hooks |
| `lane-heartbeat-hook.sh` (per #2739) | Pure shell | **Retire** when TeammateIdle adopted | TeammateIdle |

Net target: 30-50% surface reduction; rest migrates to conditional or
HTTP form.

---

## 6. Skills (`.claude/skills/`) — 30+ skills consolidation

| Family | Current skills | Target | Trigger |
|---|---|---|---|
| Monitoring | `monitor`, `check-in`, `fleet-check`, `inbox-poll`, `lane-status`, `capture-pane` (6) | **Collapse to 2** (`/fleet-check` aggregates; `/lane-status` for one-off) | Monitor + TeammateIdle |
| Triage / review | `triaging-issues`, `proving-issues`, `reviewing-changes`, `check-reviews`, `monitor-pr`, `debugging-ci`, `review` (7) | **Keep** (mostly); evaluate `triaging-issues`/`proving-issues` overlap | — |
| Delegation | `delegate-task`, `start-task` (2) | **Keep** (dispatch protocol) | — |
| Playtest | `playtesting`, `playtest-hybrid`, `playtest-strategic`, `playtest-playwright` (4) | **Consolidate to 2 or 1+computer-use** | Computer use in Desktop / CLI |
| Setup / lifecycle | `init`, `park`, `session-end`, `update-config`, `keybindings-help`, `recovering-context` (6) | **Keep** | — |
| Skill management | `fewer-permission-prompts`, `simplify` (2) | **Keep**; schedule `/fewer-permission-prompts` 1×/week | — |
| Specific workflows | `validating-changes`, `running-experiments`, `analyzing-results`, `adding-strategies`, `managing-worktrees`, `planning-code-first`, `reviewing-repo`, `review-plan`, `reference-docs` (9) | **Keep** | — |
| New per draft 6/7 | `/run-archivist`, `/compile-decision-inputs`, `/create-plan`, `/create-adr`, `/lint-agent-readability`, `/review-claude-changelog` | **All new; stay** | Various |
| Loop / scheduling | `loop`, `schedule`, `away-mode` (3) | **Evaluate** against Monitor + remote sessions | Monitor + Remote sessions |
| External | `claude-api`, `telegram:access`, `telegram:configure` (3) | **Keep** | — |
| Run management | `run-fleet` (1) | **Keep** (operator-driven autonomous mode) | — |

Net target: monitoring 6→2 = -4; playtest 4→2 = -2; loop/schedule/away
3→1 = -2 (after evaluation). Total skill-count reduction ~8 from
existing 30+; new additions per draft 6/7 add ~6 (net flat). The win
is operational clarity, not raw count reduction.

---

## 7. Plans / docs cleanup

| Item | Disposition |
|---|---|
| `plans/agent_ops/5_extraction/` | **Retire** with explicit status note (per Primitive G) |
| `plans/agent_ops/5_cross_model/` | **Retire** with explicit status note |
| `plans/agent_ops/5_skill_learning/` | **Retire** with explicit status note (or absorbed into Primitive B SP-5-02 closeout) |
| `plans/agent_ops/5_portability_and_learning/` | **Retire** with explicit status note |
| `plans/agent_ops/post_pr5_follow_on_roadmap.md` | **Archive** (explicitly superseded) |
| Session plans with ABANDONED/SUPERSEDED outcomes | **Sweep and archive** (move to `plans/sessions/_archive/`) |
| Multiple memory files (MEMORY.md + indexes) | **Keep** (already index-style per goal #16) |
| `.claude/rules/` overlap with `CLAUDE.md` | **Audit** (analyst-driven; periodic) |

---

## 8. Worktrees filesystem cleanup

Sweep against `.claude/rules/75_worktree_protection.md` protected list.
Non-protected ephemeral worktrees safe to remove:

| Worktree | Disposition |
|---|---|
| `Bid-Euchre-archive` | **Evaluate** (likely safe to remove if old PR) |
| `Bid-Euchre-chore-phase5-closeout` | **Evaluate** (likely closed) |
| `Bid-Euchre-plans-proving-debt` | **Evaluate** (likely closed) |
| `Bid-Euchre-r5` | **Evaluate** (unknown status) |
| `Bid-Euchre-work-20260324-172018` | **Remove** (ephemeral name; likely stale) |
| `worktree-ci-shard-promotion` | **Evaluate** (likely closed) |
| `Bid-Euchre-steward-platform-d6` | **Remove** (ephemeral PR worktree from #2748; merged) |
| `Bid-Euchre-steward-platform-d7` | **Remove** (this worktree, after PR merges) |

---

## 9. Repo structure (Phase 2+ consideration)

Not a Phase 0 deliverable, but worth surfacing for Phase 2 inputs:

The deeper issue is that `src/bid_euchre/ops/` conflates "Bid-Euchre
game code" with "steward platform code." Platform-10 started addressing
this with `core/` + `adapters/`, but the boundary is incomplete (66
hard-blocks combined across `worktrees.py` + `token_economy.py`).
Post-Phase-2, if portability proceeds, the steward platform should
likely become its own package — `src/steward/` or even a separate
distributable. That's a Phase 2+ decision; this sub-plan does not
commit it.

---

## 10. Outcome

_To be filled after rework execution._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- Effort actuals vs. estimates: <table>
- Native-substrate adoption coverage at completion: <%>
- Notes: deviations from spec; new dispositions discovered mid-execution

## Phase 2 Decision Inputs

**Portability readiness:** sub-plan itself is a portability-signal artifact — the per-surface dispositions catalog *is* the migration shape that future second-repo audits will compare against.
**Meta-layer need:** no change.
**Kill signal for primitive(s) named:** N/A (sub-plan pre-execution).
**Re-evaluation needed in Phase 3:** no.
**Surprise finding:** none yet.
**Disposition:** open
