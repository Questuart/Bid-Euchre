# Research: Improve Orchestrator-to-Analyst Delegation Defaults

> **Issue:** #2251
> **Task Packet:** `5310b6da6630`
> **Lane:** analyst-c
> **Date:** 2026-04-03
> **Status:** COMPLETE

## Executive Summary

The orchestrator over-executes by reading source code, writing detailed
technical issue bodies, and performing analysis that should be delegated to
analyst lanes. This happens because:

1. The orchestrator's `disallowedTools` only blocks `Agent` — it retains full
   `Read`, `Grep`, `Edit`, `Write` access to all source files
2. The analyst routing triggers in the system prompt are too narrow — they
   only fire for plan-heavy or multi-lane scenarios, missing common
   investigation work
3. The delegation guidelines table routes "Exploratory analysis" to
   `author-scratch` or `flex-*` instead of analyst lanes
4. No complexity guard or "investigation budget" warns the orchestrator when
   it's spending tokens on work that should be delegated

This document proposes a hybrid enforcement strategy (prompt + tool + skill
changes) across 3 PRs.

---

## 1. Evidence of Over-Execution

### 1.1 Behavioral Evidence (from #2251)

The orchestrator has been observed:
- **Reading source files** using `Read`/`Grep` on `src/` to investigate bugs
  and understand implementations
- **Writing technical details in GitHub issues** — drafting full root cause
  analysis, affected file lists, and proposed fixes inline in issue bodies
- **Performing analysis** (reading multiple source files, tracing call chains,
  writing technical summaries) instead of creating a task packet for an
  analyst lane

This consumes orchestrator context tokens (the bottleneck in the fleet) on
work that analyst lanes are designed to handle.

### 1.2 Configuration Evidence

**Current orchestrator `disallowedTools`:**

```yaml
# .claude/agents/steward-orchestrator.md (frontmatter)
disallowedTools:
  - Agent
```

That's it. Only `Agent` is blocked. Compare with other non-implementation lanes:

| Lane | `disallowedTools` / `allowedTools` | Effect |
|------|-------------------------------------|--------|
| `steward-orchestrator` | `disallowedTools: [Agent]` | Can read/write everything except spawn agents |
| `steward-ops` | `disallowedTools: [Edit, Write, Agent]` | Cannot modify files at all |
| `steward-review` | `allowedTools: [Read, Grep, Glob, Bash, ToolSearch, Skill]` | Read-only — strictest boundary |
| `steward-analyst` | `disallowedTools: [Agent]` | Same as orchestrator (by design — analysts need source access) |

**The README documents this as intentional:**

> `steward-orchestrator` | Needs full capability set for task delegation and
> coordination

This rationale is too broad. The orchestrator needs `Read`/`Grep` for plans,
docs, and MEMORY.md — but not for `src/**`, `tests/**`, or `experiments/**`.

### 1.3 Prompt Gaps

**Gap A — Analyst routing triggers are too narrow:**

The orchestrator's system prompt (`.claude/agents/steward-orchestrator.md`)
lists these triggers for analyst routing:

> - The work needs a sub-plan or major plan refresh
> - More than one lane may touch the area
> - The implementation seam is unclear
> - Tests, gates, or proving steps are not obvious
> - A GitHub issue needs deeper evidence and a recommended fix plan
> - A restart or end-of-wave handoff needs to be drafted
> - Plans, checkpoints, or task lists have drifted from repo reality

**Missing triggers:**
- Any task requiring reading source code (`src/`, `tests/`, `scripts/`)
- Bug investigation or root cause analysis
- Feature research requiring codebase analysis
- Technical issue body writing (anything beyond a 2-sentence summary)
- Research tasks (web search, documentation review, competitive analysis)

**Gap B — Delegation guidelines table misroutes analysis:**

```
| Exploratory analysis | No | author-scratch or flex-* | (flex) |
```

This routes investigation/analysis to implementation lanes instead of analyst
lanes. The analyst lane exists precisely for this purpose.

**Gap C — No "investigation budget" guard:**

Nothing in the prompt warns: "If you are about to read source files to
understand a problem, delegate to an analyst instead." The orchestrator's
role statement says "do not write implementation code" — but investigation
and analysis are not implementation code, so the guard doesn't trigger.

### 1.4 Token Economy Impact

