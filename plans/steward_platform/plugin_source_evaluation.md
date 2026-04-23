# Claude Code Native-Substrate Plugin Source Evaluation

**Date:** 2026-04-23
**Author:** steward-analyst (analyst-a)
**Handoff driving this artifact:** `plans/steward_platform/plugin_source_evaluation_handoff.md` (orchestrator, 2026-04-23)
**Companion references:** `plans/steward_platform/claude_code_changelog_implications.md` §2 Tier S inventory; `plans/steward_platform/governing_plan.draft7.md` §9.7 first-class IDs.
**Status:** Complete. Adoption decisions below are source-informed and ready to fold into Phase 0 kickoff ADR drafts (`plans/steward_platform/adrs/NNN-*.md`) and the B.8 evaluation row.

This artifact does not re-review draft 7, does not re-open fixed constraints, and does not recommend adoption of anything the platform has not proven a need for. It reads the actual source of four candidates named in the handoff and records adoption decisions with cited source snippets.

---

## 1. Summary table

| # | Target | Adoption decision | Rationale one-liner | ADR destination |
|---|---|---|---|---|
| 1 | Official `anthropics/claude-code/plugins/code-review` | **Cherry-pick multi-agent parallel pattern + fan-in validator pass; reject wholesale replacement** | Plugin's real architecture is 4 parallel reviewers + Nx validator subagents (not 5 specialized reviewers with 0-100 scoring as marketing summarizes); overlaps `review_driver.py` orchestration but does not carry steward's Codex-CLI verdict/merge-guard/scope-lock/autofix semantics. | **ADR 005** |
| 2 | Agent Teams + TeammateTool + native Task system | **Cherry-pick lifecycle hooks (already Tier S) + `SendMessage` mailbox as supplemental channel; reject replacement of `ops/task_queue.py`** | Native tasks are session-ephemeral with no scope-lock, no domain routing, no lane affinity, no `task_type`/`complexity_estimate`/`model_hint`/`effort_hint` metadata, and teams die with the lead session (§Limitations). Steward's durable packet semantics are not subsumed. | **B.8** |
| 3 | `melodic-software/claude-code-observability` | **Cherry-pick dispatcher pattern + JSONL schema conventions; extend native with steward §9.7 first-class IDs in `ops/events.py`; do NOT fork the plugin** | Plugin's 14-event schema is 80% of what Primitive A needs but carries none of §9.7's steward-specific IDs (`project_id`, `cell_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`). Cleaner to adopt pattern in bespoke code than fork. | **ADR 007** |
| 4 | `doobidoo/mcp-memory-service` | **Reject wholesale adoption; reference only for MCP interface design input. Re-evaluate at Phase 2 if KB grep-comprehension threshold is breached.** | Vector-DB semantic memory + "dream-inspired" autonomous consolidation conflicts with steward's explicit-promotion + git-as-source-of-truth discipline. Heavy dependency footprint (ChromaDB / SQLite-vec / Cloudflare) for a use case currently satisfied by curated markdown. | **ADR 010** |

---

## 2. Target 1 — Official code-review plugin (ADR 005)

### 2.1 Source

- Repo: `https://github.com/anthropics/claude-code` (monorepo)
- Plugin path: `plugins/code-review/`
- Entry files read (via `gh api`):
  - `.claude-plugin/plugin.json` (9 lines — name, description, version 1.0.0, author Boris Cherny)
  - `README.md` (258 lines — docs + marketing + troubleshooting)
  - `commands/code-review.md` (109 lines — **the actual orchestration prompt**)
- License: follows `anthropics/claude-code` repo license (MIT)
- Maintenance posture: First-party. Active. Single author attribution (Boris Cherny, Anthropic).

### 2.2 What it actually does (source-derived, not marketing)

The README describes "5 specialized reviewers with 0-100 confidence scoring (threshold 80 default)". The `commands/code-review.md` source tells a different story.

**Actual architecture from `commands/code-review.md`:**

1. **Haiku gate agent** — skips review if PR is closed, draft, trivial, or Claude already commented.
2. **Haiku path-collector agent** — returns list of relevant CLAUDE.md file paths.
3. **Sonnet summarizer agent** — returns PR change summary.
4. **4 parallel reviewers** (not 5, not "specialized by domain"):
   - Agents 1+2: **Two parallel Sonnet agents**, both doing CLAUDE.md compliance review. Redundancy, not specialization.
   - Agent 3: Opus bug agent — "Scan for obvious bugs. Focus only on the diff itself without reading extra context."
   - Agent 4: Opus bug agent — "Look for problems that exist in the introduced code. This could be security issues, incorrect logic, etc." Runs in parallel with agent 3. The README's claim of a "history analyzer / git blame" reviewer is absent from the command.
5. **Nx validator subagents** (not a 0-100 confidence score) — for each issue flagged by agents 3 and 4, a second subagent (Opus for bugs, Sonnet for CLAUDE.md) validates the issue in isolation with the PR title and description. Issues that fail validation are filtered.
6. **Final filter + comment step** — `--comment` flag gates whether to post inline comments via `mcp__github_inline_comment__create_inline_comment`.

**Source snippet** (`commands/code-review.md` step 5, line 55):

> "For each issue found in the previous step by agents 3 and 4, launch parallel subagents to validate the issue. These subagents should get the PR title and description along with a description of the issue. The agent's job is to review the issue to validate that the stated issue is truly an issue with high confidence."

**Interpretation.** The "confidence scoring" is a **two-pass flag→validate filter**, not a numeric 0-100 ensemble. The README's 0-100 scale and "threshold 80" framing is post-hoc documentation; the command file never references any numeric threshold. The real noise-suppression mechanism is the validator-subagent pass, implemented as "if you are not certain an issue is real, do not flag it. False positives erode trust and waste reviewer time."

### 2.3 Steward overlap

