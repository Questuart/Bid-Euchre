# ADR G10 — `.claude/system_prompts/` vs. `.claude/agents/` Relationship

**Status:** SEEDED at Phase 0 kickoff; filing at Phase 0 kickoff
**Primitive:** B (B.9a artifact readiness, B.9b fleet launch adoption); cross-cutting with G (19-lane → 8-archetype mapping, G13)
**Supersedes:** implicit pre-B.9 state (19 verbose `.claude/agents/<lane>.md` files doing double duty as both Agent-tool subagent profiles and session-bootstrap identity prompts, with no `.claude/system_prompts/` directory)
**Seed source:** `plans/steward_platform/governing_plan.md` §5-B B.9 G10 open question; analyst-d finding G10 from `plans/steward_platform/draft7_review_analyst-d.md` §3 G10; default assumption in draft 8 §5-B B.9a is **(c) orthogonal**.

---

## Context

Draft 8 Primitive B sub-deliverable B.9 introduces
`.claude/system_prompts/<archetype>.md` — 8 archetype-level sparse system
prompts passed to each lane launch via `--system-prompt-file`. The
motivation is harness assumption "Default system prompt behavior": the
Claude Code default system prompt appears to degrade 4.7+ model behavior
vs. a sparse custom prompt (observed in operator testing; drove the
changelog-review skill and davidad thread referenced in draft 7).

The existing `.claude/agents/` directory already carries 23 files
serving different purposes:

- **19 lane-identity files** (orchestrator, ops, review, 4 analysts,
  4 authors, 4 brws-authors, 4 flex lanes, 1 scratch) loaded at session
  bootstrap via `.claude/tmux/steward-session.sh`'s `--agent <name>`
  flag on each `$CLAUDE_BIN` invocation.
- **6 subagent archetypes** (architecture-reviewer, correctness-reviewer,
  coverage-reviewer, plan-reviewer, blind-comparator, repair) loaded
  on-demand via the Agent tool inside a running session.
- **README.md** documenting the directory.

**Two distinct loading paths operate on this directory today:**

| Load path | Trigger | Consumer | Frontmatter semantics |
|---|---|---|---|
| Session bootstrap | `claude --agent <name>` in `steward-session.sh` (19 launches) | Pane-persistent lane identity | `name`, `description`, `allowedTools`, `disallowedTools`, `model` — **runtime-enforced** at tool dispatch |
| Agent-tool subagent spawn | Agent tool call inside a running session | Ephemeral subagent | Same frontmatter semantics, enforced for the subagent's tool calls |

**Key observation 1 — structural frontmatter boundaries are agents-file-only.**
Claude Code's `--system-prompt-file` CLI flag injects a system-prompt
string. It does **not** carry frontmatter — it cannot set `allowedTools`,
`disallowedTools`, or `model`. Those boundaries are set by `--agent
<name>` consulting `.claude/agents/<name>.md`.

Today those boundaries are load-bearing:

- `steward-review` → `allowedTools: [Read, Grep, Glob, Bash, ToolSearch, Skill]` — structurally cannot Edit/Write.
- `steward-ops` → `disallowedTools: [Edit, Write, Agent]` — monitoring-only.
- `steward-analyst` (this lane) → `disallowedTools: [Agent]` — may edit plans, cannot recurse into hidden subagents.

Removing `.claude/agents/<lane>.md` would remove those structural
guardrails and demote them to prose discipline — a regression the
plan's Pattern 9 load-bearing-ownership lint is meant to prevent.

**Key observation 2 — specialist reviewers have no system_prompts counterpart.**
B.9a creates 8 archetype files covering *lane archetypes* only.
The 6 specialist-reviewer / repair subagents (architecture-reviewer,
correctness-reviewer, coverage-reviewer, plan-reviewer, blind-comparator,
repair) are not lane archetypes — they spawn via the Agent tool inside
a running lane's session. They have no session-bootstrap moment where
`--system-prompt-file` could apply. Their profiles must remain under
`.claude/agents/` because that is the only loading path the Agent tool
consults.

**Key observation 3 — B.9a scope is explicitly 8 archetypes, not 19 lanes.**
B.9a enumerates 8 archetype prompt files. The 19 current lanes collapse
to 8 archetypes per G13's first-deliverable mapping: orchestrator, ops,
review, analyst, author, brws-author, flex, scratch. Lanes within the
same archetype (analyst-a/b/c/d, author-a/b/c/d, etc.) share the same
`--system-prompt-file` at launch but may keep differentiated agents-file
identities (`steward-author-a` vs. `steward-author-b`).

## Decision

**Pick (c) Orthogonal — confirming draft 8's default assumption, with
three refinements that clarify the split and pre-empt foreseeable
confusion.**

The two surfaces describe different things and both persist:

### (c.1) `.claude/system_prompts/<archetype>.md` — sparse system-prompt override for session bootstrap

- **Scope:** 8 files, one per archetype (orchestrator, ops, review,
  analyst, author, brws-author, flex, scratch).
- **Loader:** `claude --system-prompt-file .claude/system_prompts/<archetype>.md`
  passed by `steward-session.sh` alongside `--agent` (B.9b).
- **Purpose:** replace the Claude Code default system prompt (which
  degrades 4.7+ behavior per harness assumption) with a sparse
  archetype-level prompt.
- **Content discipline:** sparse. Role summary + hard constraints +
  named-skill pointers. Does not duplicate the operating-rules detail
  that lives in agents-file bodies.
- **Content scope:** archetype-level generic, not lane-specific. All
  4 analyst lanes load the same `analyst.md`; all 4 authors load the
  same `author.md`.

### (c.2) `.claude/agents/<lane-or-subagent>.md` — per-lane/subagent identity + frontmatter boundaries + on-demand Agent-tool subagent prompt

- **Scope:** remains per-lane (19 files) + per-specialist-subagent
  (6 files) + README = 26 files after G13 lane count is
  preserved. G13 may later consolidate lane identities but does not
  collapse them to 8 at the agents-file layer — lane identity
  differentiation (e.g., author-a vs. author-b) is still useful for
  session metadata, dashboard display, and targeted ops tooling.
- **Loader:** `claude --agent <name>` at session bootstrap; Agent tool
  at subagent spawn.
- **Purpose:** (i) enforce structural tool boundaries via frontmatter;
  (ii) provide lane-persistent identity metadata (name, description,
  model); (iii) provide subagent-spawn prompt content for the 6
  specialist subagents that have no session-bootstrap moment.
- **Content discipline:** no change in this ADR. Lane agents-file
  bodies may be sparse or verbose depending on whether the lane's
  operating rules are better carried by `.claude/rules/` or by the
  agents-file body. See "Open questions" below for the follow-on
  question of whether lane agents-file bodies should themselves be
  compressed to reduce 4.7+ context inflation at subagent-spawn time.

### Load-order contract when both flags fire (session bootstrap)

Claude Code's CLI accepts both `--system-prompt-file <path>` and
`--agent <name>` on the same invocation. The load-order contract we
rely on:

1. **System prompt** = contents of `--system-prompt-file` (replaces
   default). This is the 4.7+ regression fix.
2. **Agent identity + frontmatter** = `--agent` consults
   `.claude/agents/<name>.md`, establishes lane identity, enforces
   `allowedTools` / `disallowedTools` / `model` for the session's
   tool dispatch.
3. **Agent body content** — Claude Code internals determine whether the
   agents-file body is appended as additional system/user context or
   ignored when `--system-prompt-file` is also present. **This is a
   harness_assumption we do not control.** See "Open questions."

If the agents-file body is appended as additional context, the sparse
`--system-prompt-file` still replaces the default (baseline win), but
the agents-file body adds archetype-level ops detail. If the agents-file
body is ignored, only the sparse system prompt fires. In either case,
the sparse prompt + frontmatter boundaries land, which is what B.9a/b
are buying.

### `.claude/agents/README.md` update scope

The README gains a short section documenting the two loading paths,
the frontmatter-boundary-only-lives-here rule, and the relationship to
`.claude/system_prompts/`. Out of scope for this ADR (flows through
B.9a implementation packet).

## Consequences

- **Both file trees persist.** `.claude/system_prompts/` (8 archetype
  files, sparse) + `.claude/agents/` (26 files: 19 lane + 6 subagent +
  README, unchanged content discipline).
- **Frontmatter boundaries preserved.** `steward-review`'s read-only
  tool allowlist, `steward-ops`'s monitoring-only denylist, and
  `steward-analyst`'s no-subagent-recursion boundary continue to fire
  structurally.
- **Specialist-subagent loading preserved.** architecture-reviewer,
  correctness-reviewer, coverage-reviewer, plan-reviewer,
  blind-comparator, and repair continue to load from `.claude/agents/`
  via the Agent tool — unaffected by B.9a/b.
- **File-count trade.** We hold 8 system_prompts files + 26 agents
  files simultaneously. The 19-lane → 8-archetype collapse happens at
  the system_prompts layer, not the agents layer. This is the
  operational cost of keeping structural frontmatter boundaries
  per-lane.
- **No content-duplication trap.** Archetype-generic content lives in
  `.claude/system_prompts/`; per-lane identity + frontmatter
  boundaries live in `.claude/agents/`; cross-cutting operating rules
  (testing tiers, determinism, PR rules) continue to live in
  `.claude/rules/`. Three surfaces, three distinct purposes.
