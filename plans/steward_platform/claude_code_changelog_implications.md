# Claude Code Changelog Implications for Steward Platform

**Date:** 2026-04-23 (initial)
**Status:** ACTIVE REFERENCE — refreshed by the changelog review skill (§5-D of governing plan, scheduled 2-3×/week)
**Purpose:** Tier-ranked inventory of Claude Code native features relevant to the steward platform. Drives native-substrate adoption decisions per §10.9 extensibility pattern #2 ("native-substrate-first defaults").
**Companion artifacts:** `phase2_harness_engineering_research.md` (borrowed-practices memo); `post_phase2_sidecar.md` (deferred ideas).
**Latest scan date:** 2026-04-23 (initial seed; subsequent updates by `/review-claude-changelog` skill).

---

## 1. How to use this doc

This is a **living reference**, not a roadmap. The changelog review
skill refreshes it on a schedule. Operator promotions / deferrals /
rejections of Tier-S items become Phase 0 sub-plan entries or get
folded into existing primitive Work bullets in the governing plan.

**Read order for an agent loading this for context:**
1. §2 (current Tier S inventory — what to adopt now)
2. §3 (plan-tier vs. system-rework-tier comparison — why some items promoted)
3. §4 (per-system rework specs — what changes in existing code)
4. §5 (changelog review skill spec — how this doc gets refreshed)
5. §6 (external-signal sources — where the skill scrapes)

---

## 2. Tier inventory (Jan-Apr 2026 snapshot)

Sources reviewed: `https://code.claude.com/docs/en/changelog`,
`https://code.claude.com/docs/en/whats-new`, weekly pages
`whats-new/2026-w13`, `2026-w14`, `2026-w15`. Plus operator-curated
threads: Boris Cherny Opus 4.7 release thread (`@bcherny`,
2026-04-16); davidad / thebes `--system-prompt-file` thread
(2026-04-20).

### Tier S — adopt now, pre-Phase-2

Each item names the steward primitive(s) where it lands per draft 7.

| Item | Primitive(s) | Notes |
|---|---|---|
| Monitor tool + self-pacing `/loop` | A, H | Replaces polling in `ops/monitor.py` and `ops/attention.py`; drives replay-assertion polling in H |
| Conditional hooks | A, E | Scope hook trigger conditions precisely; reduces per-tool-call overhead across existing hooks |
| Lifecycle hooks (PermissionDenied, StopFailure, TaskCompleted, TeammateIdle, ConfigChange) | A, D, E | Native event emitters absorb into unified schema; archivist subscribes; active-triage signals |
| WorktreeCreate / WorktreeRemove hooks + declarative isolation | G | Largest single portability win; ~80% of `ops/worktrees.py` collapses |
| Session metadata (`${CLAUDE_SESSION_ID}`, `last_assistant_message`, session title) | A, C | First-class schema IDs; lane-attribution clarity |
| Recaps | A, C, D | Native session-summary feature; archivist input; richer MEMORY.md handoffs |
| Shared project memory across worktrees | C | Substrate for MEMORY.md cross-worktree linkage |
| HTTP hooks | A, E | Replace shell-glue for service integration (Phoenix, bus subscribers) |
| Task system with dependency tracking | B (B.8 evaluation ADR) | Evaluate vs. bespoke task_queue contract; mostly stays bespoke |
| Read-tool token reductions / large tool result persistence | F, H | Changes baseline cost profile; baseline re-capture required |
| Native `/usage` | F | Comparison feed for Slice F evaluation; outlier detection |
| Native `/cost` | F | Token-economy supplemental telemetry |
| Per-tool MCP result-size override | F (dashboard outputs) | Cap operational-query token cost |
| Plugin executables on PATH | C, G | Skill distribution model; simpler discovery and installation |
| Tool-search | C, G | Substrate for skill discovery across 30+ skills |
| `--system-prompt-file` per lane | B (B.9), G (Setup hook) | Sparse custom prompts beat default for 4.7+; per-lane `.claude/system_prompts/<lane>.md` |
| `/effort` adaptive-thinking configuration | B (B.10), F | Per-task-type effort recommendations (lower / xhigh / max); Boris Cherny Opus 4.7 guidance |
| Auto memory (supplementary) | C, G | Inflow layer for archivist; bespoke curated memory continues |
| Setup hook event | G | Formalizes `steward-session.sh` bootstrap into declarative config + Setup-hook entrypoint |
| Remote-control / remote sessions | G | Substrate match for existing away-mode + Telegram + push-notification path |
| Computer use in Desktop / CLI | G (playtest skills consolidation) | Browser-game visual verification; consolidates 4 playtest variants → 2 |

### Tier A — adopt narrowly or evaluate-only