From the token economy analysis (`plans/sessions/2026-04-03_token_economy_optimization.md`):

| Pool | Output/Commit (K tokens) | Sessions |
|------|-------------------------|----------|
| Author | 9.9 | 520 |
| Analyst | 21.6 | 56 |
| Control (orch+ops) | N/A (0 commits) | 142 |

The orchestrator burns tokens on analysis work that produces no commits.
When the orchestrator investigates, those tokens are pure overhead — an
analyst doing the same work at least produces a durable artifact (plan,
issue package, handoff document).

---

## 2. Prior Art: Multi-Agent Delegation Patterns

### 2.1 Industry Frameworks

| Framework | Coordinator Model | Tool Boundary Enforcement |
|-----------|------------------|--------------------------|
| **CrewAI** (hierarchical) | Auto-introduces "Manager Agent" that coordinates, doesn't execute | Task-output mediation — manager sees results, not tools |
| **Google ADK** | AgentTool pattern: specialists are tools the coordinator invokes | Coordinator's tools ≠ specialist's tools by construction |
| **Microsoft Azure Agent Framework** | "Orchestrator contains zero business logic about when to use specific tools" | Coordinator routes to Connected Agents |
| **Claude Code agent defs** | `disallowedTools` / `allowedTools` in frontmatter | Runtime enforcement at tool-dispatch level |

### 2.2 Addy Osmani — "Code Agent Orchestra" (2026)

> "You can press Shift+Tab to restrict the lead to coordination only —
> spawning, messaging, shutting down teammates, and managing tasks. This
> stops a common problem: **the lead getting distracted and implementing
> things itself instead of waiting for teammates.**"

This directly describes our problem. The solution is structural: restrict
the coordinator's tool surface so it *cannot* do the work, forcing
delegation.

### 2.3 Academic Survey (arXiv 2601.13671)

> "The Governance Agent's role is not to execute tasks, but to resolve
> conflicts, arbitrate between competing proposals, and enforce system-level
> constraints."

> "Workers execute narrow tasks, supervisors coordinate and verify, and a
> meta-agent controls strategy and confidence."

### 2.4 Key Insight

All mature multi-agent frameworks enforce coordinator boundaries
**structurally** (tool restrictions, capability limits) rather than relying
solely on prompt instructions. Prompt-only enforcement degrades under
context pressure — the model "forgets" its role boundaries when the task
seems simple enough to handle inline.

