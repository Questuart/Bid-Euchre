# Handoff: Claude Code Native-Substrate Plugin Source Evaluation

**Date:** 2026-04-23
**From:** orchestrator (co-drafted with operator)
**To:** steward-analyst (lane TBD — source-reading research task; fresh eyes not required since no prior plan review is in scope)
**Scope:** Read the actual source of four Claude Code native-substrate candidates flagged as Tier S adoption evaluations in `plans/steward_platform/claude_code_changelog_implications.md` §2. Produce adoption decisions informed by real artifact shape, not marketing/search summaries.
**Output artifact:** `plans/steward_platform/plugin_source_evaluation.md` (new file, ~400 lines).

---

## 1. Context (skim, don't re-derive)

The steward platform governing plan draft 7 (merged via PR #2750; now at `plans/steward_platform/governing_plan.draft7.md`) commits to four ADR-level evaluations of Claude Code native substrate candidates:

| ADR | Target | Primitive(s) |
|---|---|---|
| **B.8** | Agent Teams + TeammateTool + Task system | Primitive B (dispatch/skill/prompt-policy) |
| **ADR 005** | Official code-review plugin + cloud `/autofix-pr` | Primitive C/E; overlaps with `scripts/internal/review_driver.py` |
| **ADR 007** | `melodic-software/claude-code-observability` plugin | Primitive A (trace/observability) |
| **ADR 010** | `doobidoo/mcp-memory-service` | Primitive C/D (KB + archivist) |

Each was elevated from orchestrator tier-research that relied on marketing claims / search summaries, not source-level reading. Before draft 8 (the tightening pass applying analyst-d's G6-G13 findings) promotes to canonical `governing_plan.md`, the ADR boundaries should reflect source-informed decisions. This handoff dispatches that source-reading work.

**What draft 8 does NOT need from this task:** draft 8 itself ships without waiting for your findings. It carries the ADRs as evaluation targets with current framing. Your findings fold in as a follow-up update to ADR content (`plans/steward_platform/adrs/NNN-*.md` drafts filed at Phase 0 kickoff) or as a same-session scoped amendment PR.

## 2. Your task

Read the source of the four candidates and produce adoption decisions for each.

### Target 1 — Official code-review plugin

**Source:** `https://github.com/anthropics/claude-code/tree/main/plugins/code-review` (source accessible via `gh api` or `WebFetch`).

**Context:** per `https://claude.com/plugins/code-review` — five specialized reviewers (CLAUDE.md compliance, bug detection, git history context, previous PR comment review, code comment verification) with 0-100 confidence scoring (threshold 80 default) to reduce false positives.

**Steward overlap:**
- `scripts/internal/review_driver.py` — single-Codex-CLI review
- `/reviewing-changes` skill
- The `reviewing-changes` advisory status published via `scripts/internal/set_review_status.sh`
- The 50-106 precheck false-positive pattern recent PRs (#2745–#2750) keep hitting

**Evaluation questions to answer:**
1. What prompt structure / reviewer roles does the plugin use? Are they orthogonal to steward's precheck + Codex CLI review pipeline, or do they overlap?
2. How does confidence scoring work under the hood? Ensemble voting? Separate-then-threshold? Can it be configured?
3. How does the plugin integrate with CI and status contexts? Does it write to `reviewing-changes` or a different status?
4. What steward-specific semantics (scope-lock enforcement, Codex CLI auth, verdict bridge to merge guard) would need adapter-shim work?
5. Adoption decision: **adopt wholesale** / **cherry-pick reviewer roles and confidence-scoring pattern** / **reference only for review_driver.py improvements** / **reject — single-Codex-CLI works**.

### Target 2 — Agent Teams + TeammateTool

**Source:** Claude Code docs at `https://code.claude.com/docs/en/agent-teams` + source of the Task tool / TeammateTool APIs (searchable via `gh api` on `anthropics/claude-code` or via `claude --help` / `claude agent-teams --help`).

**Context:** "One session acts as the team lead, coordinating work, assigning tasks, and synthesizing results, while teammates work independently, each in its own context window, and communicate directly with each other." Enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` settings.json flag.

**Steward overlap:**
- `src/bid_euchre/ops/task_queue.py` — scope-locked task packets, domain routing, lane affinity, routing metadata (`task_type`, `complexity_estimate`, `model_hint`, `effort_hint`)
- `src/bid_euchre/ops/worker_pool.py` — round-robin / explicit targeting
- `src/bid_euchre/ops/scheduler.py` — task/event scheduling
- The existing orchestrator → author-lane dispatch protocol: orchestrator creates packet via `ops.py task create` → `ops.py task dispatch <packet> <lane> --approve` → lane receives `/start-task <packet_id>` tmux nudge + inbox message

**Evaluation questions to answer:**
1. Can Agent Teams' task system express scope-locked packets (every task has explicit file-pattern scope)?
2. Can it express domain routing (platform vs. browser-game pools)?
3. Can it express lane affinity (author-a remains author-a across sessions)?
4. How does dependency tracking work? Is it DAG-shaped? Same shape as TaskCreate/TaskUpdate with `addBlockedBy`?
5. Is there a way to persist packet routing metadata (`task_type`, `complexity_estimate`, `model_hint`, `effort_hint`)?
6. How does inter-agent messaging work? Does it replace the `ops/message_bus.py` durable-message semantics or run alongside?
7. Adoption decision: **adopt wholesale** (replace bespoke task system) / **cherry-pick dispatch-pattern + keep bespoke task_queue.py** / **reference only** / **reject — steward semantics don't fit**.

### Target 3 — `melodic-software/claude-code-observability`

**Source:** `https://github.com/melodic-software/claude-code-observability-plugins` (exact repo path may vary; search `claudepluginhub.com` listing: `https://www.claudepluginhub.com/plugins/melodic-software-claude-code-observability-plugins-claude-code-observability`).

**Context:** 14-event hook logging for audit trails; audit hook schemas for drift with fix options; JSONL query for session timelines, tool traces, agent lifecycles, team activity, stats, summaries.

**Steward overlap:**
- `src/bid_euchre/ops/events.py` — event schema (the subject of Primitive A's native-substrate absorption work)
- `src/bid_euchre/ops/audit_trail.py` — JSONL audit trail
- `src/bid_euchre/ops/monitor.py` — session timelines / tool traces
- §9.7 first-class IDs: `project_id`, `cell_id`, `session_id`, `task_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`, `schema_version`

**Evaluation questions to answer:**
1. What are the 14 events? List them.
2. Is the schema compatible with §9.7 first-class IDs? Specifically — does it carry `task_id`, `lane_id`, `prompt_policy_version`, `incident_fingerprint`, `schema_version`?
3. If steward-specific fields aren't native, is the schema extensible (plugin accepts additional fields) or forked-if-extended?
4. License (MIT / Apache / other)?
5. Maintenance posture (single maintainer / organizational; release cadence; open issues shape)?
6. What's the JSONL query capability? Does it provide the grep-style filtering steward's Primitive A Phase 1 Validation needs ("full experiment reconstructable from trace corpus alone")?
7. Adoption decision: **adopt wholesale** (replaces `ops/events.py` + parts of `audit_trail.py` + `monitor.py`) / **cherry-pick 14-event schema convention + keep bespoke implementation** / **reference only for schema design input** / **reject — schema incompatibility**.

### Target 4 — `doobidoo/mcp-memory-service`

**Source:** `https://github.com/doobidoo/mcp-memory-service`.

**Context:** "Open-source persistent memory for AI agent pipelines (LangGraph, CrewAI, AutoGen) and Claude. REST API + knowledge graph + autonomous consolidation."

**Steward overlap:**
- `src/bid_euchre/ops/memory.py` — per-worktree session memory
- MEMORY.md — cross-session rolling index
- Primitive C planned KB artifacts (NOTES.md / PLAYBOOKS.md / anti_patterns.md / incidents/ / adr/ / harness_assumptions.md / INDEX.md)
- Primitive D archivist script — candidate lessons + GC report outputs
- The "shared project memory across worktrees" Tier S adoption already committed in Primitive C

**Evaluation questions to answer:**
1. What is the MCP interface? What MCP tools does it expose (names + signatures)?
2. How does "autonomous consolidation" work? Is this substitutable for the archivist script's inflow-candidate-promotion pipeline?
3. How does the knowledge graph work? Is it domain-specific (i.e., assumes certain entities) or generic (accept arbitrary node types)?
4. How does persistence work — local file? External DB? Both?
5. License (MIT / Apache / other)?
6. Maintenance posture?
7. What's the data-migration path if steward adopts and later needs to eject (lock-in risk)?
8. Adoption decision: **adopt wholesale** (replaces `ops/memory.py` + parts of Primitive C/D scope) / **cherry-pick MCP interface pattern** / **reference only** / **reject — too heavy / incompatible**.

## 3. Deliverable format

`plans/steward_platform/plugin_source_evaluation.md` with:

### §1 Summary table

| Target | Adoption decision | Rationale one-liner | ADR destination |
|---|---|---|---|
| Official code-review plugin | [decision] | [1-sentence why] | ADR 005 |
| Agent Teams + TeammateTool | [decision] | [1-sentence why] | B.8 |
| melodic-software/claude-code-observability | [decision] | [1-sentence why] | ADR 007 |
| doobidoo/mcp-memory-service | [decision] | [1-sentence why] | ADR 010 |

### §2-§5 One section per target

- URL to actual source
- License + maintenance posture (1-2 lines each)
- Summary of what it actually does (not marketing — source-derived)
- Schema compatibility assessment (specific to §9.7 IDs where relevant)
- Steward-specific extensions required (list)
- Estimated integration effort (low/medium/high with reasoning)
- Adoption decision with explicit rationale + cited source snippets

### §6 ADR seeds

Short ADR-format text for each that can be lifted directly into draft 8's Phase 0 kickoff ADR files:
- Context
- Decision
- Consequences
- Alternatives considered

### §7 Open questions

Anything requiring operator disposition before the ADR can be finalized.

### §8 Phase 2 Decision Inputs

Standard subsection per §15.2 schema.

## 4. Scope boundaries

**In scope:**
- Read plugin source code directly (via `gh api` or `WebFetch`)
- Compare schema / interface / semantics against steward's §9.7 and existing ops-package shapes
- Produce adoption decisions and ADR seed text
- Flag license / maintenance-posture concerns

**Out of scope:**
- Installing or running the plugins locally (read-only source evaluation)
- Implementing any adapter shim or migration code
- Re-reviewing analyst-a/b/c/d findings on draft 7
- Challenging the fixed constraints (single-repo Phase 0/1; prove-before-port; goal #16 agent-first; etc.)

## 5. Mechanics

- **Write scope:** `plans/steward_platform/` for the evaluation artifact only.
- **Write under goal-#16 conventions.** Predictable §N.M structure; machine-parseable decision tables; grep-clean per-target IDs; loadable-with-minimal-preamble.
- **Time expectation:** 2-4 hours focused work. Bulk is source reading across four repos; synthesis is straightforward once reading is done.
- **Escalation:** if you find a blocker, message orchestrator with a concrete question.

## 6. What happens after you ship

Your artifact lands on main via a small PR (same pattern as analyst-a/b/c/d review PRs #2745/#2747/#2749/#2751). Orchestrator (working on draft 8 in parallel) folds your adoption decisions into the ADR seeds filed at Phase 0 kickoff, which land as a follow-up commit to the draft-8-promoted `governing_plan.md`. Your findings are not blocking draft 8 promotion; they sharpen Phase 0 execution.