| Item | Primitive(s) | Notes |
|---|---|---|
| `/fewer-permission-prompts` skill (periodic) | G | Schedule 1×/week to scan session history and propose `permissions.allow` additions |
| `/autofix-pr` (evaluation-only) | C (ADR 005), E | Overlap with `scripts/internal/review_driver.py`; document boundary, don't replace |
| Auto mode codification | G (ADR 006) | Already in use; document the user-scope `autoMode.environment` config |
| Recaps as session-handoff input (already in Tier S above) | A, C, D | Listed for cross-reference |
| Focus mode (`/focus`) | (operator UX, not platform-level) | Operator-personal preference; not codified in plan |

### Tier B — track, likely post-Phase-2

| Item | Notes |
|---|---|
| `/team-onboarding` | Single-operator scope; not relevant until multi-operator |
| Ultraplan | Risk of second planning surface before our own is proven |
| Native channels (deeper) | Beyond message-bus closeout in Primitive E; revisit at Phase 2 |

### Tier C — out of steward scope

| Item | Notes |
|---|---|
| Keyboard shortcuts, rendering, transcript search, UI polish | Operator-personal; not platform-level |
| PowerShell tool / Windows-specific / enterprise auth / provider setup | macOS-only operator; not relevant |

---

## 3. Plan-tier vs. system-rework-tier comparison

Items that *promote* in tier rank when re-evaluated against existing
steward system rework (vs. governing-plan inclusion):

| Item | Plan tier | System-rework tier | Why promoted |
|---|---|---|---|
| Auto memory | A | S | Direct fit for `ops/memory.py` + MEMORY.md mechanism |
| Setup hook event | A | S | Direct fit for `.claude/tmux/steward-session.sh` bootstrap |
| Remote-control / remote sessions | A | S | Direct fit for existing away-mode + Telegram path |
| Native `/cost` breakdown | A | S | Direct fit for `ops/token_economy.py` rework |
| Native `/usage` (added per Boris Cherny thread) | (new) | S | More comprehensive than `/cost`; parallel-session / subagent / cache-miss / long-context breakdown with optimization tips |
| Plugin executables on PATH | A | S | Direct fit for `ops/skill_promotion.py` + skill distribution |
| Per-tool MCP result-size override | A | S | Direct fit for `ops.py dashboard` / `task list` / `inbox` outputs |
| Computer use in Desktop / CLI | B | S | Direct fit for browser-game playtest skills |
| Tool-search | A | S | Live example: ToolSearch loaded WebSearch this very session |
| `/autofix-pr` | B | A (evaluate) | Direct overlap with `scripts/internal/review_driver.py` |
| Auto mode codification | B | A | Already in use; document existing config |

The pattern: **plan-tier rankings answer "include in new scope?"; system-rework-tier rankings answer "rework existing code to use?"** Different decision contexts → different rankings.

---

## 4. Per-system rework specs

Tactical detail lives in the sub-plan at
`plans/steward_platform/0_hardening/sub/rework_spec.md`. Headline
disposition for the largest existing systems:

| System | Disposition | Trigger feature(s) |
|---|---|---|
| `ops/worktrees.py` (44 hard-blocks) | **Trim hard** (~80%) | WorktreeCreate/Remove hooks + declarative isolation |
| `ops/monitor.py` (polling) | **Trim hard** | Monitor tool + TeammateIdle |
| `ops/attention.py` (custom synthesis) | **Trim moderate** | Conditional hooks + lifecycle subscriptions |
| `ops/dashboard.py` heartbeat classifier (#2743) | **Retire** (irony — just shipped) | TeammateIdle |
| `ops/memory.py` + `ops/index.py` + MEMORY.md | **Modify substrate** | Shared project memory across worktrees + auto memory |
| `ops/token_economy.py` (22 hard-blocks remain bespoke) | **Modify substrate; bespoke debt remains** | `/usage` + `/cost` + read-tool reductions + per-tool MCP override |
| `ops/message_bus.py` | **Modify; keep core** | HTTP hooks + native channels evaluation + lifecycle hook event sources |
| `ops/task_queue.py` | **Modify; partial native adoption** | Native task system (B.8 evaluation) |
| `.claude/hooks/**` (sprawling) | **Migrate ~30-50%** | Conditional hooks + lifecycle subscriptions + HTTP hooks |
| `.claude/tmux/steward-session.sh` | **Replace with Setup hook** | Setup hook event + `--system-prompt-file` |
| `.claude/skills/**` (30+ skills) | **Consolidate** (monitoring 6→2; playtest 4→2) | Monitor + TeammateIdle + computer use |
| `.claude/agents/steward-*.md` | **Augment with system_prompts** | `--system-prompt-file` per lane |
| `scripts/internal/audit_portability.py` | **Reframe target** | Becomes "native-adoption coverage measurement" once worktrees migrate |

---

## 5. Changelog review skill spec

Per §5-D of governing plan draft 7.

- **Skill:** `/review-claude-changelog`
- **Schedule:** `/loop 3d /review-claude-changelog` (2-3×/week)
- **Implementation:** `scripts/internal/changelog_review.py` (~75 lines)
- **Sources scraped (G8 updated, draft 8):**
  - `https://code.claude.com/docs/en/changelog`
  - `https://code.claude.com/docs/en/whats-new`
  - Per-week pages `https://code.claude.com/docs/en/whats-new/2026-wNN` (auto-discover)
  - **`https://github.com/anthropics/claude-code/releases`** (structured release notes; draft 8 addition)
  - **`docs.anthropic.com` blog index** (architecture / model-behavior posts; draft 8 addition)
  - **Plugin registry sources (draft 8):** `github.com/anthropics/claude-plugins-official`, `claudepluginhub.com`, `claudemarketplaces.com`, `github.com/ComposioHQ/awesome-claude-plugins`, `github.com/Kamalnrf/claude-plugins`, `www.aitmpl.com`, `claude-plugins.dev` — new plugin listings treated as `plugin-adoption-candidate` sub-tagged `native-substrate-signal` entries
  - Operator-curated `knowledge/external_signal_sources.md` URLs (Anthropic team posts; operator X/Twitter list URLs rather than individual threads, per G8 scalability note; davidad commentary)
  - Wayback / archive crawls for earlier weekly pages: **best-effort; not a readiness blocker** (G8 trim — wayback added fragility without proportionate signal)
  - `/insights` tool output (when relevant)
- **Output:** `knowledge/_candidates/<date>_changelog.md` with adoption candidates per the schema:
  ```
  ### <feature name>
  **Source:** <URL or doc reference>
  **Steward primitive(s) touched:** <A/B/C/D/E/F/G/H>
  **Stales harness assumption:** <yes/no; if yes, name the entry>
  **Tier recommendation:** S / A / B / C
  **Operator decision:** accept / defer / reject (filled at review)
  ```
- **Integrations:**
  - Stales `knowledge/harness_assumptions.md` entries when native ships a capability we synthesize.
  - Writes ledger entries to Phase 2 Decision Inputs digest under tag `native-substrate-signal`.
  - Updates this file's "Latest scan date" line.
  - Appends new findings to §2 tier inventory above.

---

## 6. External-signal sources

Operator-curated list lives at `knowledge/external_signal_sources.md`.
Initial seed (filled at Phase 0 kickoff):

- Boris Cherny tweet threads (Opus 4.7 release; auto mode; effort; verification; recaps; focus mode)
- davidad / thebes `--system-prompt-file` and global CLAUDE.md insertion-order discussion (2026-04-20)
- Anthropic Claude Code blog (when posts are published)
- (Operator adds others as discovered)

Format per entry: URL + category tag (release / workflow / model-behavior / tool-spec) + last-scraped date.

---

## 7. Refresh history

| Date | Trigger | Changes |
|---|---|---|
| 2026-04-23 | Initial seed (operator-fed Jan-Apr 2026 review) | Tier inventory established; per-system rework specs; skill spec |
| 2026-04-23 | Draft 8 tightening (G8 fix + plugin-sweep expansion) | GitHub release notes + docs.anthropic.com blog added to sources; wayback trimmed to best-effort; plugin registry URLs added; Agent Teams + code-review plugin + mcp-memory-service + melodic-software/claude-code-observability added as Tier S ADR targets (B.8 / ADR 005 / ADR 010 / ADR 007); April 2026 Claude Code updates noted (worktree switching; PreCompact hook blocking; background plugin monitors); plugin source evaluation dispatched to analyst-a (packet `a0cb1ca3a256`) for follow-up fold-in to ADR seeds |
| (future) | Scheduled scan | (filled by `/review-claude-changelog` runs) |

---

## 8. Plugin discovery (new in draft 8)

The changelog review skill is **not limited to the official changelog**.
Plugin-registry new-listings are first-class `plugin-adoption-candidate`
signals. Registries scraped (listed above in §5) yield plugin candidates
which follow the three-tier preference of §10.9 Pattern 2:

1. **Native Claude Code feature** (Monitor, lifecycle hooks, Agent Teams, `--system-prompt-file`, etc.)
2. **Official plugin** (`anthropics/claude-plugins-official`; e.g., code-review plugin for ADR 005)
3. **High-trust third-party plugin** (well-maintained, clear license, good adoption — e.g., `melodic-software/claude-code-observability` for ADR 007, `doobidoo/mcp-memory-service` for ADR 010)
4. **Bespoke synthesis** (last resort)

Each adoption decision files an ADR per §10.9 Pattern 2 discipline.
Plugin source evaluation (analyst-a packet `a0cb1ca3a256`, output at
`plans/steward_platform/plugin_source_evaluation.md`) provides the
evidence base for ADRs 005/007/010 + B.8 adoption decisions. Findings
fold into ADR seeds as follow-up commit post-draft-8-promotion.

### April 2026 Claude Code updates to absorb

- **Worktree switching** — extends WorktreeCreate/Remove substrate; may simplify multi-worktree operator workflows
- **PreCompact hook blocking** — relevant to Primitive D archivist + compaction discipline (archivist may pre-compact-block during session postmortem generation)
- **Background plugin monitors** — relevant to changelog review skill; may make scheduling cleaner than `/loop 3d`