**Sources:**
- [Addy Osmani — The Code Agent Orchestra](https://addyosmani.com/blog/code-agent-orchestra/)
- [Addy Osmani — Conductors to Orchestrators](https://addyosmani.com/blog/future-agentic-coding/)
- [Microsoft — AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [Google — Developer's Guide to Multi-Agent Patterns in ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
- [arXiv — The Orchestration of Multi-Agent Systems](https://arxiv.org/html/2601.13671v1)
- [Towards Data Science — The Multi-Agent Trap](https://towardsdatascience.com/the-multi-agent-trap/)
- [Confluent — Four Design Patterns for Event-Driven Multi-Agent Systems](https://www.confluent.io/blog/event-driven-multi-agent-systems/)
- [CrewAI GitHub](https://github.com/crewaiinc/crewai)
- [Claude Code — Custom Subagents Docs](https://code.claude.com/docs/en/sub-agents)

---

## 3. Proposed Changes

### Option A: Prompt-Only Enforcement (Soft)

Modify the orchestrator system prompt and skills to add:

1. **Expanded analyst routing triggers** — add missing cases
2. **Investigation budget guard** — explicit "do not read source files" rule
3. **Issue writing delegation rule** — delegate technical issue drafting
4. **Fix delegation guidelines table** — route analysis to analyst

**Pros:** Low-risk, no tool-level side effects, easy to iterate.
**Cons:** Degrades under context pressure. The model may still self-execute
when the task "seems simple enough."

### Option B: Tool-Level Enforcement (Hard)

Add structural tool restrictions to the orchestrator's `disallowedTools`:

```yaml
disallowedTools:
  - Agent
  - Edit
  - Write
```

Or more targeted with path patterns (if Claude Code supports path-scoped
disallowedTools — needs verification):

```yaml
disallowedTools:
  - Agent
  - Edit(src/**)
  - Edit(tests/**)
  - Edit(scripts/**)
  - Edit(experiments/**)
  - Write(src/**)
  - Write(tests/**)
  - Write(scripts/**)
  - Write(experiments/**)
```

**Pros:** Structural — cannot be bypassed by context pressure.
**Cons:** May break legitimate orchestrator workflows (writing MEMORY.md,
plans, session docs). Needs careful scoping. Path-pattern support in
`disallowedTools` needs verification.

### Option C: Hybrid (Recommended)

Combine prompt enforcement (broader triggers, investigation budget) with
targeted tool restrictions (block source file writes, not all writes).

#### C.1 — Orchestrator Agent Definition Changes

**File:** `.claude/agents/steward-orchestrator.md`

```yaml
# Change frontmatter from:
disallowedTools:
  - Agent

# To:
disallowedTools:
  - Agent
  - Edit
  - Write
```

Wait — this blocks writing plans and MEMORY.md. The orchestrator does need
`Write(plans/**)` and `Write(MEMORY.md)`. However, `disallowedTools` in
Claude Code agent frontmatter does not support path patterns (only
`permissions.allow` in `settings.json` does). So we must use `allowedTools`
(allowlist) instead:

```yaml
# Use allowlist to scope what the orchestrator CAN do:
allowedTools:
  - Read
  - Grep
  - Glob
  - Bash
  - ToolSearch
  - Skill
  - TaskCreate
  - TaskUpdate
  - TaskList
  - TaskGet
  - TaskOutput
  - TaskStop
  - WebSearch
  - WebFetch
  - AskUserQuestion
  - SendMessage
  - CronCreate
  - CronDelete
  - CronList
  - RemoteTrigger
  - mcp__github__*
  - mcp__memory__*
  - mcp__plugin_telegram_telegram__*
```

**Problem:** This allowlist is fragile — every new MCP tool needs to be added.
Also, it still allows `Read(src/**)` and `Grep(src/**)` which enables the
investigation pattern.

**Better approach:** Keep `disallowedTools` minimal and add **prompt-level
enforcement** for the investigation boundary:

```yaml
disallowedTools:
  - Agent
  - Edit
  - Write
```

Then handle plan/memory writes through a dedicated mechanism:
- The orchestrator creates analyst or author tasks that write plans
- Session handoffs and MEMORY.md updates are the final act of a session —
  done by the orchestrator in a "shutdown" mode where writes are expected

**Risk:** This is the strictest option. It makes the orchestrator fully
read-only except for Bash commands and tool calls. This may be too
restrictive — the orchestrator currently writes `plans/sessions/*.md` and
`MEMORY.md` as part of its normal workflow.

#### C.2 — Practical Recommendation

Given the risk of full Edit/Write blocking, the safest high-impact change
is a **tiered approach**:

**Tier 1 (PR 1 — Prompt changes, immediate):**

1. **Expand analyst routing triggers** in `steward-orchestrator.md`:

   Add these triggers to the "Analyst Routing" section:
   ```
   - The task requires reading source code (src/, tests/, scripts/)
   - Bug investigation or root cause analysis is needed
   - A GitHub issue body requires more than a 2-sentence summary
   - Research or competitive analysis is needed
   - You find yourself about to use Grep or Read on source files
   ```

2. **Add investigation budget guard** to "Operating Rules":
   ```
   8. **No source investigation:** If a task requires reading source files
      (src/, tests/, scripts/, experiments/) to understand the problem,
      delegate to steward-analyst immediately. You may read plans/, docs/,
      MEMORY.md, and .claude/ files for coordination. Reading source code
      is investigation — investigation is analyst work.
   ```

3. **Fix the delegation guidelines table:**
   ```
   | Exploratory analysis | No | analyst-a through analyst-d | (flex) |
   | Bug investigation    | No | analyst-a through analyst-d | (flex) |
   | Issue body drafting  | No | analyst-a through analyst-d | (flex) |
   ```

4. **Add issue-writing rule** to "Operating Rules":
   ```
   9. **Delegate issue writing:** When filing a GitHub issue that requires
      technical investigation (affected files, root cause, proposed fix),
      create an analyst task packet first. The analyst produces the issue
      package; you file it. You may file simple 1-2 sentence issues directly.
   ```

**Tier 2 (PR 2 — Skill updates, same wave):**

5. **Update `/run-fleet` analyst routing section** (lines 132-163 of
   `run-fleet/SKILL.md`) to include the expanded triggers.

6. **Update `/delegate-task` delegation guidelines table** (lines 37-45 of
   `delegate-task/SKILL.md`) to add the analyst rows.

7. **Update `/check-in` Phase 4 issue triage** to note that issues requiring
   source investigation should be routed to analyst, not investigated inline.

**Tier 3 (PR 3 — Tool restriction, after proving Tiers 1-2):**

8. **Add `Edit` and `Write` to orchestrator `disallowedTools`** once the
   prompt changes are proven effective. This structurally prevents the
   orchestrator from writing files. Plan writes and MEMORY.md updates would
   need to be routed through author or analyst lanes, or a special "shutdown
   write" mode would need to be designed.

   This is the highest-risk change and should only be attempted after Tiers
   1-2 have been running for at least 2 fleet sessions.

---

## 4. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Prompt changes degrade under context pressure | MEDIUM | Tier 3 tool restriction as backstop |
| Tool restriction blocks legitimate orchestrator writes (MEMORY.md, plans) | HIGH | Defer Tier 3 until write routing is designed |
| Over-delegation wastes analyst tokens on trivial lookups | LOW | "2-sentence rule" — if the issue needs ≤2 sentences, orchestrator handles it |
| Analyst lane unavailability causes orchestrator to block | MEDIUM | Fallback: orchestrator can read docs/plans (not src) for routing decisions |
| New triggers are too aggressive — everything gets routed | LOW | Tiers are incremental; observe before adding Tier 3 |

---

## 5. Implementation Roadmap

### PR 1: Orchestrator prompt — delegation defaults (Tier 1)

**Scope:** `.claude/agents/steward-orchestrator.md`
- Add expanded analyst routing triggers
- Add investigation budget guard (rule 8)
- Fix delegation guidelines table
- Add issue-writing delegation rule (rule 9)
- Update README.md enforced boundaries table rationale

**Validation:** Manual review — run 1 fleet session and check orchestrator
behavior. The orchestrator should delegate source-file investigation to
analyst instead of self-executing.

**Acceptance criteria:**
- All 4 new rules present in orchestrator agent def
- Delegation guidelines table routes analysis to analyst lanes
- No source-file Read/Grep by orchestrator in next fleet session (spot-check)

### PR 2: Skill updates — consistent routing (Tier 2)

**Scope:** `.claude/skills/run-fleet/SKILL.md`, `.claude/skills/delegate-task/SKILL.md`, `.claude/skills/check-in/SKILL.md`
- Mirror expanded analyst triggers in run-fleet analyst routing section
- Add analyst rows to delegate-task guidelines table
- Add routing note to check-in issue triage

**Validation:** Diff review — ensure skills match orchestrator agent def.

**Acceptance criteria:**
- All 3 skills updated with consistent analyst routing triggers
- Delegation guidelines table in delegate-task matches orchestrator def

### PR 3: Tool restriction (Tier 3) — DEFERRED

**Scope:** `.claude/agents/steward-orchestrator.md`, `.claude/agents/README.md`
- Add `Edit`, `Write` to `disallowedTools`
- Design write routing for MEMORY.md and plan updates
- Update README.md enforced boundaries table

**Prerequisites:** Tiers 1-2 proven in ≥2 fleet sessions.

**Acceptance criteria:**
- Orchestrator cannot use Edit/Write tools
- MEMORY.md and plan writes still happen (via delegated path)
- No regression in fleet throughput

---

## 6. Recommended Dispatch

**Immediate (this wave):** PR 1 + PR 2 can be dispatched to a single author
lane (author-a or author-b) — they touch only `.claude/agents/` and
`.claude/skills/` files with no source code overlap.

**Deferred:** PR 3 needs design work (write routing) and should be shaped by
an analyst before implementation.

**Safe parallelism:** PR 1 and PR 2 touch different files and can be
dispatched to separate author lanes if desired. PR 2 depends on PR 1 for
content consistency but not for merge order.

---

## Outcome

Research complete. Deliverable: this document at
`plans/sessions/2026-04-03_orch_analyst_delegation.md`.

Next: orchestrator should dispatch PR 1 to an author lane for implementation.