| Steward asset | Plugin overlap |
|---|---|
| `scripts/internal/review_driver.py` | Plugin does not replace driver. Driver's scope is: precheck → CI wait → Codex CLI → auto-fix → verdict + status publish → merge-guard bridge. Plugin only does steps analogous to "Codex CLI review" with a different orchestrator shape (4+Nx agents instead of 1 Codex call). |
| `/reviewing-changes` skill | Different contract — skill drives a deterministic review checklist (CHECKLIST.md C1/C2/N1/N2/...). Plugin outputs prose issues. |
| Merge guard + verdict JSON at `.claude/runtime/review_loops/pr_<N>/` | Not implemented by plugin. Plugin's "comment on PR" is not SHA-bound; no merge-relevance guarantees. |
| Scope lock (`ops/task_queue.py` + scope-drift guard) | Not implemented. Plugin has no notion of "the PR may only touch files in scope X". |
| Convention-pattern auto-fixes (precheck C1/C2/N1/N2) | Not implemented. Plugin posts comments; steward's driver auto-fixes and re-validates. |

### 2.4 Schema compatibility (§9.7 first-class IDs)

Not applicable. Plugin's outputs are GitHub comments, not events carrying §9.7 IDs. No schema-compat decision required.

### 2.5 Steward-specific extensions required if wholesale-adopted

Wholesale adoption would require retrofitting:

1. Codex-CLI reviewer as a 5th parallel agent (or the only reviewer, replacing agents 3/4).
2. SHA-bound verdict writing (currently absent).
3. Status-context publication to `reviewing-changes`.
4. Merge-guard integration (`pre-merge-review-guard.sh`).
5. Precheck pattern detection (C1/C2/X3 BLOCK patterns).
6. Auto-fix commit loop (plugin posts comments; steward commits + retests).
7. Scope-drift detection.
8. Follow-up issue creation for P2 findings.
9. Label taxonomy (`follow-up`, `fix:bug`, `fix:convention`, `fix:test`, `fix:docs`, `fix:process`).

That's essentially all of `review_driver.py`. Wholesale adoption is not lower-effort than the status quo.

### 2.6 Adoption decision: **Cherry-pick** the multi-agent parallel pattern + validator pass; reject wholesale replacement

**What to adopt:**

- **Multi-agent parallel review shape for `review_driver.py` round 0.** Today the driver runs a single Codex CLI call per round. Reviewing `commands/code-review.md`'s step 4 in detail suggests a worthwhile Phase-1+ experiment: run Codex CLI *plus* N parallel Opus subagent reviewers (different foci: "scan diff for bugs", "verify scope lock", "audit CLAUDE.md compliance"), then fan-in with a validator pass. This would be a `review_driver.py` extension, not an installation of the plugin.
- **Validator-subagent pattern for false-positive suppression.** Currently the driver's auto-fix logic accepts Codex findings at face value. Adding a validator-subagent pass ("given the PR title + description + the finding text, is this a real issue?") would reduce round 2+ noise that the 50-106 precheck false-positive pattern (handoff §2 Target 1 context) keeps surfacing.
- **Explicit "false positives filtered" list.** README §"False positives filtered" enumerates pre-existing issues, lint-catchable issues, pedantic nitpicks. Worth lifting into steward's `/reviewing-changes` CHECKLIST.md as a section.

**What not to adopt:**

- The plugin's 0-100 numeric confidence score (README marketing; not in source).
- Wholesale replacement of `review_driver.py`.
- The plugin's orchestration shell (the command file). Steward's orchestrator is a Python script that speaks GitHub API + Codex CLI + verdict JSON; swapping to a command-file orchestrator removes the deterministic surface.

### 2.7 Integration effort

- **Cherry-pick 2 patterns (parallel reviewers + validator pass) into `review_driver.py`:** Medium. ~150-300 lines of Python. Requires prompt engineering for the Opus subagent reviewers. Not Phase 0; defer to Primitive E post-closeout.
- **Lift "false positives filtered" list into CHECKLIST.md:** Low. Single-PR docs change.

### 2.8 Phase 2 Decision Inputs (per §15.2)

**Portability readiness:** No change. Plugin is a Claude-Code-only artifact; adoption does not move the needle on target-repo portability.
**Meta-layer need:** Modest. Adopting the validator-subagent pattern would nudge `review_driver.py` toward a more sophisticated orchestration surface that could justify a small internal framework abstraction at Phase 2 if similar patterns appear in the monitor/dispatch lanes.
**Kill signal for primitive(s) named:** No. Primitive E (review + merge discipline) remains live. ADR 005 sharpens the boundary rather than killing scope.
**Re-evaluation needed in Phase 3:** No. Adopt-or-skip decision is available now with the source read.
**Surprise finding:** The README's "0-100 confidence scoring" framing is post-hoc documentation, not reflected in the command source. The real suppression mechanism is the validator-subagent pass. This matters because draft 7's casual reference to "confidence scoring" should be amended to "validator-subagent filter pass" in the ADR 005 context block.
**Disposition:** open

---

## 3. Target 2 — Agent Teams + TeammateTool + native Task system (B.8)

### 3.1 Source

- Primary doc: `https://code.claude.com/docs/en/agent-teams` (read via WebFetch).
- Team config schema: `~/.claude/teams/{team-name}/config.json` (per docs — runtime-generated; operator should NOT hand-edit).
- Task list storage: `~/.claude/tasks/{team-name}/` (per docs).
- Behind experimental flag: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json or env.
- Requires Claude Code v2.1.32+.
- Coordination tools always available to teammates regardless of subagent `tools` allowlist: `SendMessage` (one-to-one), broadcast, and the task management tools (TaskCreate/TaskUpdate/TaskList).

### 3.2 What it actually does (spec-derived)

**Architecture** (docs §Architecture):

| Component | Role |
|---|---|
| Team lead | Main session that creates the team, spawns teammates, coordinates work |
| Teammates | Separate Claude Code instances, each with own context window |
| Task list | Shared list of work items teammates claim/complete |
| Mailbox | `SendMessage` (one-to-one) + `broadcast` (all teammates) |

**Task state machine:** pending → in_progress → completed. Dependencies expressible ("a pending task with unresolved dependencies cannot be claimed until those dependencies are completed"). Task claiming uses file-locking to prevent race conditions.

**Display modes:** in-process (all teammates share terminal; Shift+Down cycles) or split panes (tmux / iTerm2). Config key `teammateMode` in `~/.claude.json` or `--teammate-mode` flag.

**Subagent definitions reused as teammate roles:** A teammate spawned with `agent_type: security-reviewer` inherits the subagent's `tools` allowlist and `model`; its body appends to the teammate's system prompt. **But `skills` and `mcpServers` from subagent frontmatter are NOT inherited** — teammates load skills/MCP servers from project+user settings.