- **`harness_assumptions.md` entry.** The agents-file-body-loading
  behavior when both `--system-prompt-file` and `--agent` are present
  must be recorded as a harness assumption (Primitive C). Brittleness
  signal: grep pattern on `steward-session.sh` verifies both flags
  present on every launch line; `claude --help` regression check
  detects if either flag's semantics change on upgrade.
- **Pattern 10 (§10.9) verification-contract.** B.9a implementation
  packet's verification surface: `test -f .claude/system_prompts/<name>.md`
  for all 8 archetypes; agents-file frontmatter validated by
  `agent_readability_lint.py` (G1) for allowlist/denylist preservation;
  session-bootstrap launch lines in `steward-session.sh` carry both
  flags (unit test extending `tests/unit/test_steward_session.py`).

## Alternatives considered

### (a) Replacement — rejected

**Claim:** `.claude/system_prompts/<archetype>.md` supplants
`.claude/agents/<lane>.md` body content; agents-file retains
frontmatter/metadata only.

**Rejection rationale:**

1. **Specialist-subagent loading breaks.** architecture-reviewer,
   correctness-reviewer, coverage-reviewer, plan-reviewer,
   blind-comparator, and repair have no session-bootstrap moment.
   They are loaded on-demand by the Agent tool. Stripping their
   body content from `.claude/agents/` and moving it to
   `.claude/system_prompts/` leaves the Agent tool with nothing to
   load, because the tool does not consult `.claude/system_prompts/`.
2. **19 frontmatter-only agents files vs. 8 archetype system_prompts
   files creates a 19→8 mapping indirection** that must be expressed
   somewhere. The natural home is the session-bootstrap script, where
   each `--agent <lane-name>` launch line also passes a matching
   `--system-prompt-file <archetype>.md`. This works for lanes but
   **does not cover Agent-tool subagent spawns** — a subagent launched
   mid-session via `Agent(architecture-reviewer)` has no bootstrap
   moment to re-inject a system_prompts file. Replacement either
   leaves the subagent with an empty body (broken) or requires
   plumbing `--system-prompt-file` into the Agent tool's spawn path
   (substantial Claude Code internals change, not available).
3. **"Single source of truth per archetype"** — the claimed pro of
   (a) — is already achieved by (c): archetype-generic content lives
   in `.claude/system_prompts/<archetype>.md`; lane-differentiated
   metadata (which is genuinely per-lane) lives in `.claude/agents/`.
   (a) does not give us a single source; it gives us a
   frontmatter/body split where the body lives in a different file
   under a different loader — a worse single-source story, not a
   better one.

### (b) Supplement — rejected

**Claim:** `.claude/system_prompts/<archetype>.md` is a sparse override
loaded in addition to `.claude/agents/<lane>.md`; loading order
documented.

**Rejection rationale:**

1. **"Two prompts loaded for the same lane" defeats the 4.7+
   regression fix.** The sparse prompt only helps if it replaces
   verbose defaults. If it stacks on top of a verbose
   `.claude/agents/<lane>.md` body, the combined context still
   contains the verbose content — the sparse addition is cosmetic,
   not a regression fix.
2. **Loading-order documentation is not loading-order enforcement.**
   (b) presumes an operator-controlled merge semantics that Claude
   Code does not expose. We cannot guarantee the `--system-prompt-file`
   contents win over agents-file body content in the combined system
   prompt; that depends on internal concatenation order we don't
   control.
3. **(b) differs from (c) mostly in framing.** Under (c), the
   agents-file body may or may not load alongside `--system-prompt-file`
   — that ambiguity is a harness_assumption, not a design choice. (b)
   promotes the ambiguity to a design decision and claims loading
   order is documented, but the documentation has no enforcement
   surface. (c) treats it as a harness dependency, which is the
   honest framing.

### (d) Hybrid "c+a-lite" — deferred to open question

Agents-file bodies themselves could be compressed to reduce
subagent-spawn context inflation (relevant for the 6 specialist
subagents). This is orthogonal to G10 (does not affect the
system_prompts vs. agents relationship per se) and is routed to a
Primitive G follow-up — see "Open questions."

## Open questions

1. **Agents-file body content when both flags fire.** What exactly
   does Claude Code do with the `.claude/agents/<name>.md` body when
   `--system-prompt-file` is also present? Empirically verify and
   record as a `knowledge/harness_assumptions.md` entry during B.9b
   implementation. Refresh trigger: Claude Code release notes
   mentioning changes to `--agent` or `--system-prompt-file` semantics.
2. **Subagent-spawn 4.7+ regression.** B.9a/b does not close the 4.7+
   regression for Agent-tool subagent spawns (architecture-reviewer
   etc.). Whether that materially affects review quality is unknown.
   Route to Primitive G follow-up: measure during the proving run
   whether specialist-subagent output quality degrades relative to
   lane-persistent output; if yes, compress `.claude/agents/*.md`
   bodies for the 6 specialist subagents.
