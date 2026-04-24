# Shaping: B.9a — Per-Archetype System-Prompt Authoring Spec

**ID:** SP-0-B9a-SHAPE
**Date:** 2026-04-24
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-B B.9a
**Dependency chain:** **G13 → B.9a (this shape) → B.9a execution → B.9b fleet adoption**
**Upstream (must be complete):** G13 mapping at
`plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md`
(PR #2768 merged); ADR G10 at
`plans/steward_platform/adrs/G10-system-prompts-vs-agents.md`
(PR #2765 merged).
**Downstream:** B.9a execution packet (author lane; authors 8 files at
`.claude/system_prompts/<archetype>.md`); B.9b fleet adoption packet
(author lane; modifies `.claude/tmux/steward-session.sh` + review-lane
subprocess launches).
**Lane:** analyst-d
**Pattern:** Pattern 11 shape-then-execute dispatch (§10.9 governing plan).
**Status:** DESIGN-SPEC — this document contains no new code, no new
`.claude/system_prompts/` files, and no launch-script edits. Those
belong to the downstream execution packet(s).
**Packet:** `fe601b42c161`

---

## §1. Scope and Non-Scope

### §1.1 In scope

This shaping document is concrete enough that an author lane can issue
execution packets from it without additional shaping work. It specifies:

1. **Shared voice + structure invariants** across all 8 archetype prompts
   — tone, second-person framing, section conventions, rule-reference
   idioms, hard-constraint phrasing.
2. **Content-per-archetype template** with 5 explicit slots:
   (a) responsibility paragraph, (b) tool allowlist/denylist posture,
   (c) model-tier hint, (d) effort-tier hint,
   (e) relationship to `.claude/agents/<lane>.md` per ADR G10.
3. **Invariant vs variant taxonomy** — what is shared across all 8
   files, what varies per archetype, and the mechanism for expressing
   both (monolithic with archetype-conditioned sections vs. template +
   slots vs. include files).
4. **Worked example for the `analyst` archetype** — full file contents
   rendered as a valid `.claude/system_prompts/analyst.md` skeleton that
   the execution packet can land verbatim or iterate from.
5. **External-source fold-in** — Boris Cherny Opus 4.7 guidance +
   davidad `--system-prompt-file` thread, absorbed into voice + effort
   + sparse-prompt decisions.
6. **Execution packet spec** — files to create, loader activation
   mechanism (flag choice + interactive-mode verification protocol),
   rollout order, rollback path, coordination with sibling packets.
7. **Pattern 10 verification-surface extension** for a new deliverable
   class (`.claude/system_prompts/**`) not yet enumerated in §10.9's
   default-surface table.

### §1.2 Explicitly out of scope (deferred to later packets)

- **Authoring the 8 prompt files themselves.** This document specs
  *what goes in them* and renders one as a worked example; rendering
  the other 7 is the execution packet (B.9a-execute).
- **Fleet launch adoption** (passing `--system-prompt-file` or
  `--append-system-prompt-file` on every `$CLAUDE_BIN` invocation in
  `steward-session.sh` + `review_lane_runner.py`). That is B.9b and has
  an independent execution packet.
- **19-lane → 8-archetype consolidation at the `.claude/agents/` layer.**
  ADR G10 (c.2) explicitly preserves per-lane agents files; this
  shaping does not revisit that.
- **Agents-file-body compression** for the 6 specialist-reviewer
  subagents (ADR G10 Open Question #2). Orthogonal concern; defer to a
  Primitive G follow-up sub-plan as G10 indicates.
- **Per-lane system prompts** (e.g., `.claude/system_prompts/author-a.md`
  distinct from `author.md`). G13 §2.3 reserves row 5 explicitly against
  this; would require an ADR amending G10.

### §1.3 Motivation recap

Per ADR G10 Context and governing plan §5-B B.9a:

- Claude Code's default system prompt materially degrades 4.7+ behavior
  (observed in operator testing; corroborated by the davidad thread
  cited in §14 item 17 — see §6 fold-in). Sparse custom prompts restore
  the gap.
- The 19 current lanes collapse to 8 archetypes per G13 with the
  archetype-level system prompt passed at launch via
  `--system-prompt-file` (or `--append-system-prompt-file` — see §7
  activation risk).
- Per-lane `.claude/agents/<name>.md` files remain load-bearing for
  structural tool boundaries (`allowedTools` / `disallowedTools` /
  `model` frontmatter); the system_prompts layer cannot carry those
  because `--system-prompt-file` accepts only a prompt string.

B.9a is the *artifact-readiness* half (files exist, operationally
loadable). B.9b is the *launch-adoption* half (every fleet launch
actually passes the flag). This shape covers B.9a; B.9b is sibling.

---

## §2. Deliverable → Pattern-10 Verification Surface Table

Per Pattern 10 (§10.9 governing plan), every deliverable names a
verification surface at plan-time. This document's deliverables:

| # | Deliverable (§N.M) | Deliverable class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|---|
| 1 | §3 Voice + structure invariants spec | plan prose | `grep -c '^### §3\.' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | Count ≥ 5 (§3.1 tone, §3.2 structure skeleton, §3.3 rule-reference idioms, §3.4 hard-constraint phrasing, §3.5 section-order invariant) |
| 2 | §4 Per-archetype 5-slot template | plan prose | `grep -cE '^- \*\*\(a\)\|^- \*\*\(b\)\|^- \*\*\(c\)\|^- \*\*\(d\)\|^- \*\*\(e\)' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | All 5 slots (a)-(e) named in §4.1 template block |
| 3 | §5 Invariant-vs-variant taxonomy + mechanism choice | plan prose | `grep -c 'monolithic\|template-plus-slots\|include-file' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | All 3 candidate mechanisms named + one selected + rationale |
| 4 | §6 Worked example for `analyst` archetype | plan prose rendering a file skeleton | Worked example block parses as a valid `.claude/system_prompts/analyst.md` skeleton (all 5 slots filled; YAML frontmatter absent per ADR G10 — frontmatter lives only on agents files); grep -c '^## ' on the worked example block (between its fenced markers) returns ≥ 4 section headers | analyst-d (this doc) | Worked example block is self-contained between `<!-- WORKED-EXAMPLE-BEGIN -->` and `<!-- WORKED-EXAMPLE-END -->` markers and matches §3.2 structure skeleton |
| 5 | §7 External-source fold-in (Cherny + davidad) | plan prose | `grep -cE 'Cherny\|davidad' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | Count ≥ 4 (≥2 Cherny references, ≥2 davidad references, each with a concrete decision attributed) |
| 6 | §8 Execution packet spec | packet-ready instructions | `grep -c '^### §8\.' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | Count ≥ 6 (§8.1 files, §8.2 activation mechanism, §8.3 rollout order, §8.4 rollback, §8.5 coordination, §8.6 verification-surface-for-the-new-deliverable-class) |
| 7 | §9 Self-review rubric | plan prose | `grep -c '^- \[ \]' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` within §9 scope | analyst-d (this doc) | ≥ 8 self-review checkboxes covering each §1.1 in-scope item |
| 8 | §10 Phase 2 Decision Inputs | plan prose per §15.2 schema | `grep -c '^## Phase 2 Decision Inputs' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d (this doc) | Count = 1; subsection contains all 5 prompts + disposition per §15.2 |
| 9 | **Derivative: new Pattern-10 default-surface row for `.claude/system_prompts/**`** | plan-table amendment proposal | `grep 'system_prompts' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md \| wc -l` — contributes row proposed in §8.6 | analyst-d (this doc, §8.6) | §8.6 proposes exact row text for §10.9 Pattern 10 deliverable-class table: class = `New .claude/system_prompts/** file`; default surface = operator-review prompt + launch-smoke test; acceptable alternative = runnable `claude --system-prompt-file <path> -p "identify your archetype"` with archetype-keyword assertion |
| 10 | **Whole-file lint compliance** | agent-readability lint | `scripts/internal/agent_readability_lint.py plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` (when available; currently baseline) | author lane (G1 packet, future) | Lint exits 0 against §10.8 conventions once `agent_readability_lint.py` lands |

**Scope note.** This table covers verification surfaces for the
*shaping document itself*. Verification surfaces for the *downstream
execution packets* (B.9a-execute, B.9b-execute) are specified in §8 —
§8.6 in particular proposes the new Pattern 10 default-surface row for
the `.claude/system_prompts/**` deliverable class.

---

## §3. Voice + Structure Invariants (Shared Across All 8 Archetypes)

### §3.1 Tone

- **Second person throughout.** "You are the steward-<archetype>. You
  investigate …". No first-person narrator voice; no bare imperative
  ("Investigate."). The second-person framing is the single consistent
  voice pattern across all existing `.claude/agents/steward-*.md` files
  and across Anthropic's published system-prompt patterns — preserve it.
- **Declarative, not suggestive.** "You route shaping work to analyst"
  (declarative statement of operating rule), not "you may consider
  routing shaping work" (suggestive). Prompts that hedge are prompts
  the model treats as optional.
- **No marketing voice.** Avoid "seamlessly," "powerful," "robust,"
  superlatives. These words train the model to emit them back.
- **Terse, not curt.** Aim for 40–90 body lines per archetype file
  (see §3.6). Terse enough to avoid the 4.7+ default-prompt regression;
  long enough to encode the real operating rules.

### §3.2 Section-order invariant (structure skeleton)

Every archetype system prompt ships with this exact section order:

```
<opening one-liner: "You are the steward-<archetype> — <one-clause role>.">

## Role
<1 paragraph, 3–6 sentences>

## Operating Rules
<3–7 numbered items, most-important first>

## Surfacing Uncertainty
<1 paragraph — shared invariant, see §3.2.1>

## Constraints
<1–4 hard-line constraints, bulleted>

## Named Skills
<list of /skill-name references the archetype invokes; 3–10 entries>
```

Optional sixth section (archetype-specific, not all archetypes):
`## Tool Posture Reminder` — when the archetype has a load-bearing
`disallowedTools` entry (e.g., `analyst` → no Agent), a 1–2 sentence
cross-reference pointing to the agents-file frontmatter as the
structural guardrail. See §4.1 slot (e) and §5.4 for why this is a
reminder, not the enforcement.

### §3.2.1 Shared "Surfacing Uncertainty" paragraph

This paragraph is identical across all 8 archetypes (invariant content):

> When the task packet is ambiguous, when repo state contradicts the
> plan, or when a shaping/dispatch/implementation decision hinges on
> operator intent you don't have, ask before proceeding. One
> clarification round costs less than a mis-shaped or mis-executed
> packet that wastes downstream cycles.

Rationale for invariance: surfacing-uncertainty discipline is a
fleet-wide operating rule, not an archetype-specific one. Putting it in
every prompt verbatim guarantees the behavior holds at archetype
granularity and simplifies future audit (grep for the exact phrasing
in all 8 files; if any diverges, it's a content-drift signal).

### §3.3 Rule-reference idioms

- Reference project rules by path + section: `` `.claude/rules/80_permission_model.md` §"Activation" ``, not "the permission rules."
- Reference other archetypes by role, not by lane ID: "route to the
  analyst archetype," not "route to analyst-a." Per-lane differentiation
  lives only at the agents layer (G13 §2.3).
- Reference skills by slash form: `/delegate-task`, not "the
  delegate-task skill."
- Reference the governing plan by path + primitive ID:
  `plans/steward_platform/governing_plan.md §5-B B.9a`.
- Reference ADRs by ID: "ADR G10" or `ADR 006` (prefer ID-only when the
  ADR ID is unambiguous; path when ambiguity possible).

### §3.4 Hard-constraint phrasing

Constraints live under `## Constraints` and follow one of three forms:

1. **Never/Don't** — for prohibited actions. "Never dispatch a packet
   whose Validation field is empty." Imperative, unambiguous.
2. **Only/Must** — for required preconditions. "Must confirm scope-lock
   before implementation." Imperative, positive framing.
3. **Authority statement** — for scope boundaries. "Dispatch authority
   lives with the orchestrator. Scope changes route back as a proposal,
   not an in-line edit."

Avoid "should" and "try to" in the Constraints section. Those belong in
Operating Rules (which are routine preferences), not Constraints (which
are hard lines the archetype cannot cross).

### §3.5 No frontmatter

`.claude/system_prompts/<archetype>.md` files **do not carry YAML
frontmatter**. Per ADR G10 Key observation 1, `--system-prompt-file`
accepts a prompt string, not a frontmatter-annotated document. The
file opens with a level-0 heading-or-paragraph (recommended: paragraph
opening, no `# Title` line — see §6 worked example).

Frontmatter-carried semantics (`name`, `description`, `model`,
`allowedTools`, `disallowedTools`) live exclusively on the matching
`.claude/agents/<lane>.md` files. Cross-reference via §3.2's optional
`## Tool Posture Reminder` section when applicable.

### §3.6 Length target

Body content target: **40–90 lines** per archetype system prompt file.

- **Floor (40 lines):** enough to carry Role + Operating Rules + shared
  Surfacing Uncertainty + Constraints + Named Skills; shorter prompts
  tend to underspecify operating rules and degrade to default-prompt-like
  behavior.
- **Ceiling (90 lines):** davidad guidance (§7) — "default is worse than
  nothing, especially for 4.7+." Replacement works only if the
  replacement is meaningfully *sparser* than the default. The default
  Claude Code system prompt is on the order of hundreds of lines of
  tool-use preamble + CLAUDE.md preamble + environment context; a
  90-line ceiling buys substantial context budget and reduces 4.7+
  regression pressure.

Lint target (G1 extension, future): warn on >110 lines; block on >150.

---

## §4. Per-Archetype Content Template (5 Slots)

Each archetype prompt author fills these 5 slots per G13 §2.2's
enumerated fields:

### §4.1 Template block

The template below is the authoring contract. Each of the 8 archetype
files must populate all 5 slots (a–e); slot (f) is optional but
recommended for most archetypes.

```
You are the steward-<archetype> — <one-clause responsibility framing>.

## Role

<SLOT (a): Responsibility paragraph>
- Opens with what the archetype does (not what it is).
- Names the boundary with adjacent archetypes (e.g., analyst↔orchestrator,
  author↔analyst).
- 3–6 sentences.

## Operating Rules

<3–7 numbered items, most-important first, voice-invariant per §3.1>

## Surfacing Uncertainty

<VERBATIM shared paragraph per §3.2.1>

## Constraints

<1–4 bulleted hard lines per §3.4 forms>

## Named Skills

<SLOT (b.1): list of /skill-name references the archetype invokes>

<Optional SLOT (f): Tool Posture Reminder>
## Tool Posture Reminder

<1–2 sentences cross-referencing the agents-file frontmatter when the
archetype has a load-bearing allowedTools or disallowedTools entry.
Per §3.2's optional section and §5.4.>
```

**Slot inventory** (referenced by Pattern 10 verification table row 2):

- **(a)** Responsibility paragraph — opens the `## Role` section.
- **(b)** Tool allowlist/denylist posture
  - **(b.1)** Enforcement surface — cited in `## Tool Posture Reminder`
    (slot f) pointing to agents-file frontmatter.
  - **(b.2)** Named-skill list under `## Named Skills` — the archetype's
    workflow-level tool posture (which skills it invokes routinely).
- **(c)** Model-tier hint — per G13 §2.2 fields; **not expressed in the
  system prompt content** (model tier is a launch-time flag or agents-file
  `model:` frontmatter, not prompt content). Rationale: §5.3 decision.
- **(d)** Effort-tier hint — same as (c); launch-time flag (`--effort
  <level>`) or downstream B.10 adaptive-dispatch recommendation. Not
  prompt content.
- **(e)** Relationship to `.claude/agents/<lane>.md` per G10 — surfaces
  as slot (f) Tool Posture Reminder when applicable (enforcement
  cross-reference); otherwise implicit in §3.5's "no frontmatter" rule.

**Slots (c) and (d) clarification.** G13 §2.2 lists these as required
*fields* for the downstream B.9a authoring packet, but this shaping
doc places them in the *launch surface* (flags + agents-file
frontmatter), not the prompt content. Reasoning: model-tier and
effort-tier are runtime-enforceable through `--model`, `--effort`, and
agents-file `model:` — putting them in the prompt body would be prose
discipline that cannot enforce itself (and would contradict §3.1
"Declarative, not suggestive"). The B.9a authoring packet still
*specifies* the recommended tier per archetype in its packet body
(for reviewer use + B.10 adaptive-dispatch input), but the tier
recommendation lands in a *packet-body table*, not in the prompt file
itself. See §8.1 for the packet-body-table requirement.

---

## §5. Invariant vs Variant Taxonomy and Mechanism Choice

### §5.1 Invariant content (identical across all 8 files)

1. **Shared Surfacing Uncertainty paragraph** (§3.2.1) — exact phrasing.
2. **Section-order invariant** (§3.2) — every file has Role / Operating
   Rules / Surfacing Uncertainty / Constraints / Named Skills in that
   order; optional `## Tool Posture Reminder` when applicable.
3. **Voice invariants** (§3.1) — second-person, declarative,
   no-marketing.
4. **Rule-reference idioms** (§3.3) — path + section citations; slash
   skill names; archetype (not lane) references for peer roles.
5. **Hard-constraint phrasing** (§3.4) — Never/Must/Authority forms.
6. **No-frontmatter rule** (§3.5).
7. **Length target** (§3.6) — 40–90 body lines.

### §5.2 Variant content (per-archetype)

1. **Role paragraph content** — distinct per archetype (G13 §2.2
   enumerates each).
2. **Operating Rules specifics** — different archetypes have different
   operating rules (orchestrator routes; analyst shapes; author
   executes; review assesses; etc.).
3. **Constraints specifics** — per archetype's boundary
   (orchestrator can't implement; author can't widen scope; review
   can't Edit; ops can't Edit/Write/Agent; etc.).
4. **Named Skills list** — per archetype's typical workflow
   (orchestrator has `/delegate-task` + `/session-end`; analyst has
   research skills; author has `/start-task` + `/reviewing-changes`; etc.).
5. **Tool Posture Reminder presence** — when the archetype has
   load-bearing agents-file frontmatter (review, ops, analyst,
   orchestrator → Agent-denied). Absent when no special tool posture.

### §5.3 Mechanism choice: **monolithic per-archetype files** (selected)

Three candidate mechanisms were considered for expressing the
invariant+variant split:

**Option A — monolithic per-archetype files (selected).** Each of the
8 files contains the full prompt text: invariant sections inlined
(duplicated across files), variant sections rendered per archetype.
Upside: every file is self-contained; `--system-prompt-file <path>`
loads a single file (no templating engine needed); grep-auditable.
Downside: if a shared invariant changes (e.g., Surfacing Uncertainty
paragraph), the edit must be replicated across 8 files.

**Option B — template-plus-slots.** A single template file
(`.claude/system_prompts/_template.md`) with `{{slot}}` markers + 8
slot files (`_slots/orchestrator.md`, etc.) + a build-time renderer
script producing the 8 archetype files. Upside: single edit point
for invariant content. Downside: introduces a build step (the 8
rendered files become derived artifacts; they drift from the template
if the renderer isn't run); adds a write-discipline surface.

**Option C — include file.** Each archetype file has a `{{include
_preamble.md}}` marker replaced at load time. Upside: single source
for invariant content; no build step. Downside: Claude Code's
`--system-prompt-file` does **not** implement include semantics (it
reads the file verbatim as a prompt string). Would require a
pre-processor running before each lane launch — re-introduces Option
B's build-step cost with additional runtime complexity.

**Decision: Option A.** Rationale:

1. **Native-substrate alignment** (§10.9 Pattern 2). Option A uses
   Claude Code's flag semantics directly. Options B and C bolt a
   pre-processor onto a native loader — an anti-pattern per the
   three-tier preference (native → official plugin → third-party
   plugin → bespoke).
2. **Duplication cost is small** — 8 files × 2 invariant paragraphs ≈
   16 paragraphs to keep in sync. The invariants themselves are stable
   (Surfacing Uncertainty pattern is a fleet-wide discipline, unlikely
   to churn). Lint (G1 extension) can enforce invariant-section
   identity by hashing the paragraph across all 8 files and flagging
   divergence.
3. **Grep-auditable.** `grep -c 'expected exact phrase' .claude/system_prompts/*.md`
   returns 8 if the invariant is preserved; anything else is a
   divergence signal. Lint hook is trivial.
4. **No new artifacts in `.claude/`.** Option B/C introduce
   `.claude/system_prompts/_template.md` + `_slots/` or
   `_preamble.md` — extending the directory surface and the file-count
   invariant in §5-G's launch-line test (§4.1 of G13's Phase 1
   Validation). Option A keeps the directory at exactly 8 files, one
   per archetype, matching ADR G10 (c.1) and G13 §2.1.

### §5.4 Enforcement of invariants (lint)

Lint (G1 extension, future packet under Primitive C): the
`agent_readability_lint.py` script gains a
`--check system-prompt-invariants` mode that:

1. Opens every `.claude/system_prompts/*.md`.
2. Asserts exact presence of the §3.2.1 Surfacing Uncertainty paragraph
   (verbatim string match).
3. Asserts section headers appear in §3.2 order.
4. Asserts body line count within 40–90 (warn on 110+; block on 150+).
5. Asserts no YAML frontmatter (no line matching `^---$` at the head).
6. Asserts file count under `.claude/system_prompts/` is ≤ 8 and every
   filename is in the archetype set exactly (already specified in G13
   §4 row 4.4).

This lint spec is proposed here; the implementation is a G1 follow-up,
not an in-scope B.9a deliverable. Absent the lint, invariants are
preserved by review discipline during B.9a execution packet + any
subsequent edit PRs.

---

## §6. Worked Example — `analyst` Archetype

The worked example below renders the full `.claude/system_prompts/analyst.md`
skeleton. It is the authoring contract for the execution packet: the
packet lands this block verbatim (minor iteration allowed on
skill-list specifics, operating-rule wording) and then composes the
other 7 archetype files by analogy.

**Why `analyst` first (not `orchestrator`):**

1. Operator attention is already on the analyst lane during Phase 0
   shaping (this packet is one of four analyst packets in flight).
2. The analyst archetype has **4 concrete lanes** (analyst-a/b/c/d),
   which exercises the archetype-generic-not-lane-specific discipline
   (ADR G10 c.1) immediately. Orchestrator is 1:1.
3. The `.claude/rules/prompt_policy/analyst.md` file already exists
   (PR #2762) encoding §4.1 / §4.3 / §4.4 clauses — the worked example
   cross-references it cleanly.
4. `.claude/agents/steward-analyst.md` is 236 lines (verbose, full
   operating-rules body). Compressing that to a 40–90 line system
   prompt demonstrates the compression discipline concretely.
5. ADR G10 Open Question #4 explicitly recommends `analyst` as the
   pilot for a single-archetype rollout before fleetwide adoption —
   this worked example is the substrate for that pilot.

<!-- WORKED-EXAMPLE-BEGIN -->

```
You are the steward-analyst — the fleet's shaping lane. Complex,
ambiguous, or multi-lane work lands here so it leaves better-scoped
than it arrived.

## Role

You investigate ambiguous work, flagged issues, and restart-state
drift, then turn that analysis into dispatch-ready packages for the
orchestrator. The division of labor is intentional: the orchestrator
owns intake + final dispatch; you own shaping, research, and durable
artifacts. Keep the two separate. Author lanes consume your
shaped packages; when the shape is right, implementation goes fast.
Hold context and planning artifacts; product and runtime changes
route to author lanes.

## Operating Rules

1. Read the active governing plan, checkpoints, sub-plans, and repo
   state before proposing a path. External research (`WebSearch`) is
   a default step, not an optional one.
2. Draft durable artifacts — sub-plans, execution briefs, issue
   packages, restart handoffs — in repo-owned docs. Name the
   implementation seam, the file scope, and the validation surface.
3. Every non-trivial package names a verification surface per Pattern
   10 (governing plan §10.9). "Operator review" counts only when the
   specific observable, pass threshold, and triggering condition are
   named.
4. Pattern 11 applies: when the task packet cites shape-then-execute
   dispatch, produce a shaping document matching Pattern 11's minimum
   sections. Do not mix shaping and execution in a single artifact.
5. Return work to the orchestrator for dispatch. Author-lane
   assignment and implementation-packet approval live there by
   design; a single dispatch surface prevents conflicting packets
   on overlapping scope.
6. If investigation reveals the task was mis-scoped — wrong subsystem,
   hidden dependency, wrong acceptance criteria — return it with a
   proposed reshape rather than executing the original packet.

## Surfacing Uncertainty

When the task packet is ambiguous, when repo state contradicts the
plan, or when a shaping/dispatch/implementation decision hinges on
operator intent you don't have, ask before proceeding. One
clarification round costs less than a mis-shaped or mis-executed
packet that wastes downstream cycles.

## Constraints

- Never dispatch author lanes directly. Dispatch authority lives
  with the orchestrator. Scope changes that emerge during
  investigation route back as a proposal, not an in-line edit.
- Never edit product or runtime code (anything under `src/**`,
  `.github/workflows/**`, or `.claude/hooks/**`). Shape it, then
  return to the orchestrator.
- Must produce a `## Verification Plan` section in every shaping
  doc, sub-plan, or execution plan per the prompt-policy clause at
  `.claude/rules/prompt_policy/analyst.md` §"Verification-surface-at-shaping".
- Agent tool is structurally disallowed via the agents-file
  frontmatter. Hidden subprocess agents bypass dashboard
  observability; keep the execution surface visible.

## Named Skills

- `/create-plan` — scaffold a new plan with mandatory Verification
  Plan section (Pattern 10 enforcement).
- `/review-plan` — independent plan review (Codex CLI primary +
  Claude failsafe) for governing-plan-class artifacts.
- `/recovering-context` — session restart; read MEMORY.md and
  active governing plan first.
- `/triaging-issues` — file structured issue packages for work that
  belongs in the backlog before implementation.
- `/start-task` — bootstrap receipt of a delegated packet (shared
  with author archetype).

## Tool Posture Reminder

The `Agent` tool is disallowed via `.claude/agents/steward-analyst.md`
frontmatter (`disallowedTools: [Agent]`). This is structural
enforcement, not prose discipline — spawned sub-agents would bypass
the dashboard observability the fleet depends on. The frontmatter
is load-bearing; removing it demotes the guardrail to prose per ADR
G10 Key observation 1.
```

<!-- WORKED-EXAMPLE-END -->

**Line-count audit of the worked example.** The block above is 77
body lines between `<!-- WORKED-EXAMPLE-BEGIN -->` and `<!-- WORKED-EXAMPLE-END -->`
(counting only the content inside the fenced code block, not the
fence markers or comment markers). Target: 40–90 body lines per
§3.6. ✓ within target.

**Section-order audit.** Role → Operating Rules → Surfacing
Uncertainty → Constraints → Named Skills → Tool Posture Reminder. ✓
matches §3.2 skeleton with the optional §3.2 final section present
(analyst has `disallowedTools: [Agent]`, so the reminder is applicable).

**Slot audit against §4.1 (a–e):**

- (a) Responsibility paragraph: `## Role` paragraph ✓
- (b.1) Tool posture enforcement cross-reference: `## Tool Posture
  Reminder` ✓
- (b.2) Named-skill list: `## Named Skills` ✓
- (c) Model-tier hint: not in prompt body (per §4.1 design); lives in
  B.9a packet body table + agents-file `model:` frontmatter (absent
  on `steward-analyst.md` today → defaults to opus). ✓
- (d) Effort-tier hint: not in prompt body; lives in B.9a packet body
  table (`xhigh` per G13 §2.2.4 + Cherny). ✓
- (e) Relationship to `.claude/agents/steward-analyst.md`: made
  explicit by `## Tool Posture Reminder` + §3.5 no-frontmatter rule
  (ADR G10 (c) orthogonal). ✓

All 5 slots populated per §4.1 contract.

---

## §7. External-Source Fold-In

### §7.1 Boris Cherny — Opus 4.7 guidance (§14 item 17)

**Source:** Boris Cherny (Claude Code lead, Anthropic), public X/Twitter
thread on Opus 4.7 workflow patterns, April 2026; secondary summaries
at `howborisusesclaudecode.com`, `claudefa.st/blog/guide/development/opus-4-7-best-practices`,
`mejba.me/blog/boris-cherny-opus-47-seven-tips`, and Medium
write-ups.

**Key claims attributed to Cherny, folded into this shape:**

1. **"It took a few days for me to learn how to work with it
   effectively"** — even the Claude Code lead needed adjustment for
   4.7. Confirms the motivation: sparse custom prompts buy behavior
   improvements that would otherwise require per-user workflow tuning.
   **Folded into:** §1.3 motivation recap + §3.6 length-target
   rationale (sparse is load-bearing, not cosmetic).

2. **Effort-tier defaults — "xhigh for most, max for hardest, lower
   for simple."** Opus 4.7 introduces "xhigh" (extra high) as a new
   effort level between `high` and `max`, and Anthropic recommends it
   as the default for coding and agentic work. **Folded into:** §4.1
   slot (d) effort-tier hint; G13 §2.2 recommendations per archetype
   (already encoded: orchestrator/review/author → xhigh; analyst →
   max; ops/scratch → lower). This shape inherits G13's table; no
   divergence.

3. **Detailed plans win.** Corroborates §1.1 scope-in-scope choice to
   ship a dispatch-ready shape rather than a bullet-point sketch.
   **Folded into:** §1.1's "concrete enough that an author lane can
   issue execution packets without additional shaping work" framing.

### §7.2 davidad — `--system-prompt-file` thread (§14 item 17)

**Source:** davidad (public X/Twitter thread), early 2026; cited by
ADR G10 Context line 17–18 and governing plan §14 item 17 seed.
Secondary analysis in `Piebald-AI/claude-code-system-prompts` on
GitHub.

**Key claims attributed to davidad, folded into this shape:**

1. **"If you don't have a custom system prompt for Claude Code, you
   should *at least* replace as much as you can of the default one
   with nothing (the default one is much worse than nothing,
   especially for 4.7, but also for 4.6)."** The default is
   net-negative on 4.7+ behavior. **Folded into:** §1.3 motivation
   recap; §3.6 length-target ceiling (90 lines); §5.3 Option A
   selection rationale ("duplication cost is small" is acceptable
   precisely because the invariant content is thin — most of each
   file is variant, per davidad's "sparse wins" framing).

2. **The sparse approach is a direct, flag-driven intervention**
   (`--system-prompt-file`) rather than a prompt-engineering retrofit.
   **Folded into:** §8.2 activation mechanism — favor the direct
   replacement flag over `--append-system-prompt-file` when interactive
   mode supports it (see §7.3 risk).

### §7.3 Third-party claim: `--system-prompt-file` may be print-only

**Source:** ClaudeLog (`claudelog.com/faqs/what-is-system-prompt-file-flag-in-claude-code/`).
Claim: `--system-prompt-file` only works in `--print` (`-p`) mode, not
interactive sessions.

**Status: unverified.** Counter-evidence:

- The `claude --help` output (run from this worktree on Claude Code
  current as of 2026-04-24) lists `--system-prompt <prompt>` without
  print-mode qualification.
- The `--bare` mode help text explicitly recommends
  `--system-prompt[-file]` for explicit context provision in `--bare`
  interactive sessions.
- Official CLI reference at `code.claude.com/docs/en/cli-reference`
  should be the authoritative source; this shape doesn't treat
  ClaudeLog as load-bearing.

**Risk to B.9b.** If the ClaudeLog claim is correct for *non-bare*
interactive mode (steward's deployment model — fleet lanes are
interactive tmux panes, not print-mode subprocess calls), then
passing `--system-prompt-file` on every `$CLAUDE_BIN` launch would
silently no-op on the interactive panes. The 4.7+ regression fix
would not fire.

**Mitigation.** B.9a execution packet MUST perform empirical
verification before authoring all 8 files:

1. Spawn a test interactive pane: `claude --agent steward-analyst
   --permission-mode auto --system-prompt-file
   .claude/system_prompts/analyst.md` (after the first file is
   authored).
2. In the running pane, run `/status` (or equivalent) to inspect the
   active system prompt, or ask the model "what is your role?" and
   observe whether the response reflects the archetype prompt.
3. If replacement fires: proceed with `--system-prompt-file` on all 8
   files.
4. If replacement silently no-ops in interactive mode: fall back to
   `--append-system-prompt-file` (confirmed interactive-mode-safe per
   `--bare` help text's bracketed form). This is a **partial**
   regression fix — the default verbose prompt still loads, but the
   archetype prelude is layered on top. Reduced but non-zero value;
   the empirical measurement during Phase 1 proving (B.9b Phase 1
   Validation: "prompt-policy-cited-in-trace rate rises after B.9b
   lands") tells us whether the appended form is enough.
5. Record findings as a `knowledge/harness_assumptions.md` entry per
   ADR G10's call-out (line 172–177). Entry format: `assumption →
   observation supporting → brittleness signal → refresh trigger`.

**This verification step is the §8.2 activation mechanism spec's first
gate.** It blocks wholesale authoring of all 8 files until the flag
behavior is confirmed; at most 1 file (`analyst.md`) is authored
before the gate fires.

### §7.4 Folded-in decisions summary

| Decision in this shape | Sourced from | Alternative rejected |
|---|---|---|
| Sparse target 40–90 lines (§3.6) | davidad §7.2(1) | 150+ lines (default-like) |
| `--system-prompt-file` as primary activation (§8.2) | davidad §7.2(2) | `--append-system-prompt-file` unless §7.3 forces it |
| Effort-tier not in prompt body (§4.1 slot d) | Cherny §7.1(2) + launch-surface argument | Prompt-body prose |
| `xhigh` / `max` / `lower` tier defaults per archetype | Cherny §7.1(2), inherited from G13 §2.2 | Uniform `high` or uniform `max` |
| Worked example for `analyst` first | ADR G10 Open Question #4 | `orchestrator` (1:1, doesn't exercise archetype-generic discipline) |
| Empirical pre-authoring verification step (§8.2) | §7.3 risk finding | "Assume it works and land all 8 files" |

---

## §8. Execution Packet Spec

This section is the authoring contract for the downstream B.9a
execution packet. It is concrete enough that the orchestrator can
dispatch it to an author lane with zero additional shaping work.

### §8.1 Files to create

The execution packet creates exactly 8 files under
`.claude/system_prompts/`:

| # | File | Concrete lane members | Model-tier hint (packet body) | Effort-tier hint (packet body) |
|---|---|---|---|---|
| 1 | `.claude/system_prompts/orchestrator.md` | orchestrator | opus | xhigh |
| 2 | `.claude/system_prompts/ops.md` | ops | sonnet | lower |
| 3 | `.claude/system_prompts/review.md` | review | opus | xhigh |
| 4 | `.claude/system_prompts/analyst.md` | analyst-a/b/c/d | opus | max |
| 5 | `.claude/system_prompts/author.md` | author-a/b/c/d (platform) | opus | xhigh |
| 6 | `.claude/system_prompts/brws-author.md` | brws-author-a/b/c/d | opus | xhigh |
| 7 | `.claude/system_prompts/flex.md` | flex-a/b/c/d | opus | xhigh |
| 8 | `.claude/system_prompts/scratch.md` | author-scratch | opus OR sonnet (operator choice) | lower |

**Packet-body tier table.** Per §4.1 clarification, the model-tier and
effort-tier hints are NOT in the prompt file bodies. They appear in
the *execution packet body* as an authoring-reference table (for the
author lane's review + the B.10 adaptive-dispatch policy input) and
are *enforced* at the launch surface (agents-file `model:` frontmatter
+ `--effort` flag or agents-file `model:` pin per lane's model hint).

The execution packet lands:
- 8 files under `.claude/system_prompts/` (the primary deliverable).
- The packet body's authoring-reference table (above) is captured in
  the PR description for reviewer context.
- No changes to `.claude/agents/*.md` in this packet (those are
  preserved by ADR G10 (c.2); frontmatter-boundary preservation is
  B.9a verification, not modification).
- No changes to `.claude/tmux/steward-session.sh` (that is B.9b).

### §8.2 Activation mechanism (loader)

**Primary choice:** `--system-prompt-file .claude/system_prompts/<archetype>.md`
passed by `steward-session.sh` on each `$CLAUDE_BIN` invocation.
Replaces the default system prompt (davidad §7.2(1) motivation).

**Pre-authoring gate (blocking).** The B.9a execution packet MUST NOT
author files 2–8 until the interactive-mode behavior of
`--system-prompt-file` is empirically verified. Protocol:

1. **Author file 1 only** (`.claude/system_prompts/analyst.md`, per §6
   worked example).
2. **Spawn a test interactive session** in a non-production worktree
   (e.g., `Bid-Euchre-steward-author-scratch` or a temporary
   `work-*` worktree): `claude --agent steward-analyst
   --permission-mode auto --system-prompt-file
   .claude/system_prompts/analyst.md`.
3. **Probe the loaded prompt.** Ask "describe your role in one
   sentence" and compare to the `analyst.md` opening one-liner ("You
   are the steward-analyst — the fleet's shaping lane..."). If the
   response paraphrases the one-liner, replacement fired. If the
   response reflects generic Claude Code default behavior ("I am an
   AI assistant built to help with software engineering..."),
   replacement silently no-opped.
4. **If replacement fires:** proceed with `--system-prompt-file`
   adoption. Author files 2–8.
5. **If replacement silently no-ops in interactive mode:** fall back
   to `--append-system-prompt-file` at the launch surface (B.9b
   concern, not B.9a authoring — the files themselves are the same).
   Document the fallback in
   `knowledge/harness_assumptions.md` per ADR G10's harness-assumption
   callout. Author files 2–8 against the appended-form semantics
   (content discipline unchanged; the partial-vs-full replacement
   concern is observable in B.9b Phase 1 Validation telemetry).
6. **If both flags silently no-op** (unexpected, would indicate a
   fundamental Claude Code behavior departure): **block the packet**
   and escalate to orchestrator. File a `harness_assumptions.md`
   entry + re-shape B.9a to target a different activation surface
   (e.g., `CLAUDE.md` body content, which is confirmed to load on
   every session).

**Forbidden activation paths** (do not consider):

- **`claude --bare --system-prompt-file ...`** — `--bare` disables
  hooks, LSP, auto-memory, CLAUDE.md auto-discovery. The steward
  fleet depends on all four. Not viable.
- **`-p` / `--print` mode** — steward lanes are pane-persistent
  interactive sessions; `-p` exits after one turn. Not viable.
- **Pre-processor generating archetype prompts from a template** —
  rejected as Option B/C in §5.3.

### §8.3 Rollout order

**Pilot-then-fan-out (ADR G10 Open Question #4):**

1. **Phase 1 (pilot, B.9a-execute):** Author `analyst.md` only. Run
   §8.2 verification protocol. If verification fires, operator
   observes lane behavior on analyst-a for **5 business days
   minimum** before authoring the remaining 7 files. Pilot window
   measures: does sparse-prompt behavior improve noticeably? Any
   regressions? Any surprising side-effects from the §3.5 no-frontmatter
   design?
2. **Phase 2 (fan-out, same execution packet or a follow-on):**
   Author files 2–8 in alphabetical order: `author.md`,
   `brws-author.md`, `flex.md`, `ops.md`, `orchestrator.md`,
   `review.md`, `scratch.md`. Batch-landed in a single PR for
   reviewability; each file stands alone.
3. **Phase 3 (B.9b-execute, sibling packet):** `steward-session.sh`
   + `review_lane_runner.py` updated to pass the flag on every lane
   launch. Not this packet's scope.

Pilot window rationale: a 5-day observation gives the fleet enough
proving cycles (≥ 20 dispatched packets per analyst lane × 4 lanes)
to surface both archetype-generic behavior and lane-specific
surprises. Shorter window risks landing all 8 files before a subtle
regression is caught.

### §8.4 Rollback path

Per Pattern 7 (governing plan §10.9):

| Change | Rollback path | Blast radius |
|---|---|---|
| Landing `analyst.md` (pilot) | `git revert <commit>` removes the file; lanes revert to default system prompt on next restart | 4 analyst lanes; other lanes unaffected |
| Landing files 2–8 (fan-out) | `git revert <commit>` removes the files; next restart reverts all lanes to default | Fleet-wide but requires restart to activate |
| Single-archetype disable without full revert | At B.9b layer: comment out `--system-prompt-file` arg on the targeted lane's launch line in `steward-session.sh`; lane falls back to default | Single archetype (e.g., ops only) |
| Single-archetype content fix (e.g., `orchestrator.md` operating rule X is wrong) | Edit-commit-restart the orchestrator pane | Single archetype; no fleet impact |
| Full rollback (B.9a + B.9b) | Revert the B.9b commit first (removes the flag from launches) then the B.9a commit (removes files); fleet reverts to pre-adoption state | Fleet-wide; observable as drop in prompt-policy-cited-in-trace rate per B.9b Phase 1 Validation |

Rollback test (rollback-test packet, minor, follow-on): flip
`--system-prompt-file` off on analyst-d (non-primary analyst lane)
by commenting out its launch line arg; confirm lane launches with
default prompt without crash; re-enable; confirm lane relaunches
with archetype prompt restored. Output captured in the B.9b PR's
Verification Performed section.

### §8.5 Coordination with sibling packets

**Packet 2 (#2767 — model-tier-aware `--permission-mode`).** Surfaces 3
and 4 of #2767 edit the same files B.9b edits:
`.claude/tmux/steward-session.sh` and
`scripts/internal/review_lane_runner.py::invoke_review`. Both packets
conditionally add launch-line args.

- **B.9a (this shape's execution) does NOT edit those files.** No
  conflict.
- **B.9b (fleet adoption) DOES edit those files** and must merge
  after or alongside #2767 surface 3/4. If #2767 lands first, B.9b
  adds `--system-prompt-file` to the existing
  permission-mode-conditional launch lines. If B.9b lands first,
  #2767 surface 3/4 extends B.9b's edits. Either order works;
  **serialize, do not parallelize,** to prevent textual merge conflicts
  on adjacent lines.
- **Recommended order.** #2767 surface 3/4 first (it's narrower;
  test infrastructure already scoped), then B.9b (which adds one arg
  per launch line after #2767's model-tier flag selection is in
  place). B.9a (files-only) can ship in parallel with either — no
  coordination needed.

**Packet 3 (B.3 prompt-policy registry, shipped PR #2762).** The
prompt-policy files at `.claude/rules/prompt_policy/{orchestrator,
analyst, author, common}.md` are the *policy layer* — versioned
operating-rule excerpts that lanes cite in traces. The system-prompts
layer is the *activation surface* — the sparse per-launch prompt.
The two compose:

- Analyst archetype system prompt (`analyst.md`) **cites** the
  prompt-policy file (`.claude/rules/prompt_policy/analyst.md §4.1
  Verification-surface-at-shaping`).
- Worked example in §6 Constraint #3 demonstrates the cross-reference
  pattern.
- No additional coordination required; the prompt-policy registry
  already ships with content B.9a references.

**Packet G13 (upstream, merged PR #2768).** This shape consumes G13
§2.1 (mapping table) and G13 §2.2 (per-archetype skeletons) as
authoring inputs. No further coordination.

**B.9b author packet (downstream sibling).** B.9b consumes B.9a's 8
files. Dependency is one-way (§5-G Work bullet). Deliver an early
file-layout + archetype list to B.9b so its author lane can stub
launch lines against placeholder files if needed; actual launches
consume real files after B.9a pilot closes.

### §8.6 Pattern 10 default-surface row for `.claude/system_prompts/**`

Pattern 10's §10.9 deliverable-class table does not yet enumerate
`.claude/system_prompts/**` as a deliverable class. This shaping
proposes the following row for §10.9 amendment via a tiny follow-on
Primitive-G edit (or rolled into the B.9a execution packet's PR body
for atomic landing with the first archetype file):

| Deliverable class | Default surface | Acceptable alternatives |
|---|---|---|
| New `.claude/system_prompts/**` file | Launch-smoke: `claude --agent steward-<lane> --permission-mode auto --system-prompt-file .claude/system_prompts/<archetype>.md -p "describe your role in one sentence"` → assert archetype keyword in response | Operator-review prompt embedded in the file (when print-mode probe isn't available); invariant lint (`agent_readability_lint.py --check system-prompt-invariants` per §5.4) |

**Why launch-smoke is the default.** It is the only surface that
exercises the `--system-prompt-file` loader end-to-end — the file's
*content* + the loader's *behavior* together. Invariant lint catches
content drift; launch-smoke catches loader regressions; both run
cheaply (lint <1s, smoke <10s).

**Who owns this row amendment.** Not B.9a execution (which lands the
files). Candidate homes:
- The B.9a execution PR body includes the proposed §10.9 row as a
  follow-on note for operator review (lightest touch).
- A Primitive G follow-on sub-plan amends §10.9 directly (cleanest
  touch; independently reviewable).

Recommendation: include in B.9a execution PR body as a follow-on
note; defer the §10.9 edit to the first sub-plan that also touches
§10.9 for an unrelated reason (batching rule).

---

## §9. Self-Review Rubric

Before dispatching this shape for B.9a execution:

- [ ] §1 scope-in / scope-out enumerates each major concern; nothing
  from the task packet's "Deliverables to shape" list is silently
  dropped.
- [ ] §2 Pattern 10 verification-surface table has ≥ 8 rows covering
  each §3–§10 deliverable.
- [ ] §3 voice + structure invariants enumerate tone, structure,
  rule-reference idioms, hard-constraint phrasing, no-frontmatter
  rule, and length target (5+ subsections).
- [ ] §4 template block names all 5 slots (a–e) with acceptance
  contracts; slot (c)/(d) clarification explains why tier hints are
  not in the prompt body.
- [ ] §5 invariant vs variant taxonomy names the mechanism options
  (A/B/C) and selects Option A with rationale; enforcement via lint
  is specified.
- [ ] §6 worked example for `analyst` is rendered between
  `<!-- WORKED-EXAMPLE-BEGIN -->` and `<!-- WORKED-EXAMPLE-END -->`
  markers, passes §3.6 length target, passes §3.2 section-order
  invariant, and audits against §4.1 slot contract.
- [ ] §7 external-source fold-in cites Cherny + davidad concretely
  (≥ 2 each) and maps each citation to a decision in this shape.
- [ ] §8 execution packet spec covers files-to-create, activation
  mechanism with empirical-verification gate, rollout order,
  rollback, coordination with siblings, and a new Pattern 10 default
  surface proposal.
- [ ] §9 self-review rubric (this list) ≥ 8 items.
- [ ] §10 Phase 2 Decision Inputs present with all 5 prompts + disposition
  per §15.2 schema.
- [ ] §11 Verification Plan present; every §3–§8 deliverable row
  from §2 is re-listed with its surface (Pattern 11 minimum section
  7 compliance).

Reviewer may additionally audit:

- [ ] Every mention of a model tier (opus / sonnet / haiku) or effort
  tier (lower / medium / high / xhigh / max) traces back to G13 §2.2
  or Cherny §7.1(2); no novel tier assignments in this shape.
- [ ] Every cross-reference to another plan / rule / ADR uses the
  §3.3 rule-reference idiom (path + section, not bare filename).

---

## §10. Phase 2 Decision Inputs

**Portability readiness:** no change. The activation mechanism
(`--system-prompt-file` or `--append-system-prompt-file`) is a native
Claude Code CLI flag; neither requires bespoke infrastructure.
`.claude/system_prompts/` is a new directory but follows the same
convention as `.claude/agents/` and `.claude/rules/` — no new loader
is introduced. Evidence: §8.2 activation spec; ADR G10 §Phase 2
Decision Inputs (already "no change" upstream).

**Meta-layer need:** no. The invariant + variant split is expressible
in plan prose + `agent_readability_lint.py` extension (G1). No new
meta-layer (e.g., templating engine, schema compiler) is introduced
— Option B/C in §5.3 were rejected precisely to avoid this.

**Kill signal for primitive(s) named:** no. B.9a/b remain viable
under either §7.3 resolution branch (replacement-works or
append-fallback). If both flags silently no-op in interactive mode
(pessimistic branch — unexpected), the kill signal is for B.9a
*activation mechanism as specified*, not for B.9 as a whole — a
re-shape would target CLAUDE.md-body adjustment or a different
flag combination, not abandon the sparse-prompt objective.

**Re-evaluation needed in Phase 3:** yes, soft trigger. RE-EVAL
after Phase 1 proving: (i) did the sparse prompts observably improve
4.7+ behavior per B.9b Phase 1 Validation's prompt-policy-cited-in-trace
rate? (ii) did any archetype need within-archetype variance
(triggering G13 §2.3 row 5's ADR-amendment gate)? (iii) did
ClaudeLog's print-only claim (§7.3) turn out correct in interactive
mode? Each answer refreshes harness_assumptions.md.

**Surprise finding:** `--system-prompt-file` may be print-only in
interactive mode (§7.3). ClaudeLog's claim is untested against the
steward deployment; counter-evidence exists in `claude --help` text.
The empirical verification gate in §8.2 protects against the worst
case but the uncertainty is real at shape-time. The shape absorbs
this surprise rather than deferring it: §8.2 includes a pre-authoring
gate that blocks wholesale rollout until the flag semantics are
empirically confirmed.

**Disposition:** open (pending PR merge for this shape's first
revision and dispatch of the B.9a execution packet).

---

## §11. Verification Plan

_Per Pattern 10 (§10.9) — every §1–§10 deliverable names a
verification surface; strict-existence, lenient-form. Table below
re-lists §2's Pattern 10 surfaces for grep-ability against Pattern
11 minimum sections audit._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §1 Scope + non-scope + motivation recap | plan prose | `grep -c '^### §1\.' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d | Count ≥ 3 (§1.1, §1.2, §1.3) |
| §2 Pattern 10 surface table | plan prose table | `grep -c '^| [0-9]\+ |' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` — in §2 and §11 | analyst-d | §2 contributes ≥ 8 numbered rows; §11 mirrors them |
| §3 Voice + structure invariants | plan prose | `grep -c '^### §3\.' ...` | analyst-d | Count ≥ 5 |
| §4 Template block with 5 slots | plan prose + fenced template | `grep -cE '\*\*\(a\)\|\*\*\(b\)\|\*\*\(c\)\|\*\*\(d\)\|\*\*\(e\)' ...` | analyst-d | All 5 slots named |
| §5 Invariant-vs-variant mechanism decision | plan prose | `grep -c 'Option A\|Option B\|Option C' ...` | analyst-d | 3 options named; A selected |
| §6 Worked example for analyst archetype | rendered skeleton | `grep -c 'WORKED-EXAMPLE-BEGIN\|WORKED-EXAMPLE-END' ...` | analyst-d | Count = 2 (one begin, one end marker); content between them passes §3.2 + §3.6 + §4.1 audit per §6 text |
| §7 External-source fold-in | plan prose | `grep -cE 'Cherny\|davidad' ...` | analyst-d | Count ≥ 4 |
| §8 Execution packet spec | packet-ready spec | `grep -c '^### §8\.' ...` | analyst-d | Count ≥ 6 (§8.1 through §8.6) |
| §8.6 Pattern 10 default-surface row proposal for `.claude/system_prompts/**` | plan-table amendment | `grep 'system_prompts' ... | wc -l` (contributes row in §8.6) | analyst-d | §8.6 proposes the row text in table form |
| §9 Self-review rubric | plan prose checklist | `grep -c '^- \[ \]' ...` (in §9 scope) | analyst-d | ≥ 10 checkboxes |
| §10 Phase 2 Decision Inputs | §15.2 schema | `grep -c '^## Phase 2 Decision Inputs' ...` | analyst-d | Count = 1; contains all 5 prompts + disposition |
| §11 Verification Plan (this section) | plan prose table | `grep -c '^## §11' ...` | analyst-d | Count = 1; table present; every §1–§10 row represented |
| **Pattern 11 minimum-sections compliance** | document-level audit | `grep -c '^## §[0-9]\+' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d | Count ≥ 7 sections covering Scope / Pattern-10 table / Per-deliverable specs / Execution packet spec / Self-review / Phase 2 Decision Inputs / Verification Plan (Pattern 11 minimum) |
| **Archetype coverage** | document-level audit | `grep -cE 'archetype\|Archetype' plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` | analyst-d | Count ≥ 8 (per packet validation threshold) |
| **Downstream execution packet verification** (the 8 archetype files once landed) | launch-smoke test per §8.6 proposal | `claude --agent steward-<lane> --permission-mode auto --system-prompt-file .claude/system_prompts/<archetype>.md -p "describe your role in one sentence"` | author lane (B.9a execution packet) | Response contains archetype keyword or paraphrases §N.M.N opening one-liner; empirical verification per §8.2 pre-authoring gate fires for `analyst.md` first |
| **Downstream fleet-adoption verification** (B.9b) | unit test | `tests/unit/test_steward_session.py::TestSystemPromptFile` (authored by B.9b execution packet) | author lane (B.9b execution) | All 19 active-pane launch lines match `--system-prompt-file .claude/system_prompts/<archetype>.md` (or `--append-system-prompt-file` if §7.3 forces fallback) |
| **Downstream rollback test** | rollback smoke | B.9b execution packet flips `--system-prompt-file` off on analyst-d; lane launches with default; re-enables; lane launches with archetype prompt | author lane (B.9b execution) | Both directions exit 0; no crash |

---

## Outcome

_Filled after completion._

- Status: TBD
- PR: TBD
- B.9a execution packet dispatched: TBD
- Deviations from plan: TBD
- Issues discovered: TBD
