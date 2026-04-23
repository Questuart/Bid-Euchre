# Sub-Plan: G13 — Lane → Archetype Mapping and System-Prompt Scaffolds

**ID:** SP-0-G13
**Date:** 2026-04-23
**Parent:** `plans/steward_platform/governing_plan.md` §5-G Primitive G
(first-deliverable sub-sub-plan); blocks §5-B B.9a / B.9b.
**Status:** proposed
**Owner:** analyst-d (drafting); author lane assigned by orchestrator for
downstream B.9a authoring packets
**Scope:** `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md`
(this file only).

---

## 1. Purpose

Produce the canonical mapping from the fleet's current concrete lane
identifiers to the 8 lane archetypes enumerated in governing plan §5-B
B.9 (orchestrator / ops / review / analyst / author / brws-author / flex
/ scratch), and publish the skeleton scaffolds for each archetype's
`--system-prompt-file` content. This sub-plan is G13 — the first
deliverable under Primitive G and the strict upstream gate for B.9a
(per-archetype system-prompt files) and B.9b (fleet launch adoption of
`--system-prompt-file`). Dependency chain: **G13 → B.9a → B.9b** (§5-G
Work bullet, §5-B B.9a Readiness).

The mapping consumes ADR G10 `.claude/system_prompts/` ↔ `.claude/agents/`
**orthogonal** ruling (see
[`plans/steward_platform/adrs/G10-system-prompts-vs-agents.md`](../../adrs/G10-system-prompts-vs-agents.md),
PR #2765). Under G10:

- `.claude/system_prompts/<archetype>.md` (8 files) carries the sparse
  per-launch system prompt passed to `claude --system-prompt-file`;
- `.claude/agents/<lane>.md` (26 files: 19 lane-identity + 6 specialist
  subagent + README) keeps its existing per-lane identity + frontmatter
  tool-boundary enforcement role, unchanged by this sub-plan.

G13 produces the archetype catalog (the *what*) and a content-shape
scaffold (the *skeleton*); full authoring of each archetype's system
prompt is a downstream B.9a authoring packet, not this one.

---

## 2. Work

### 2.1 Lane → archetype mapping table (all current lanes)

**Canonical archetype set** (governing plan §5-B B.9a enumeration): 8
archetypes — `orchestrator`, `ops`, `review`, `analyst`, `author`,
`brws-author`, `flex`, `scratch`.

**Source of truth for the concrete-lane enumeration:**
[`.claude/rules/75_worktree_protection.md`](../../../../.claude/rules/75_worktree_protection.md)
§ Protected Worktrees. Mapping rows below enumerate **20** protected
worktrees (19 active lanes — control plane + 4-lane pools — plus 1
legacy scratch lane that is protected-but-unpopulated under current
dispatch).

> **Arithmetic note.** Governing plan §5-B B.9a and ADR G10 reference
> "19 lane-identity files" and "19 launches" interchangeably with "19
> current steward lanes." Those counts collapse to the 19 *active*
> panes (orchestrator + 3 control-plane + 16-lane working pool); the
> 20th protected worktree is `author-scratch`, which is a protected
> filesystem entry but is not included in the active-pane count. This
> sub-plan maps all 20 rows rather than 19 so the archetype catalog is
> exhaustive with respect to the worktree protection registry.

| # | Lane identifier | Worktree path (protected) | Archetype | Rationale (if non-obvious) |
|---|---|---|---|---|
| 1 | `orchestrator` | `Bid-Euchre-steward` (main checkout) | `orchestrator` | 1:1 |
| 2 | `ops` | `Bid-Euchre-steward-ops` | `ops` | 1:1 |
| 3 | `review` | `Bid-Euchre-steward-review` | `review` | 1:1 |
| 4 | `analyst-a` | `Bid-Euchre-steward-analyst` | `analyst` | pool member |
| 5 | `analyst-b` | `Bid-Euchre-steward-analyst-b` | `analyst` | pool member |
| 6 | `analyst-c` | `Bid-Euchre-steward-analyst-c` | `analyst` | pool member |
| 7 | `analyst-d` | `Bid-Euchre-steward-analyst-d` | `analyst` | pool member |
| 8 | `author-a` | `Bid-Euchre-steward-author` | `author` | platform pool primary |
| 9 | `author-b` | `Bid-Euchre-steward-author-b` | `author` | platform pool member |
| 10 | `author-c` | `Bid-Euchre-steward-author-c` | `author` | platform pool member |
| 11 | `author-d` | `Bid-Euchre-steward-author-d` | `author` | platform pool member |
| 12 | `brws-author-a` | `Bid-Euchre-steward-brws-author-a` | `brws-author` | browser-game pool primary |
| 13 | `brws-author-b` | `Bid-Euchre-steward-brws-author-b` | `brws-author` | browser-game pool member |
| 14 | `brws-author-c` | `Bid-Euchre-steward-brws-author-c` | `brws-author` | browser-game pool member |
| 15 | `brws-author-d` | `Bid-Euchre-steward-brws-author-d` | `brws-author` | browser-game pool member |
| 16 | `flex-a` | `Bid-Euchre-steward-flex-a` | `flex` | domain-agnostic overflow pool |
| 17 | `flex-b` | `Bid-Euchre-steward-flex-b` | `flex` | domain-agnostic overflow pool |
| 18 | `flex-c` | `Bid-Euchre-steward-flex-c` | `flex` | domain-agnostic overflow pool |
| 19 | `flex-d` | `Bid-Euchre-steward-flex-d` | `flex` | domain-agnostic overflow pool |
| 20 | `author-scratch` | `Bid-Euchre-steward-author-scratch` | `scratch` | disposable exploratory lane; protected-but-unpopulated under current dispatch |

**Orphan check.** Zero lanes in the worktree protection registry fall
outside an archetype. Zero archetypes lack at least one concrete lane.
Coverage is 20/20 in both directions. Verification surface: §5.

**Non-collapse at the agents layer.** Consistent with ADR G10
decision (c.2), this mapping **does not** collapse 20 agents files to
8 at the `.claude/agents/` layer. `.claude/agents/<lane>.md` files
remain per-lane to preserve:

1. Lane identity metadata (`name`, `description`, `model` where set)
   used by dashboard display and `CLAUDE_AGENT_NAME` routing.
2. Structural tool-boundary enforcement (`allowedTools`,
   `disallowedTools`) which is frontmatter-driven and per-lane — see
   ADR G10 Key observation 1.
3. Specialist-subagent loading paths (6 files outside the 19+1
   lane-identity subset) that have no session-bootstrap moment and
   must load via the Agent tool.

The 20 → 8 collapse happens exclusively at the `.claude/system_prompts/`
layer: 8 archetype files, referenced by `--system-prompt-file` at each
of the 19 active-pane launches. Lane-within-archetype differentiation
(e.g., `author-a` vs. `author-b`) persists in the agents file only.

### 2.2 Per-archetype system-prompt scaffolds (skeleton, not full authoring)

Each scaffold below names the five required fields for downstream B.9a
authoring packets: **(a) responsibility paragraph**, **(b) tool
allowlist posture**, **(c) model-tier hint**, **(d) effort-tier hint**,
**(e) relationship to `.claude/agents/<lane>.md` per G10**. Scaffolds
are intentionally short; full prose authoring (including folding in
insights from the Boris Cherny Opus 4.7 guidance referenced in
governing plan §5-B B.10) is a **downstream B.9a authoring packet**,
not G13.

The `.claude/system_prompts/` directory is created empty at B.9a
authoring time; file paths listed below are the canonical targets for
that packet.

#### 2.2.1 `orchestrator` archetype
- **Target file:** `.claude/system_prompts/orchestrator.md`
- **Concrete lane members:** `orchestrator` (1 lane).
- **Responsibility:** Single user-facing intake point for the steward
  dashboard. Routes shaping work to analyst, dispatches implementation
  work to author lanes via durable task packets, owns final dispatch
  authority.
- **Tool allowlist posture:** **selective** — Agent tool denied
  (preserved from `.claude/agents/steward-orchestrator.md`
  `disallowedTools: [Agent]`); otherwise permissive.
- **Model-tier hint:** opus (unset in existing agents file → default).
- **Effort-tier hint:** xhigh (routing + shaping require high-quality
  reasoning; Boris Cherny "xhigh for most").
- **Relationship to `.claude/agents/steward-orchestrator.md`:**
  **orthogonal** per G10 (c). Agents file retains frontmatter
  (`disallowedTools: [Agent]`), lane identity metadata, and persists
  body content governing the Agent-tool interaction profile. System
  prompt carries sparse per-launch role + named-skill pointers; the
  two compose at launch via `--agent steward-orchestrator
  --system-prompt-file .claude/system_prompts/orchestrator.md`.

#### 2.2.2 `ops` archetype
- **Target file:** `.claude/system_prompts/ops.md`
- **Concrete lane members:** `ops` (1 lane).
- **Responsibility:** Operator / monitoring surface. Observes lane
  health, CI, logs, worktrees, and blocked states; surfaces next safe
  action. Read-only — implementation edits route to author lanes.
- **Tool allowlist posture:** **restrictive** — Edit / Write / Agent
  all denied (preserved from `.claude/agents/steward-ops.md`
  `disallowedTools: [Edit, Write, Agent]`).
- **Model-tier hint:** sonnet (matches current `.claude/agents/steward-ops.md`
  `model: sonnet` frontmatter — monitoring loads do not need opus
  depth; cost-optimized).
- **Effort-tier hint:** lower (monitoring / status reporting is mostly
  pattern-matching; Boris Cherny "lower for simple").
- **Relationship to `.claude/agents/steward-ops.md`:** **orthogonal**
  per G10 (c). Agents file retains the `model: sonnet` and
  `disallowedTools` frontmatter — those are the structural guardrails
  keeping ops read-only and cost-bounded and cannot be expressed via
  `--system-prompt-file` alone.

#### 2.2.3 `review` archetype
- **Target file:** `.claude/system_prompts/review.md`
- **Concrete lane members:** `review` (1 lane).
- **Responsibility:** Independent reviewer. Reviews author branches
  against main, prioritizes findings by correctness risk, files WARN
  follow-up issues directly, routes complex issue packages back to
  analyst. Cannot edit code (structural).
- **Tool allowlist posture:** **restrictive** — `allowedTools: [Read,
  Grep, Glob, Bash, ToolSearch, Skill]` (preserved from
  `.claude/agents/steward-review.md`; most restrictive of the fleet).
  `Edit` and `Write` are structurally absent from the allowlist.
- **Model-tier hint:** opus (review quality is load-bearing; unset in
  existing agents file → default).
- **Effort-tier hint:** xhigh (thorough correctness review benefits
  from extended reasoning; Boris Cherny "xhigh for most").
- **Relationship to `.claude/agents/steward-review.md`:** **orthogonal**
  per G10 (c). The `allowedTools` frontmatter is load-bearing — it is
  the structural reason `steward-review` cannot Edit or Write code,
  even under a permissive `--system-prompt-file`. Removing the agents
  file or stripping its frontmatter would demote this guardrail to
  prose discipline (the regression ADR G10 Alternative (a) rejects).

#### 2.2.4 `analyst` archetype
- **Target file:** `.claude/system_prompts/analyst.md`
- **Concrete lane members:** `analyst-a`, `analyst-b`, `analyst-c`,
  `analyst-d` (4 lanes). All four load the *same* archetype system
  prompt per G10 (c) archetype-generic design.
- **Responsibility:** Shaping lane. Investigates ambiguous / flagged /
  restart-state-drift work, produces sub-plans, execution briefs,
  issue packages, and restart handoffs in repo-owned docs. Holds
  context, not code: product changes route to author lanes.
- **Tool allowlist posture:** **selective** — Agent denied (preserved
  from `.claude/agents/steward-analyst.md` `disallowedTools: [Agent]`;
  prevents subagent recursion into hidden lanes that would bypass
  dashboard observability).
- **Model-tier hint:** opus (shaping depth is the lane's value prop;
  unset in existing agents file → default).
- **Effort-tier hint:** max (deepest shaping benefits from the longest
  reasoning budgets; Boris Cherny "max for hardest").
- **Relationship to `.claude/agents/steward-analyst.md`:** **orthogonal**
  per G10 (c). Agents file retains the `disallowedTools: [Agent]`
  guardrail and lane-identity metadata. All four analyst lanes share
  one system prompt; per-lane differentiation (analyst-a vs. analyst-d)
  lives only in the agents file (`name`, `description`) and is
  dashboard-surface metadata, not operating-rule variance.

#### 2.2.5 `author` archetype
- **Target file:** `.claude/system_prompts/author.md`
- **Concrete lane members:** `author-a`, `author-b`, `author-c`,
  `author-d` (4 lanes — platform pool).
- **Responsibility:** Primary implementation lane for the steward
  dashboard's platform domain. Executes bounded coding tasks delegated
  via task packets. One bounded task at a time; scope-locked to
  packet's declared file patterns.
- **Tool allowlist posture:** **permissive** — Agent denied (preserved
  from `.claude/agents/steward-author-*.md` `disallowedTools: [Agent]`);
  otherwise full tool surface.
- **Model-tier hint:** opus (implementation quality benefits from
  depth; unset in existing agents files → default).
- **Effort-tier hint:** xhigh (most implementation work; Boris Cherny
  "xhigh for most"). Operator override to `max` for the hardest packets
  or `lower` for trivial single-file fixes.
- **Relationship to `.claude/agents/steward-author-*.md`:**
  **orthogonal** per G10 (c). All four author lanes share one system
  prompt; per-lane differentiation (a / b / c / d) lives only in the
  agents file (`name`, `description`, and primary-vs-secondary framing
  in the body). Dispatch-routing decisions (which author lane gets
  which packet) are orchestrator concerns, not system-prompt concerns.

#### 2.2.6 `brws-author` archetype
- **Target file:** `.claude/system_prompts/brws-author.md`
- **Concrete lane members:** `brws-author-a`, `brws-author-b`,
  `brws-author-c`, `brws-author-d` (4 lanes — browser-game pool).
- **Responsibility:** Primary implementation lane for the browser-game
  domain. Same lifecycle shape as `author`; scope-locked to
  browser-game packets unless explicitly overridden.
- **Tool allowlist posture:** **permissive** — Agent denied (preserved
  from `.claude/agents/steward-brws-author-*.md` `disallowedTools:
  [Agent]`); otherwise full tool surface.
- **Model-tier hint:** opus (same rationale as `author`).
- **Effort-tier hint:** xhigh (same rationale as `author`).
- **Relationship to `.claude/agents/steward-brws-author-*.md`:**
  **orthogonal** per G10 (c). Domain scoping (browser-game vs. platform)
  is the meaningful variance between `author` and `brws-author`
  archetypes; within each archetype, the four concrete lanes share
  one system prompt.

#### 2.2.7 `flex` archetype
- **Target file:** `.claude/system_prompts/flex.md`
- **Concrete lane members:** `flex-a`, `flex-b`, `flex-c`, `flex-d`
  (4 lanes — domain-agnostic overflow pool).
- **Responsibility:** Domain-agnostic overflow lane. Accepts work from
  any domain (platform or browser-game) when dedicated pool lanes are
  exhausted. Same lifecycle shape as `author` / `brws-author`.
- **Tool allowlist posture:** **permissive** — Agent denied (preserved
  from `.claude/agents/steward-flex-*.md` `disallowedTools: [Agent]`);
  otherwise full tool surface.
- **Model-tier hint:** opus (same rationale as `author`).
- **Effort-tier hint:** xhigh (same rationale as `author`).
- **Relationship to `.claude/agents/steward-flex-*.md`:** **orthogonal**
  per G10 (c). Cross-domain acceptance is the meaningful variance between
  `flex` and the domain-scoped author archetypes. Agents-file inventory
  currently has 3 flex files (`flex-a`, `flex-b`, `flex-c`); `flex-d`
  is protected in the worktree registry but has no agents file at the
  time of this sub-plan. **Flagged follow-up:** B.9a authoring packet
  should file `.claude/agents/steward-flex-d.md` if the lane is to be
  launched (see §2.3 Variance, row 3).

#### 2.2.8 `scratch` archetype
- **Target file:** `.claude/system_prompts/scratch.md`
- **Concrete lane members:** `author-scratch` (1 lane; legacy,
  protected, not in active pool).
- **Responsibility:** Disposable exploratory lane for planning,
  comparisons, draft work, and non-production reasoning. Output is
  non-authoritative unless explicitly promoted to a production author
  lane.
- **Tool allowlist posture:** **permissive** — Agent denied (preserved
  from `.claude/agents/steward-author-scratch.md` `disallowedTools:
  [Agent]`); otherwise full tool surface. Lack of production discipline
  is a content-posture constraint, not a tool-allowlist one.
- **Model-tier hint:** opus OR sonnet, operator choice at B.9a
  authoring (sonnet defensible for exploratory work where cost
  trumps depth; unset in existing agents file → default opus).
- **Effort-tier hint:** lower (exploratory work doesn't benefit from
  maxed reasoning; Boris Cherny "lower for simple"). Operator override
  to `xhigh` for exploratory plan drafting that will feed production
  packets.
- **Relationship to `.claude/agents/steward-author-scratch.md`:**
  **orthogonal** per G10 (c). Disposability framing lives in the
  agents file body and is the lane's distinguishing semantic; system
  prompt is a sparse role + "not-for-production" reminder.

### 2.3 Identified variance (per-lane-within-archetype divergence)

Most within-archetype variance is routing metadata (which dispatched
packet goes to author-a vs. author-b), not operating-rule variance.
Rows below enumerate the cases where within-archetype lanes *do*
genuinely diverge — these require per-lane overrides at the agents-file
layer, *not* per-lane system prompts (which would defeat the 8-file
collapse at the `.claude/system_prompts/` layer).

| # | Archetype | Within-archetype divergence | Carrier surface | Notes |
|---|---|---|---|---|
| 1 | `author` | `author-a` framed as "primary" (preferred for multi-file features); `author-b/c/d` as secondary/parallel pool members | `.claude/agents/steward-author-{a,b,c,d}.md` body prose | Dispatch-routing concern; no system-prompt impact |
| 2 | `brws-author` | `brws-author-a` framed as primary; others as pool members | `.claude/agents/steward-brws-author-{a,b,c,d}.md` body prose | Dispatch-routing concern; no system-prompt impact |
| 3 | `flex` | `flex-d` worktree protected but **no agents file** (`steward-flex-d.md` absent); `flex-a/b/c` have agents files | `.claude/agents/steward-flex-d.md` (to be authored) | **Follow-up:** B.9a authoring packet should file the missing agents file if `flex-d` is to participate in fleet dispatch. Currently 16 lane-identity agents files present (not 19+1 = 20). |
| 4 | all author archetypes | Pool primary vs. pool members have identical operating rules — differentiation is scheduling/affinity, not behavior | agents-file body prose + orchestrator dispatch heuristics | No system-prompt impact |
| 5 | (reserve) | No other genuine within-archetype divergence identified | — | If a future review finds one, add a row here; do **not** create per-lane system-prompt files without explicit ADR amendment superseding G10 |

**Principle.** Any proposal to introduce per-lane system prompts
(e.g., `.claude/system_prompts/author-a.md` distinct from
`.claude/system_prompts/author.md`) requires an ADR amending or
superseding G10, because it contradicts G10 decision (c.1)
"archetype-level generic, not lane-specific." Row-5 reservation exists
to catch that proposal early.

---

## 3. Phase 0 Readiness

**Readiness criteria for G13 to close and unblock B.9a:**

- [ ] Mapping table (§2.1) committed to this file; 20/20 lanes covered;
  zero orphan lanes; zero unmapped archetypes.
- [ ] 8 system-prompt scaffolds (§2.2) committed to this file, each
  specifying the five required fields (responsibility, tool allowlist
  posture, model-tier hint, effort-tier hint, G10 relationship).
- [ ] ADR G10 cited by file path + PR number in §1 Purpose
  (PR #2765; `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md`).
- [ ] Identified-variance table (§2.3) committed; `flex-d` missing
  agents-file flagged as B.9a follow-up row 3.
- [ ] Phase 2 Decision Inputs subsection (§15.2 schema) present at
  end of file.
- [ ] Orchestrator review logged (this sub-plan lands via PR to main;
  merge implies orchestrator review).

**Downstream gates unblocked by G13 readiness:**

- **B.9a authoring packet** (per-archetype system-prompt file creation
  at `.claude/system_prompts/<archetype>.md` × 8) — consumes the §2.2
  scaffolds as skeletons and adds full prose per Boris Cherny Opus 4.7
  guidance.
- **B.9b fleet launch adoption** (modify `.claude/tmux/steward-session.sh`
  to pass `--system-prompt-file` on every `$CLAUDE_BIN` invocation) —
  consumes B.9a files.

---

## 4. Phase 1 Validation

**Validation contract for G13 (proving-run signals):**

| # | Check | Surface | Pass criterion |
|---|---|---|---|
| 4.1 | Every fleet launch passes `--system-prompt-file` pointing to a file under `.claude/system_prompts/` | `tests/unit/test_steward_session.py` extension (B.9b precondition) | Structural test asserts each `$CLAUDE_BIN` launch line in `steward-session.sh` contains `--system-prompt-file .claude/system_prompts/<archetype>.md` where `<archetype>` matches the lane's row in §2.1 |
| 4.2 | Zero launches fall back to the Claude Code default system prompt | same test | Test scans all 19 active-pane launch lines; count of lines without `--system-prompt-file` must be 0 |
| 4.3 | Agents-file frontmatter tool-boundary preservation | `agent_readability_lint.py` (§5-C, G1) | Lint asserts `allowedTools` / `disallowedTools` / `model` fields in `.claude/agents/*.md` match the posture declared in §2.2 scaffolds (e.g., `steward-review.md` has `allowedTools: [Read, Grep, Glob, Bash, ToolSearch, Skill]`; `steward-ops.md` has `disallowedTools: [Edit, Write, Agent]` and `model: sonnet`) |
| 4.4 | No per-lane system-prompt files introduced | `agent_readability_lint.py` extension | Lint asserts `.claude/system_prompts/` contains at most 8 files, named from the archetype set exactly; any per-lane file (e.g., `author-a.md`) is a lint violation unless accompanied by an ADR amending G10 |

**Phase 1 Validation ownership.** 4.1 and 4.2 are B.9b's Phase 0 Readiness
criteria (governing plan §5-B B.9b) — they become Phase 1 Validation
*for G13* in the sense that G13 is the upstream author of the archetype
list those tests assert against. 4.3 is an invariant preservation
check that runs throughout Phase 1. 4.4 is the write-discipline guard.

---

## 5. Verification Plan

_Per Pattern 10 (§10.9) — every §2 / §3 deliverable names a
verification surface; strict-existence, lenient-form._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2.1 mapping table — all 20 lanes → 8 archetypes, zero orphans | new KB-class artifact (plan row table) | `grep -c '^| [0-9]\+ | \`' plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` (counts all numbered table rows with backticked lane/archetype identifiers in column 2 — §2.1 contributes 20, §2.3 contributes 3) | analyst | Count = 23 (= 20 §2.1 rows + 3 §2.3 rows with backticked archetype); §2.1-only cross-check via `grep 'Bid-Euchre-steward' plans/.../g13_archetype_mapping.md \| wc -l` yields 21 (20 §2.1 rows + 1 self-reference in this verification table); cross-check against `.claude/rules/75_worktree_protection.md` § Protected Worktrees list — 20 entries including `author-scratch` (flex-d appears twice in the registry due to a known duplication typo; counted once here) |
| §2.2 eight archetype scaffolds, each with 5 required fields | new KB-class artifact (plan subsections) | `grep -c '^#### 2\.2\.' plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` and per-section presence of "Responsibility", "Tool allowlist posture", "Model-tier hint", "Effort-tier hint", "Relationship to" | analyst | 8 subsections (§2.2.1 through §2.2.8); each subsection contains all 5 field labels |
| §2.3 variance table with `flex-d` follow-up flagged | new KB-class artifact | `grep 'flex-d' plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` | analyst | Returns at least one line in §2.3 row 3; the row names `.claude/agents/steward-flex-d.md` as the follow-up file |
| §3 Phase 0 Readiness — ADR G10 citation | ADR-class cross-reference (Pattern 9 load-bearing ownership) | `grep -n 'G10-system-prompts-vs-agents.md\|PR #2765' plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` | analyst | Returns ≥1 citation of the ADR file path AND ≥1 citation of PR #2765 |
| §4 Phase 1 Validation 4.1 / 4.2 — B.9b launch-line coverage | unit test (extension of existing) | `tests/unit/test_steward_session.py::TestSystemPromptFile` (authored by B.9b author packet) | author (B.9b packet) | Pytest passes; all 19 active-pane launch lines match the `--system-prompt-file .claude/system_prompts/<archetype>.md` pattern; 0 bare-default launches |
| §4 Phase 1 Validation 4.3 — agents-file frontmatter preservation | lint (existing script extension) | `scripts/internal/agent_readability_lint.py --check frontmatter-posture plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` (G1 script extended per §5-C) | author (G1 packet) | Lint exits 0; every §2.2 scaffold's declared posture matches the live `.claude/agents/<lane>.md` frontmatter |
| §4 Phase 1 Validation 4.4 — no per-lane system prompts | lint | same script, `--check archetype-file-count` mode | author (G1 packet) | `.claude/system_prompts/` file count ≤ 8; every filename is in the archetype set exactly; any violation fails CI |
| §6 Rollback — mapping revertible via git revert; system-prompt files individually disable-able | rollback test (Pattern 7) | `git revert <SP-0-G13 merge commit>` smoke (documented in §6) + per-file feature-flag disable path documented in §6 | author (rollback-test packet, minor) | Revert applies cleanly; flagged disable leaves `--system-prompt-file` absent on targeted lane; lane launches with default prompt without error |
| **Whole-file lint compliance** | agent-readability lint | `scripts/internal/agent_readability_lint.py plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` | author (G1 packet) | Lint exits 0 against §10.8 conventions |

**ADR cross-reference.** ADR G10 supersession route is documented in
G10 itself (§Phase 2 Decision Inputs "Kill signal" row). This
sub-plan's verification surfaces for §2.1 / §2.2 deliverables
transitively depend on G10 remaining in force; if a future ADR
supersedes G10, this sub-plan's §2.2 scaffolds must be re-authored
(not auto-migrated).

---

## 6. Rollback

**Reversibility of G13** (Pattern 7 — rollback path documented at
change-time).

| Change | Rollback path | Blast radius |
|---|---|---|
| This sub-plan file landing | `git revert <merge commit>` removes the file; no runtime dependency | File-only; B.9a packets not yet issued have no upstream artifact to consume — they must re-author the mapping or block on G13 re-land |
| Mapping entry revision (e.g., reassigning a lane to a different archetype) | New commit amending §2.1; B.9b launch-line test (§4.1) catches stale references on re-run | Single-lane; limited to that lane's `--system-prompt-file` target |
| Archetype set expansion (adding a 9th archetype) | Requires ADR amending G10 (G10 Open Question 3 explicitly permits if G13 changes archetype count); this sub-plan is updated to include the new archetype row and scaffold | Fleet-wide; all launch lines re-checked |
| Per-file disable at `.claude/system_prompts/<archetype>.md` layer | Feature flag at `steward-session.sh` launch-line level: comment out `--system-prompt-file` argument for the lane; lane falls back to Claude Code default system prompt | Single-lane; lane reverts to pre-B.9b behavior (4.7+ regression reappears for that lane but fleet continues) |
| Fleet-wide rollback of the `--system-prompt-file` adoption | Revert B.9b commit; `steward-session.sh` drops all `--system-prompt-file` arguments; fleet launches with defaults | Fleet-wide; observable as immediate drop in `prompt-policy-cited-in-trace` rate (per governing plan §5-B B.9b Phase 1 Validation) |

**Rollback-test proof (§Pattern 10 entry for §6).** The B.9b author
packet includes a rollback-test case: flip `--system-prompt-file` off
on a single lane (e.g., `author-d`); confirm lane launches with
default prompt without crash; re-enable the flag; confirm lane relaunches
with the archetype prompt restored. Output captured in the B.9b PR's
Verification Performed section.

---

## Phase 2 Decision Inputs

**Portability readiness:** no change — both `--system-prompt-file`
and `--agent` are native Claude Code CLI flags; neither requires
bespoke infrastructure. The mapping itself is Repo-specific metadata
(lane names are bespoke) but lives in
`.claude/rules/75_worktree_protection.md` as existing convention; G13
does not introduce new adapter-boundary pressure. Evidence: ADR G10
§Phase 2 Decision Inputs "Portability readiness" (unchanged from
this sub-plan's perspective).

**Meta-layer need:** no — relationship expressible in sub-plan prose +
`agent_readability_lint.py` extension (Primitive C, G1). No new
meta-layer required to express "archetype file count ≤ 8" or "launch
line carries `--system-prompt-file`."

**Kill signal for primitive(s) named:** no. G13 completion strengthens
Primitive G's Phase 0 Readiness (one more bullet flips green); B.9a /
B.9b become unblocked. If G13 cannot be completed (e.g., archetype
set expansion exceeds 8 to the point where the collapse is not
meaningful), the kill signal is for B.9a / B.9b, not for G. See §11-B
row 2 for the relevant cross-reference.

**Re-evaluation needed in Phase 3:** soft trigger — RE-EVAL: after
Phase 1 proving run, re-examine whether any within-archetype variance
emerged (§2.3) that the Phase 0 scaffold missed. If yes, consider
promoting the divergent lane(s) to a sub-archetype under an ADR that
amends G10. Also re-evaluate if new lanes are added to the fleet
(e.g., a new browser-expansion pool) — mapping must be extended before
those lanes launch.

**Surprise finding:** `flex-d` is protected in the worktree registry
but has no `.claude/agents/steward-flex-d.md` file at the time of this
sub-plan (§2.3 row 3). The fleet runs with 16 lane-identity agents
files + 3 control-plane = 19 files, not 20; the protection registry
anticipates a 4th flex lane that has not yet been materialized into
an agents file. B.9a authoring packet should either (a) file the
missing agents file and the flex archetype system prompt covers both,
or (b) retire `flex-d` from the protection registry if it is not to
be launched. Flagged as follow-up; does not block G13 merge.

**Disposition:** open (pending PR merge for this sub-plan's first
revision).

---

## Outcome

_Filled after completion._

- Status: TBD
- PR: TBD
- Deviations from plan: TBD
- Issues discovered: TBD