3. **G13 mapping formalization.** Which 19 lanes map to which 8
   archetypes is covered by G13's first-deliverable sub-sub-plan
   under Primitive G. This ADR assumes that mapping exists at B.9a
   authoring time; if G13 materially changes the archetype list
   (e.g., to 7 or 9), B.9a absorbs the change without needing a new
   ADR — the relationship between system_prompts and agents holds
   regardless of archetype count.
4. **Pilot on single lane first?** Optionally land B.9a + B.9b for
   one archetype (recommendation: `analyst`, since it has 4 lanes
   with identical archetype semantics and operator attention is
   already on this lane during Phase 0 shaping) before fleetwide
   rollout. Reduces blast radius of a harness-assumption surprise.

## Source evidence

- `.claude/agents/README.md` — documents "Enforced Role Boundaries"
  table (review → allowedTools; ops → disallowedTools Edit/Write/Agent;
  analyst → disallowedTools Agent), "Model Annotations" table, and
  "Session Bootstrap" section stating `steward-session.sh` uses
  `--agent <name>` flags for 15+ lanes.
- `.claude/tmux/steward-session.sh` lines 431–535 — 19 launch lines
  each carrying `--agent steward-<lane> --permission-mode auto`.
- `.claude/agents/steward-review.md` lines 1–11 — YAML frontmatter
  with `allowedTools: [Read, Grep, Glob, Bash, ToolSearch, Skill]`
  as structural enforcement.
- `.claude/agents/steward-analyst.md` lines 1–6 — frontmatter with
  `disallowedTools: [Agent]`.
- `plans/steward_platform/governing_plan.md` §5-B B.9a (line 359) —
  "Relationship to existing `.claude/agents/<lane>.md` (23 files
  currently loaded by Agent tool) **resolved via ADR at Phase 0
  kickoff (G10 fix)**"; default assumption stated as (c) orthogonal.
- `plans/steward_platform/governing_plan.md` §5-B B.9b (line 360) —
  "Every fleet launch passes `--system-prompt-file`; zero launches
  fall back to default."
- `plans/steward_platform/governing_plan.md` §5-G Work bullet (line
  580) — dependency chain G13 → B.9a → B.9b documented as strictly
  one-way.
- `plans/steward_platform/0_hardening/sub/rework_spec.md` §3 line 99
  (G10/G13 catalog row) — `.claude/agents/` disposition: "Consolidate
  to 8 archetypes per B.9. [...] Specialist reviewer agents
  (architecture, correctness, coverage, plan-reviewer) stay as
  subagent archetypes, not lane archetypes."
- `plans/steward_platform/draft7_review_analyst-d.md` §3 G10 (lines
  570–618) — analyst-d's original finding and three-option framing
  that draft 8 absorbed.

## Phase 2 Decision Inputs

**Portability readiness:** no change. Both loading surfaces (CLI flags
`--agent` and `--system-prompt-file`) are native Claude Code; neither
introduces a bespoke loader. Native-substrate adoption increases at
B.9b, which is the portability win.

**Meta-layer need:** no change. The relationship is expressible in
plan prose and `agent_readability_lint.py` (G1) without a new meta-layer.

**Kill signal for primitive(s) named:** no. (c) keeps both surfaces;
neither primitive B nor G is invalidated. If empirical observation
during the proving run shows the harness-assumption about agents-file
body loading is materially wrong (e.g., both `--system-prompt-file`
contents and agents-file body concatenate verbosely and the 4.7+
regression persists), this ADR is superseded by a new ADR revisiting
(a)/(b), not killed.

**Re-evaluation needed in Phase 3:** yes, soft trigger. RE-EVAL: after
Phase 1 proving run, re-examine whether the specialist-subagent 4.7+
regression (Open Question #2) is material; if yes, the right fix is
compressing `.claude/agents/*.md` bodies for the 6 specialist
subagents (orthogonal to G10 core decision). Also re-evaluate if
Claude Code release notes change `--agent` or `--system-prompt-file`
semantics.

**Surprise finding:** `.claude/agents/<name>.md` frontmatter is
load-bearing for structural tool-boundary enforcement (allowlist /
denylist / model). Options (a) and (b) both implicitly assumed
frontmatter is metadata-only and bodies are the substantive content;
in fact the frontmatter carries the runtime guardrails that prevent
`steward-review` from editing code and `steward-ops` from spawning
subagents. This reinforces Pattern 9 load-bearing-ownership lint:
what looks like "just YAML metadata" is actually the enforcement
surface for lane role boundaries.

**Disposition:** open (pending Phase 0 kickoff filing)