**Permissions:** Teammates inherit the lead's permission mode at spawn. Per-teammate permissions can be changed after spawn but not at spawn time.

**Lifecycle hooks available:**
- `TeammateIdle` — exit 2 to keep teammate working.
- `TaskCreated` — exit 2 to block creation + send feedback.
- `TaskCompleted` — exit 2 to block completion + send feedback.

### 3.3 Steward overlap — the key comparisons

**Does Agent Teams' task system express scope-locked packets?**
**No.** Task has no field for `scope_declared: List[str]`. Docs explicitly say "Two teammates editing the same file leads to overwrites. Break the work so each teammate owns a different set of files." That's exactly the hazard steward's scope-lock + `audit_portability.py` scope-drift guard prevents, and Agent Teams provides no native safeguard.

**Does it express domain routing (platform vs. browser-game lane pools)?**
**No.** Teams are flat. A single lead spawns teammates; docs §Limitations: "One team per session. No nested teams." No native pool concept.

**Does it express lane affinity across sessions?**
**No.** Docs §Limitations: "No session resumption with in-process teammates. `/resume` and `/rewind` do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist." Steward's `author-a`/`author-b`/`analyst-*` lanes persist across session restarts via worktree + message-bus durable state. Agent Teams does not.

**Dependency tracking shape?**
**DAG, same shape as `TaskCreate` + `addBlockedBy` semantics.** A pending task cannot be claimed while any of its blocking tasks are unresolved. This part IS substitutable for `ops/task_queue.py` intra-session dependency tracking, but only for intra-session work.

**Routing metadata (`task_type`, `complexity_estimate`, `model_hint`, `effort_hint`)?**
**Not first-class.** The team config and task objects are documented as runtime-generated JSON the operator should not hand-edit. No schema field for steward's dispatch metadata. Any steward adoption would have to shoehorn these into task title/description strings or a non-standard sidecar file — both are fragile.

**Inter-agent messaging shape vs. `ops/message_bus.py`?**
- Agent Teams: `SendMessage` (one-to-one), `broadcast`, delivered automatically without polling. Session-ephemeral.
- Steward bus: durable messages with expiration, read/expired reconciliation, inbox ack cycle, message types (ack / task_received / completion / blocker / progress), priority, cross-session replay. Persistent across restarts.

Agent Teams' mailbox is **strictly a subset** of steward's bus — fine for lead↔teammate pings within a session, but does not carry durability guarantees the multi-session orchestrator/author handoff relies on.

### 3.4 Schema compatibility (§9.7)

Partial. Agent Teams provides `agent_id`, `agent_type`, `parent_agent_id` in `SubagentStart` / `SubagentStop` hook inputs (see observability plugin §4.2). These map loosely to `lane_id` but are session-local identifiers, not the stable cross-session `author-a` / `analyst-b` / `brws-author-c` names steward uses. Integration would require a lookup table.

### 3.5 Steward-specific extensions required if adopted for packet dispatch

Full adoption of Agent Teams as packet dispatch substrate would require:

1. A `scope_declared` extension field on task objects (not supported; would have to live in description prose).
2. A domain-routing layer on top (teams can't span pools).
3. A lane-affinity layer (teams die with the lead).
4. Durable-across-restart task state (task files live at `~/.claude/tasks/{team-name}/` but tasks reset when the team is cleaned up).
5. Routing metadata sidecar.
6. `SendMessage`-to-bus bridge (or dual-writes to keep bus as durable source-of-truth).

The extensions are substantial enough that "keep bespoke `ops/task_queue.py`" is cheaper than "adopt Agent Teams + build 6 extensions".

### 3.6 Adoption decision: **Cherry-pick** lifecycle hooks + mailbox as supplemental channel; keep `ops/task_queue.py` bespoke

**What to adopt (already in Tier S per `claude_code_changelog_implications.md` §2):**

- `TeammateIdle`, `TaskCreated`, `TaskCompleted` hook events — these are native emitters Primitive A's schema should absorb regardless of B.8 verdict, so they don't depend on this decision.
- `SendMessage` + `broadcast` as a **supplemental** intra-session channel for lead↔author-lane coordination pings. Not a replacement for `ops/message_bus.py`; steward's durable bus stays authoritative. Use case: orchestrator pings a specific author lane mid-task to surface a blocker without going through the full packet-dispatch loop.

**What not to adopt:**

- Replacement of `ops/task_queue.py`. Steward's packet contract (scope-locked, domain-routed, lane-affined, metadata-rich, durable-across-restart) is not expressible in native Agent Teams tasks.
- Replacement of `ops/worker_pool.py`'s round-robin / explicit-lane targeting. Teams are flat, cannot express pools.
- Replacement of the orchestrator→author-lane nudge protocol. The `/start-task <packet_id>` + inbox message + tmux send-keys pattern predates and outperforms Agent Teams' mailbox for the durability-across-restart use case.

### 3.7 Integration effort

- **Adopt `TeammateIdle` / `TaskCreated` / `TaskCompleted` into `ops/events.py` schema:** Low-to-medium. ~2 PR's worth (already on Tier S list).
- **Add `SendMessage`-as-supplemental-channel bridge:** Medium. Opt-in. Phase-1+ consideration if a concrete use case emerges; not a Phase 0 blocker.

### 3.8 Phase 2 Decision Inputs (per §15.2)

**Portability readiness:** No change. B.8 is a Claude-Code-substrate binding decision; not a portability lever.
**Meta-layer need:** No change. Bespoke packet contract stays; no new abstraction needed.
**Kill signal for primitive(s) named:** No. Primitive B (adaptive dispatch + skill improvement + prompt-policy) remains live; B.8 narrows scope in exactly the way draft 7 already framed ("mostly stays bespoke").
**Re-evaluation needed in Phase 3:** Possibly. If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` graduates from experimental and the task schema gains scope/metadata fields, revisit. Recommended evaluation window: 6 months post Phase 2 close, or when the flag ceases to be experimental, whichever sooner.
**Surprise finding:** Agent Teams' docs explicitly acknowledge the file-conflict hazard (§Best Practices "Avoid file conflicts") and offer no runtime guard. This validates draft 7's scope-lock discipline as an **orthogonal contribution** worth preserving independent of native substrate evolution.
**Disposition:** open

---

## 4. Target 3 — `melodic-software/claude-code-observability` plugin (ADR 007)

### 4.1 Source

- Repo: `https://github.com/melodic-software/claude-code-plugins` (a plugin monorepo; the observability plugin is at `plugins/claude-code-observability/`).
- Note on handoff URL: the handoff referenced `melodic-software/claude-code-observability-plugins` which 404s; the correct path is inside the monorepo linked above.
- License: **MIT** (both the repo LICENSE and the plugin's declared license in `.claude-plugin/plugin.json`).
- Stars: 1717 on the repo (many plugins share that total; the observability plugin is one of ~35).
- Last pushed: 2026-04-07 (pushed 2026-04-22 — actively maintained).
- Maintenance posture: Single-org, many-plugin monorepo. Observability plugin is self-contained (dispatcher + hooks.json + 2 skills). Schema version `SCHEMA_VERSION = "1.9.0"` (dispatcher source line 58) indicates the author evolves the schema with versioning discipline.

### 4.2 The 14 events (source-derived)

From `hooks/hooks.json` and `hook_dispatcher.py` `EVENT_FIELD_REGISTRY`:

| # | Event | Event-specific fields (beyond `_common`) |
|---|---|---|
| 1 | `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id` |
| 2 | `PermissionRequest` | `tool_name`, `tool_input`, `permission_suggestions` |
| 3 | `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id` |
| 4 | `PostToolUseFailure` | `tool_name`, `tool_input`, `tool_use_id`, `error`, `is_interrupt` |
| 5 | `Notification` | `message`, `title`, `notification_type` |
| 6 | `UserPromptSubmit` | `prompt` |
| 7 | `Stop` | `stop_hook_active` |
| 8 | `SubagentStart` | `agent_id`, `agent_type`, `parent_agent_id` |
| 9 | `SubagentStop` | `stop_hook_active`, `agent_id`, `agent_type`, `agent_transcript_path`, `parent_agent_id` |
| 10 | `PreCompact` | `trigger`, `custom_instructions` |
| 11 | `SessionStart` | `source`, `model`, `agent_type` |
| 12 | `SessionEnd` | `reason` |
| 13 | `TeammateIdle` | `teammate_name`, `team_name` |
| 14 | `TaskCompleted` | `task_id`, `task_subject`, `task_description`, `teammate_name`, `team_name` |

**Common fields** (`_common`): `session_id`, `transcript_path`, `cwd`, `permission_mode`, `seq`, `pid`, `timestamp_ns`.

**Correlation fields** (dispatcher + README §Correlation Fields):
- `seq` — monotonic counter per log directory (locked `.seq` file).
- `pid` — writer process ID.
- `timestamp_ns` — `time.time_ns()` nanosecond epoch.
- `turn_id` — conversation turn counter (`.turn` file, incremented on `userpromptsubmit`).

**Verbosity modes:** `minimal` (~200 B, timestamp+event+session+tool+duration) / `summary` (~500 B, adds event-specific fields with large-field summarization) / `full` (1-50 KB, raw input + env context).

**Extensibility:** `extra_fields` bucket captures unknown input fields automatically (dispatcher line 298: "Capture unknown fields for future-proofing"). Steward-specific fields injected upstream into hook input would flow through to `extra_fields` without plugin modification.

**Non-blocking semantics:** All hooks `"async": true` (hooks.json); dispatcher "Never block Claude Code - all exceptions caught, always exit 0". Cross-platform (pathlib, conditional `fcntl`/`msvcrt` locking).

### 4.3 Schema compatibility with §9.7 first-class IDs

| §9.7 ID | Plugin schema | Verdict |
|---|---|---|
| `project_id` | Absent. `CLAUDE_PROJECT_DIR` present only in `full` verbosity's `environment` block. | **Missing** — needs promotion to top-level. |
| `cell_id` | Absent. | **Missing** — pipeline-cell concept is steward-specific. |
| `session_id` | Present (`_common`), falls back to `CLAUDE_SESSION_ID` env. | **Compatible**. |
| `task_id` | Present **only in `TaskCompleted` event** via EVENT_FIELD_REGISTRY. Not cross-event. | **Partial** — needs cross-event propagation for steward packet correlation. |
| `lane_id` | Absent. `agent_type` in `SessionStart` / `SubagentStart` is close but is session-local. | **Missing** — steward lane names don't map cleanly to `agent_type` / `agent_id`. |
| `trace_id` | Absent. `turn_id` is the closest analog but scoped to one session. | **Missing**. |
| `incident_fingerprint` | Absent. | **Missing**. |
| `prompt_policy_version` | Absent. | **Missing** — would need injection from steward B.3 registry. |
| `schema_version` | Present as `_v: "1.9.0"` on every entry. | **Compatible pattern**, different value — steward would own its own `schema_version` per §4.1 Primitive A. |

Five of nine §9.7 IDs are missing; two more are partial. The plugin's schema is 80% of Primitive A by event-class coverage, but 40% by first-class-ID coverage.

### 4.4 Steward-specific extensions required

Two adoption paths:

**Path A — Fork the plugin.** Add fields to `EVENT_FIELD_REGISTRY`, extend `_build_summary_entry` / `_build_full_entry` to emit steward IDs, re-maintain across upstream schema bumps (`SCHEMA_VERSION` ticked on each registry change). Maintenance cost: re-reconcile on every upstream schema change. Not recommended.

**Path B — Adopt the dispatcher pattern in `ops/events.py`.** Implement in steward's own codebase (Python stdlib only, same async + never-block + pathlib + fcntl-locking pattern), with §9.7 IDs native. Costs: ~1000-line module (dispatcher source is 1068 lines), plus hook config in `.claude/settings.json`. Benefits: no fork maintenance; §9.7 IDs are first-class, not `extra_fields` bucket; rotation/retention/compression polices tunable. Recommended.

### 4.5 `log-inspection` and `hook-schema-audit` skills

The plugin ships two skills at `skills/log-inspection/` and `skills/hook-schema-audit/` (not read in detail for this evaluation; directory listing confirmed their presence). Worth a later targeted read before Primitive A Phase 1 validation ships — the hook-schema-audit skill likely implements the schema-drift validation steward needs under §4.2 Primitive A Phase 0 Readiness ("Event schema finalized; committed"). File follow-up issue after this PR lands.

### 4.6 Adoption decision: **Cherry-pick dispatcher pattern + JSONL schema conventions; do NOT fork**

**What to adopt (into `ops/events.py`):**

- Single-entry-point dispatcher pattern (one `hook_dispatcher.py`-analog handles all 14 events).
- JSONL-per-day file layout with rotation via `events-{YYYY-MM-DD}-NNN.jsonl` naming.
- Correlation fields: `seq`, `pid`, `timestamp_ns`, `turn_id`. Already implicitly needed for Primitive A's "full experiment reconstructable from trace corpus alone" validation; source this pattern here.
- Verbosity levels (`minimal` / `summary` / `full`) with env-var control — matches Tier F (token economy) cost-discipline framing.
- `extra_fields` bucket for future-proofing unknown fields.
- File-locking pattern for cross-process ordering (`fcntl.flock` on Unix, `msvcrt.locking` on Windows — though steward is macOS-only, keep the pattern for portability discipline per goal #8).
- `_categorize_error` pattern (`interrupted` / `timeout` / `permission_denied` / `execution_error`) — matches steward's existing incident-fingerprint taxonomy.
- `_build_status_message` pattern for async-hook system messages.

**What not to adopt:**

- The plugin itself as an installed dependency — schema lacks §9.7 IDs, and forking incurs upstream-drift maintenance cost.
- Environment variable names prefixed `CLAUDE_HOOK_LOG_*` — use steward-namespaced `STEWARD_EVENTS_*` to avoid conflict if operator later installs the plugin for comparison.

### 4.7 Integration effort

- **Write steward `ops/events.py` using plugin pattern + §9.7 fields native:** Medium. ~1000 Python lines, extensive tests, schema finalization per Primitive A Phase 0 Readiness bullet. This is existing Primitive A scope; ADR 007 sharpens the *implementation pattern*, not the scope.
- **Follow-up: read `skills/log-inspection/` and `skills/hook-schema-audit/` before Phase 1 validation.** Low, single-session task.

### 4.8 Phase 2 Decision Inputs (per §15.2)

**Portability readiness:** Modestly improved. Adopting the dispatcher pattern with a clean Python-stdlib-only implementation (no ChromaDB, no framework imports) makes `ops/events.py` a natural extraction candidate for other Claude Code fleets.
**Meta-layer need:** No change. Dispatcher is a single file; no meta-framework implied.
**Kill signal for primitive(s) named:** No. ADR 007 is implementation guidance, not a kill candidate for Primitive A.
**Re-evaluation needed in Phase 3:** No. Decision is available now.
**Surprise finding:** The plugin's `extra_fields` bucket + `_v` schema-version pattern is a clean additive-extension model steward should adopt for event schema evolution (§4.2 `schema_version`: "v1.N and remain replay-compatible"). Specifically, the combination "known fields in registry, unknown fields in `extra_fields`, version bump on registry change" is a pattern worth lifting verbatim into Primitive A's schema discipline.
**Disposition:** open

---

## 5. Target 4 — `doobidoo/mcp-memory-service` (ADR 010)

### 5.1 Source

- Repo: `https://github.com/doobidoo/mcp-memory-service` (exists and matches handoff URL).
- License: **Apache-2.0**.
- Stars: 1717; Forks: 260; Open issues: 8; Last pushed 2026-04-22 (actively maintained).
- Version: `10.13.0` (per `src/mcp_memory_service/__init__.py`).
- Structure: `src/mcp_memory_service/` with modules `api/`, `backup/`, `cli/`, `consolidation/`, `discovery/`, `embeddings/`, `harvest/`, `health/`, `ingestion/`, `quality/`, `reasoning/`, `server/`, `services/`, `storage/`, `sync/`, `web/`, plus top-level `mcp_server.py` (27 KB) and `server_impl.py` (**152 KB** — the core implementation).
- Storage backends: `sqlite_vec.py` (192 KB), `cloudflare.py` (90 KB), `hybrid.py` (90 KB), `milvus.py` (68 KB), `graph.py` (27 KB), `http_client.py` (19 KB). Pluggable via `factory.py`.

### 5.2 MCP interface (tool names + signatures)

From `mcp_server.py` (seven `@mcp.tool` decorators read in detail; more exist in `server_impl.py`):

| Tool | Signature (abbreviated) | Annotations |
|---|---|---|
| `store_memory` | `(content: str, tags=None, memory_type="note", metadata=None, client_hostname=None)` | `destructiveHint=False` |
| `retrieve_memory` | `(query: str, n_results: int = 5)` | `readOnlyHint=True` (semantic vector search) |
| `search_by_tag` | `(tags: Union[str, List[str]], match_all: bool = False)` | `readOnlyHint=True` |
| `delete_memory` | `(content_hash: str)` | `destructiveHint=True` |
| `check_database_health` | `()` | `readOnlyHint=True` |
| `list_memories` | `(page=1, page_size=10, tag=None, memory_type=None)` | `readOnlyHint=True` |
| `get_cache_stats` | `()` | `readOnlyHint=True` |

Plus (per module layout, not read line-by-line): `exact_match_retrieve`, `recall_memory` (time-based), `delete_by_tag` / `delete_by_tags` / `delete_by_all_tags`, `delete_by_timeframe`, `delete_before_date`, `cleanup_duplicates`.

**Memory model:** content + tags + `memory_type` + metadata dict + `content_hash` (auto-computed). Semantic similarity via embedding models (embeddings module). Tags and memory_type are first-class organizing primitives.

**Content limits:** Cloudflare / Hybrid backends: 800 chars with auto-chunking at natural boundaries + 50-char overlap. SQLite-vec: no limit.

### 5.3 Autonomous consolidation (the "dream-inspired" mechanism)

From `consolidation/__init__.py`:

> "Dream-inspired memory consolidation system. This module implements autonomous memory consolidation inspired by human cognitive processes during sleep cycles, featuring exponential decay scoring, creative association discovery, semantic compression, and controlled forgetting."

Modules:

- `ExponentialDecayCalculator` (decay.py, 12 KB) — per-memory importance decay over time.
- `CreativeAssociationEngine` (associations.py, 15 KB) — discovers associations between memories.
- `SemanticClusteringEngine` (clustering.py, 16 KB) — groups semantically similar memories.
- `SemanticCompressionEngine` (compression.py, 21 KB) — compresses clusters into summary entries.
- `ControlledForgettingEngine` (forgetting.py, 26 KB) — deletes low-importance memories after configurable window.
- `DreamInspiredConsolidator` (consolidator.py, 41 KB) — orchestrates the above.
- `ConsolidationScheduler` (scheduler.py, 18 KB) — periodic background runs.
- `ConsolidationHealthMonitor` (health.py, 22 KB) — monitors consolidation performance.

**Semantics.** The consolidator autonomously mutates memory state: compresses clusters, forgets low-score entries, adds associations. The scheduler runs this on its own schedule without operator review.

### 5.4 Knowledge graph

`storage/graph.py` (27 KB) + `relationship_inference.py` (27 KB in consolidation/) implement a knowledge graph over memory entries. Graph is generic (nodes = memories, edges = inferred associations), not domain-typed. Not equivalent to steward's curated ADR→incident→playbook cross-references, which are human-authored links in markdown.

### 5.5 Persistence

- **Local SQLite** (default, via `sqlite_vec.py`).
- **Cloudflare KV + Vectorize** (optional, via `cloudflare.py`).
- **Hybrid** (local primary + Cloudflare sync, via `hybrid.py`).
- **Milvus** (external vector DB, via `milvus.py`).

None of these write to git-committed markdown files. The memory corpus lives **outside the repo** (per-machine SQLite or cloud), which conflicts with steward's `rules/deferred/30_data_contract.md` commit policy (only promoted artifacts committed) and with the draft 7 KB structure (`knowledge/NOTES.md`, `PLAYBOOKS.md`, etc. are committed markdown).

### 5.6 Schema compatibility with §9.7

| §9.7 ID | mcp-memory-service equivalent | Verdict |
|---|---|---|
| `content_hash` (not in §9.7 but notable) | First-class; primary key. | n/a |
| `project_id` | Absent as first-class; could live in `metadata` dict. | **Missing first-class slot.** |
| `cell_id` | Absent. | **Missing.** |
| `session_id` | Absent as first-class; could live in `metadata`. | **Missing first-class slot.** |
| `task_id` | Absent. | **Missing.** |
| `lane_id` | Absent. | **Missing.** |
| `trace_id` | Absent. | **Missing.** |
| `incident_fingerprint` | Absent (the plugin uses `content_hash` as its own fingerprint concept, different semantics). | **Missing.** |
| `prompt_policy_version` | Absent. | **Missing.** |
| `schema_version` | Memory class versioned via package `__version__` (`10.13.0`); no per-entry schema_version. | **Pattern mismatch.** |

All §9.7 IDs are absent as first-class fields. Would have to live inside `metadata: Optional[Dict[str, Any]]`, which makes them non-queryable except via full-scan — defeats the point of §9.7's "first-class IDs carried in every event" framing.

The impedance is deeper than the ID mapping. The plugin models memory as "content + tags + semantic embedding"; steward models knowledge as "curated artifact classes (NOTES / PLAYBOOKS / anti_patterns / incidents / ADRs / harness_assumptions / INDEX)" with explicit operator-gated promotion. These are different epistemic models — one is "retrieve whatever is similar to this query", the other is "read the canonical artifact for this class". Shoehorning the latter into the former loses the artifact-class discipline.

### 5.7 Lock-in and migration risk

Migration off mcp-memory-service would require:

1. Dump all SQLite entries to structured text.
2. Decide how to re-classify entries into steward artifact classes (NOTES vs. PLAYBOOK vs. incident vs. anti-pattern vs. ADR).
3. Rebuild any relationship-graph edges that the plugin inferred autonomously (not easily reproducible).
4. Re-embed under a replacement retrieval system if semantic search is still needed.

The "content_hash keyed + vector-embedded + consolidator-mutated" model is moderately path-dependent. Not extreme lock-in (Apache-2.0 + documented schema), but re-classification is manual and slow.

### 5.8 Steward-specific extensions required if wholesale-adopted

1. Extensions to all MCP tool signatures for §9.7 IDs as first-class (not metadata-dict).
2. Disable `ControlledForgettingEngine` — steward's commit discipline prohibits silent deletion.
3. Disable `SemanticCompressionEngine` — steward's commit discipline prohibits silent mutation.
4. Bridge to git: every `store_memory` call that meets a "promote to committed artifact" gate writes to `knowledge/*.md` and commits.
5. Gate `retrieve_memory` / `search_by_tag` against artifact-class taxonomy so callers distinguish "search across NOTES" vs. "search across PLAYBOOKS".
6. Operator-review gate on consolidation runs (scheduler would have to halt for operator disposition).

Items 2-6 are substantial enough that the adoption cost approaches writing a new system. The plugin's value is the semantic retrieval layer; everything else would be disabled or bridged.

### 5.9 Adoption decision: **Reject wholesale adoption; reference only for MCP interface design input**

**What to adopt (reference):**

- The MCP tool-signature pattern (`store_memory` / `retrieve_memory` / `search_by_tag` / `list_memories` / `delete_memory`) is a clean API shape. If steward later exposes its own MCP interface over the committed KB markdown (unlikely until Phase 2+), this shape is a reasonable starting point.
- The `tags` + `memory_type` + `metadata` field schema is well-considered. If steward's `knowledge/INDEX.md` auto-generation (Primitive C Phase 0 Readiness bullet) ever gains structured metadata, use this shape.
- `destructiveHint` / `readOnlyHint` MCP tool annotations — adopt the convention.

**What to reject:**

- Wholesale replacement of `ops/memory.py` or `knowledge/` markdown artifacts.
- Vector-DB dependency (SQLite-vec / ChromaDB / Milvus / Cloudflare). None are justified by a current steward workflow; adding one solves no proven problem.
- The autonomous-consolidation mechanism. Steward's archivist flow (Primitive D) is explicitly operator-gated via inflow candidate file promotion. Dream-inspired consolidation would silently mutate state outside git — incompatible with draft 7 §9-related commit discipline.
- The knowledge graph. Steward's cross-references (ADR ↔ incident ↔ playbook) are human-authored, not inferred.

### 5.10 Integration effort

- **Reject path (chosen):** Zero effort beyond filing ADR 010.
- **Adopt path (rejected for reference):** High. Substantial extensions listed in §5.8 would bring effort into multi-week range, with significant lock-in.

### 5.11 Phase 2 Decision Inputs (per §15.2)

**Portability readiness:** No change. Rejection keeps `ops/memory.py` + `knowledge/` markdown as the portable pattern.
**Meta-layer need:** No change. Bespoke curated-markdown model stays.
**Kill signal for primitive(s) named:** No. Primitive C (durable memory + KB) remains live; ADR 010 closes a named evaluation without reshaping scope.
**Re-evaluation needed in Phase 3:** **Yes, soft trigger.** Re-evaluate at Phase 3 **if either of the following fires during Phase 1 / 2**: (a) `knowledge/NOTES.md` exceeds a size where grep-based recall breaks agent-readability (soft threshold: ~20 KB or ~500 entries, whichever first); (b) archivist inflow volume exceeds operator-review capacity (≥10 candidate lessons per nightly run sustained for ≥1 week). Recommended evaluation window: 6 months post Phase 2 close.
**Surprise finding:** The plugin's storage layer is larger than the rest of the plugin combined (192 KB `sqlite_vec.py` vs. 27 KB `graph.py` + 152 KB `server_impl.py`). Most of the cost is in the backend and embeddings, not the MCP interface. If steward ever did need semantic retrieval, it would be cheaper to stand up a thin `sentence-transformers + SQLite-vec` wrapper over the committed markdown corpus than to adopt this plugin.
**Disposition:** open

---

## 6. ADR seeds (for Phase 0 kickoff ADR files)

The following four ADR-shaped drafts are written to be lifted (with light editing) into `plans/steward_platform/adrs/NNN-*.md` at Phase 0 kickoff per draft 7 §4.2 Primitive C Work ("ADR 001 … is filed at Phase 0 kickoff", and the B.8 / ADR 005 / ADR 007 / ADR 010 evaluations named in draft 7).

### 6.1 ADR 005 — Review plugin evaluation

**Context.** Anthropic's official `anthropics/claude-code/plugins/code-review` overlaps steward's `scripts/internal/review_driver.py`. Draft 7 commits to an ADR-level evaluation. Source read (2026-04-23 by analyst-a) shows the plugin is a 4-parallel-reviewer + Nx-validator-subagent orchestration in ~109 lines of command prompt, not the "5 specialized reviewers with 0-100 confidence scoring" marketing framing. Plugin has no SHA-bound verdict, no merge-guard, no scope-lock, no auto-fix commit loop, no status-context publication — steward's `review_driver.py` carries all of these.

**Decision.** Retain `review_driver.py` as the sole review orchestrator. Cherry-pick two patterns into it (as a Phase-1+ improvement, not a Phase-0 blocker):
1. Parallel-reviewer fan-out with Codex CLI + N Opus subagent reviewers on different foci.
2. Validator-subagent pass for false-positive suppression before writing findings.

Do not install the plugin.

**Consequences.** `review_driver.py` gains an optional multi-reviewer mode (feature-flagged, rollback via flag flip). Steward's single-Codex-CLI default remains the Phase 0 baseline. Draft 7 language around "0-100 confidence scoring" should be amended to "validator-subagent filter pass" since the former is post-hoc documentation, not source behavior.

**Alternatives considered.**
- Install the plugin and delete `review_driver.py`. Rejected — plugin does not carry SHA-bound verdicts, merge-guard integration, auto-fix commit loop, scope-lock, or status-context publication; retrofitting all six is more work than the status quo.
- Leave `review_driver.py` unchanged. Rejected — the validator-subagent pass is a clean noise-reduction win worth implementing.

### 6.2 B.8 — Native task/dependency system evaluation

**Context.** Claude Code `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` provides a team lead + teammates + shared task list + mailbox architecture. Draft 7 B.8 commits to an ADR stating which parts of steward's `ops/task_queue.py` contract are subsumed. Source read (2026-04-23, via docs at `code.claude.com/docs/en/agent-teams`) shows: native tasks have no `scope_declared`, no domain routing, no lane affinity, no `task_type` / `complexity_estimate` / `model_hint` / `effort_hint` metadata, and teammates die with the lead session (no session resumption per experimental limitations).

**Decision.** Keep `ops/task_queue.py`, `ops/worker_pool.py`, `ops/scheduler.py`, and the orchestrator→author-lane nudge protocol bespoke. Adopt the following from Agent Teams as supplemental, not replacement:
1. Lifecycle hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) into `ops/events.py` schema — already in Tier S.
2. `SendMessage` + `broadcast` as **supplemental intra-session channel** for orchestrator↔lane coordination pings. Steward message bus remains authoritative for durable/cross-restart semantics.

Do not enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` for steward lanes. (Retainable decision: operator may enable per-lane for experimentation; it does not compete with the bus.)

**Consequences.** Steward's task contract survives unchanged. The scope-lock discipline remains orthogonal to any native task primitive, preserving its value independent of substrate evolution. The §9.7 first-class IDs remain expressible on steward packets; `agent_id` / `agent_type` from Agent Teams hooks can be correlated via a lookup table if needed.

**Alternatives considered.**
- Adopt Agent Teams as packet-dispatch substrate. Rejected — would require building 6 extensions (scope field, domain routing, lane affinity, durable state, routing metadata, bus bridge) atop native, which is more work than keeping bespoke.
- Replace message bus with `SendMessage`. Rejected — session-ephemeral; loses cross-restart durability.

### 6.3 ADR 007 — Observability plugin evaluation

**Context.** `melodic-software/claude-code-observability` (MIT, v1.0.0, schema v1.9.0, actively maintained) implements a single-Python-dispatcher + 14-event JSONL logger with verbosity tiers, rotation, seq/pid/turn_id correlation, and `extra_fields` extensibility. Source read (2026-04-23) shows 80% of Primitive A's event-class coverage but only 40% of §9.7 first-class-ID coverage (session_id + schema_version pattern only; project_id / cell_id / task_id cross-event / lane_id / trace_id / incident_fingerprint / prompt_policy_version absent).

**Decision.** Implement steward's `ops/events.py` per Primitive A §4.2 Work using the plugin's dispatcher pattern as the reference implementation, with §9.7 IDs native to the top-level schema (not `extra_fields`). Do not fork the plugin. Adopt: single-dispatcher architecture, JSONL daily files with rotation, correlation fields (`seq`, `pid`, `timestamp_ns`, `turn_id`), verbosity tiers (`minimal` / `summary` / `full`), registry-driven known fields with `extra_fields` future-proofing, cross-platform file locking, `_categorize_error` taxonomy, `_build_status_message` pattern.

**Consequences.** Primitive A's Phase 0 Readiness ("Event schema finalized; committed") is implemented via a known, proven pattern. `ops/events.py` becomes a natural candidate for cross-fleet extraction (goal #8 portability). Steward owns its own `schema_version` bump policy per §4.2 ("v1.N and remain replay-compatible").

**Alternatives considered.**
- Install the plugin + inject `extra_fields`. Rejected — §9.7 IDs as non-first-class break queryability; forking incurs upstream-drift maintenance.
- Write from scratch without pattern reference. Rejected — plugin's dispatcher design is well-considered (never-block, async, pathlib-portable, stdlib-only); re-deriving is wasteful.

### 6.4 ADR 010 — mcp-memory-service evaluation

**Context.** `doobidoo/mcp-memory-service` (Apache-2.0, v10.13.0, 1717 stars) provides MCP tools for semantic memory (`store_memory` / `retrieve_memory` / etc.), plus autonomous "dream-inspired" consolidation (exponential decay, creative associations, semantic compression, controlled forgetting) and pluggable storage (SQLite-vec / Cloudflare / Milvus / Hybrid). Source read (2026-04-23) shows all §9.7 first-class IDs absent; storage lives outside git; autonomous consolidation silently mutates memory state.

**Decision.** Do not adopt. Keep `ops/memory.py` + `knowledge/` curated markdown + MEMORY.md + archivist operator-gated promotion as the Primitive C/D mechanism. Reference the plugin's MCP tool signatures only — if steward later exposes an MCP interface over the committed KB corpus, reuse the shape.

**Consequences.** Steward's commit discipline (only promoted artifacts committed; operator review before promotion) remains intact. No vector-DB dependency introduced. KB stays git-auditable and portable. Soft re-evaluation trigger: revisit at Phase 3 if `knowledge/NOTES.md` exceeds ~20 KB / 500 entries or archivist inflow exceeds operator-review capacity sustained for ≥1 week.

**Alternatives considered.**
- Wholesale adoption as replacement for `ops/memory.py`. Rejected — autonomous consolidation conflicts with commit discipline; heavy dependency footprint; lock-in via content-hash + embedding storage.
- Adopt as supplemental inflow-only layer. Deferred — no current workflow requires semantic retrieval; re-evaluate at Phase 3 trigger.

---

## 7. Open questions (require operator disposition before ADR finalization)

Each item is scoped to require one operator decision; analyst-a will not pre-resolve.

1. **Should ADR 005's "validator-subagent pass" cherry-pick ship during Phase 0, or strictly Phase 1+?** It is not a Phase 0 blocker and is neutral against kill criteria, but it is a meaningful change to `review_driver.py`. Defer-to-operator.

2. **Under ADR 007, is `extra_fields` tolerated in steward's schema for Phase 1, or must all unknown-field routing be resolved before Phase 1 ships?** The plugin's extensibility pattern is "known → registry → top-level; unknown → `extra_fields`". Steward's §4.2 discipline could either (a) mirror this, or (b) enforce "every known emitter must route to a top-level field; `extra_fields` is a bug marker". Operator call.

3. **Under B.8, is there value in piloting `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` on a single flex lane for observation, or is the source-level evaluation sufficient to close B.8 without empirical data?** Evaluation says "insufficient to change the decision"; operator may want a small empirical pilot to sharpen the "graduates from experimental" Phase 3 re-evaluation trigger.

4. **Under ADR 010, should the Phase 3 soft re-evaluation trigger thresholds (20 KB / 500 entries / 10 candidate lessons per nightly / 1 week sustained) be tightened, loosened, or replaced with an operator-read threshold like "grep produces >50 hits on a common query"?** Thresholds in this evaluation are first-cut; operator can calibrate against actual KB growth observed during Phase 0.

---

## 8. Phase 2 Decision Inputs (per §15.2, cross-cutting — this artifact)

This is the subsection for the evaluation artifact itself, distinct from the per-target subsections in §2-§5.

**Portability readiness:** Improved. Rejecting wholesale adoption of three of four candidates (code-review plugin / Agent Teams / mcp-memory-service) and cherry-picking patterns for implementation in bespoke code keeps the portability seam thin. Only Primitive A's dispatcher implementation (ADR 007) introduces a pattern dependency on external source, and that pattern is Python-stdlib-only.
**Meta-layer need:** No change. Source evaluations sharpen scope boundaries without implying a new abstraction layer.
**Kill signal for primitive(s) named:** No. Primitives A, B, C, D, E all remain live. Evaluations narrow scope (B.8) and refine implementation (ADR 005, ADR 007) rather than kill.
**Re-evaluation needed in Phase 3:** Yes, two soft triggers: (a) if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` graduates from experimental and task schema gains scope/metadata fields (B.8 re-evaluation); (b) if `knowledge/NOTES.md` exceeds size/cadence thresholds (ADR 010 re-evaluation). Recommended evaluation window for both: 6 months post Phase 2 close, or when the respective upstream change lands, whichever sooner.
**Surprise finding:** Three of four candidates are marketed with framing that exceeds source behavior — `code-review` plugin's "0-100 scoring" is actually a two-pass filter; Agent Teams' "persistent task system" is session-ephemeral with no restart; `mcp-memory-service`'s "consolidation" is autonomous mutation that would conflict with commit discipline. Marketing-vs-source gap reinforces §10.9 extensibility pattern #2 ("native-substrate-first defaults") as a **source-reading discipline**, not a search-summary discipline. Worth codifying a changelog-review-skill rule: "for any Tier S candidate, require a source snippet citation before adoption."
**Disposition:** open
