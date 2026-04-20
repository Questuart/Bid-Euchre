# Agent System Prompt Refresh — Valued-Teammate Migration Plan
**Date:** 2026-04-20
**Goal:** Shape a phased migration from command-heavy `.claude/agents/*.md` system prompts to collaborative, context-rich framings that treat Claude as a capable teammate — without changing tool frontmatter, model assignments, or fleet structure.

**Parent issue:** #2677 ("Refresh agent system prompts as valued teammates")
**Delivery mode:** Plan document (PR) + summary comment on #2677 (hybrid — see task packet `887fd7ee47e6`).
**Analyst lane:** `steward-analyst-d`. This is a shaping artifact; implementation is out of scope for this packet.

---

## Summary and Motivation

The fleet currently runs 22+ lane prompts in `.claude/agents/*.md`. A structural inventory (detailed below) found **123 negative-instruction tokens** (`MUST` / `NEVER` / `DO NOT` / `Do not` / `do not` / `NOT` / `Never` / `must`) across 23 files, versus **~5 collaborative keywords** (`we` / `teammate` / `colleague` / `partner` / `collaborate` / `ask help` / `surface uncertainty` / `if unsure` / `when in doubt` / `push back` / `escalate`) across 3 files — a **~24:1 command-to-collaboration ratio**. Eleven author-lane prompts (platform authors a–d, brws-authors a–d, flex a–c) share ~85% identical text, meaning any prompt change today either drifts across copies or requires coordinated edits to eleven files.

The operator's hypothesis, documented in #2677, is that Anthropic's published guidance treats Claude as a capable collaborator, and fleet prompts drifted away from that stance over time as individual issues added guardrails ("MUST do X", "NEVER touch Y"). Each guardrail was individually reasonable; the accumulated effect is a tone that reads as mistrust. This plan grounds the hypothesis in external research, proposes principles, and sequences a safe migration — it does **not** rewrite any prompts.

**Why this matters now (not later):**
- Fleet is stable post-Platform-10; extraction-ready state is a natural pause point for hygiene work.
- Messaging revamp is in flight (see sibling 2026-04-20 plans); prompt refresh is adjacent but independent and should not block on it.
- The duplication problem across 11 author lanes is actively costing us: any lane-prompt bugfix today requires editing 11 files.

---

## Research Findings (Plan-Relevant)

Full citations in the §References block. Key points that drove the principles:

1. **Anthropic explicitly endorses the "capable teammate" framing.**
   > "Think of Claude as a brilliant but new employee ... who needs explicit instructions. Like any new employee, Claude does not understand our norms, preferred tools, or what is or is not OK to say."
   — Anthropic Prompting Best Practices

   This validates treating Claude as competent-but-new-to-this-repo, not as an untrusted tool that needs constant negation.

2. **Anthropic explicitly warns against aggressive negative instructions.**
   > "Dial back any aggressive language. Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting like 'Use this tool when...'"
   — Anthropic Prompting Best Practices

   This is a direct match for the pattern we see most in our prompts (e.g., orchestrator's "The orchestrator must NOT..." list).

3. **Positive framing outperforms negative framing.**
   > "Tell Claude what to do instead of what not to do."
   > Less effective: `NEVER use ellipses`
   > More effective: instruction that explains *why* and what to do instead.
   — Anthropic Prompting Best Practices

4. **Uncertainty-surfacing is an Anthropic-trained safety property, not a prompt hack.**
   > "We train Claude to ask clarifying questions when facing ambiguous tasks ... Training models to recognize their own uncertainty and surface issues to humans proactively is an important safety property."
   — Anthropic research, measuring-agent-autonomy

   Our current prompts rarely grant this affordance explicitly (only ops, repair, and analyst use any form of "escalate if unsure"). Making it explicit across lanes aligns our prompts with Claude's training.

5. **Prompt politeness has a measurable but non-monotonic effect on LLM performance.**
   ACL 2024 ("Should We Respect LLMs?") found that impolite prompts degrade task performance across languages, while overly polite prompts do not guarantee improvement — there is a "sweet spot" and it is language- and task-specific. This is the strongest published evidence that command-heavy prompts carry real cost, but it is also a caution against over-correcting into flowery language.

6. **No peer-reviewed evidence that command capitalization ("MUST", "NEVER") measurably improves instruction compliance for modern frontier LLMs.** Absent positive evidence, Anthropic's own guidance against aggressive framing is the load-bearing source.

---

## Current-State Inventory (Summary)

Full per-file notes were captured during research. Headline numbers:

| Bucket | Files | Negation tokens | Collab tokens | Notes |
|--------|-------|-----------------|---------------|-------|
| Orchestrator | 1 | ~13 | 0 | "The orchestrator must NOT..." list is the sharpest command block. |
| Ops | 1 | 1 | 2 | Shortest + most collaborative. Good baseline. |
| Review | 1 | 9 | 0 | Strong autonomy grant ("you have full authority") is a good pattern; rest is command-framed. |
| Analyst (this lane) | 1 | 11 | 1 | "Research Protocol", "When To Use / When Not To Use" are good patterns. |
| Repair | 1 | 13 | 1 | Explicit stop rules are a good escalation pattern; dominant tone is command. |
| Plan reviewer | 1 | 4 | 0 | Rubric-based (P1–P16). Low command density, strong structure. Good pattern. |
| Specialist reviewers (correctness/coverage/architecture) | 3 | ~4 each | 0 | "HARD SCOPE CONSTRAINT" pattern is focus-enhancing but command-framed. |
| Blind comparator | 1 | low | 0 | "Do NOT guess which strategy is which" is anti-cheating, legitimate use. |
| Authors (platform a–d) | 4 | ~5 each | 0 | ~92% identical. Duplication is the primary problem here, not tone. |
| Authors (brws a–d) | 4 | ~5 each | 0 | ~95% identical to each other; ~90% identical to platform authors. |
| Flex (a–c) | 3 | ~5 each | 0 | ~100% identical except lane name. |
| Author-scratch | 1 | ~3 | 1 | Softer ("treat this lane as disposable"). |

Totals: **123 negation tokens / 23 files**, **~5 collaborative tokens / 3 files**. Ratio ≈ 24:1.

**Good patterns to preserve across the migration:**
- Ops: "Distinguish observed facts from inferred state when reporting status."
- Review: "You have full authority to create GitHub issues — this is your primary function. Do not ask for confirmation." (autonomy grant)
- Analyst: "Research Protocol" step; "When To Use / When Not To Use" meta-framing.
- Repair: explicit stop-and-escalate triggers.
- Plan-reviewer: rubric-based structure with numbered checks.
- All lanes: structurally-enforced tool boundaries via YAML frontmatter — these do **not** rely on prose discipline and should stay exactly as-is.

**Known copy-error to flag (not fix in this plan):** `brws-author-b`, `brws-author-c`, `brws-author-d` all self-describe as "the primary browser-game implementation lane" while their meta description says "Overflow". Flag for cleanup in the template deduplication wave.

---

## Principles

Ten principles derived from the research, each anchored to a citation or empirical observation. Implementation waves will apply these; this plan does not apply them.

1. **Lead with role identity, not prohibitions.**
   Open each prompt with a one-paragraph statement of who the lane is, what it owns, and how it collaborates with other lanes. Anthropic: "Giving Claude a role ... can dramatically improve its performance." Current orchestrator prompt opens with a rules list; invert that order.

2. **Replace "MUST / NEVER / DO NOT" with positive instructions + rationale.**
   Not "The orchestrator must NOT implement code"; instead "The orchestrator dispatches work to author lanes — author lanes own implementation scope." Direct application of Anthropic's positive-framing guidance.

3. **Preserve one layer of "NEVER" for safety-critical actions only.**
   E.g., `blind-comparator`'s "Do NOT guess which strategy is which" prevents experimental contamination; `repair`'s stop rules prevent runaway fixes. These are legitimate and should remain explicit. Keep the total count small and justified — target fewer than 3 hard prohibitions per file.

4. **Grant permission to surface uncertainty explicitly.**
   Every lane prompt should name one sentence of the form "If scope is ambiguous / repro is unclear / the plan contradicts repo state, ask the orchestrator before proceeding." Aligns with Anthropic's trained uncertainty-surfacing behavior and gives lanes a first-class escape hatch from bad task packets.

5. **Grant authority to deviate (with a narrow gate).**
   Each lane should have one paragraph describing when it is *expected* to push back on an instruction (e.g., review lane refusing to approve a merge without a verdict; author lanes refusing to expand scope beyond `scope_declared`). Current prompts have this implicitly; make it explicit.

6. **Explain context for why a rule exists.**
   When a constraint is load-bearing (e.g., "author lanes do not touch other author worktrees"), state the reason (preventing cross-lane write conflicts) rather than just the rule. Gives Claude the judgment input it needs for edge cases not covered by the rule.

7. **Prefer "we" and "the fleet" for shared conventions; "you" for lane-owned decisions.**
   Small linguistic shift that reframes rules as shared team norms rather than top-down mandates. ACL 2024 politeness evidence supports collaborative framing having real effect.

8. **Keep structurally-enforced constraints (YAML frontmatter) as the primary enforcement mechanism.**
   Tool `allowedTools` / `disallowedTools` / `model` settings are not changed in this plan and are not relaxed by softer prose. The prose migration is orthogonal to the structural guardrails.

9. **Deduplicate author/brws/flex lanes before softening them.**
   Eleven author prompts share ~85% of text. Any tone migration applied to copies drifts. Extract a shared baseline (e.g., a hypothetical `<shared-author-baseline>` file in `.claude/agents/`, or an include mechanism) before refreshing the language, or script the refresh to touch all eleven atomically. The exact authoring surface is TBD during Wave 3 scoping. Deduplication can happen without any tone change first, as a safe refactor.

10. **Validate by qualitative transcript review, not by chasing statistical significance on a short pilot.**
    Per `.claude/rules/deferred/05_rigor.md`, our fleet volume (~10–40 PRs/day) is insufficient for a statistically rigorous before/after comparison on a one-week pilot. Validation is operator judgment + targeted transcript review, honestly labeled as such. Measurement integrity matters more here than the illusion of a gate.

---

## Per-Role Recommendations

High-level intent only — concrete rewrites are **out of scope for this plan** and will be drafted in follow-up PRs during implementation waves.

### steward-orchestrator
- Open with role identity as fleet coordinator ("You are the steward-orchestrator: you shape work, dispatch task packets, and keep the fleet unblocked").
- Convert "The orchestrator must NOT..." list into a positive-framed "Orchestrator responsibilities vs author-lane responsibilities" table.
- Preserve the existing anti-pattern list but reframe as "Patterns that signal you've drifted out of your lane" with reasons.

### steward-ops
- Already the cleanest prompt in the fleet. Preserve wholesale.
- Minor additions: explicit uncertainty-surfacing sentence; explicit authority grant for read-only investigation.

### steward-review
- Preserve the strong autonomy grant ("you have full authority ... do not ask for confirmation").
- Reframe convention-check list as "what you're looking for" instead of "what must not pass".
- Add explicit deviate-authority: "If a PR violates a convention that isn't load-bearing for correctness, note it as a warning, not a block."

### steward-analyst (this lane)
- Preserve "Research Protocol" and "When To Use / When Not To Use" sections.
- Convert the 11 "must not" / "do not" instances to positive framings.
- Add explicit permission to propose scope changes back to the orchestrator when investigation reveals the task was mis-shaped.

### steward-author-a/b/c/d, steward-brws-author-a/b/c/d, steward-flex-a/b/c (11 files)
- **Deduplication is the prerequisite.** Do not refresh language on 11 copies without consolidating first.
- Proposed structure: one baseline prompt describing "author-lane contract" + per-lane overlays that state only the lane's domain (platform / browser-game / flex).
- After deduplication, the baseline can be softened once and inherited.
- Fix the "Overflow" vs "primary" meta-description copy error as part of this wave.

### steward-author-scratch
- Already softer tone. Preserve "disposable and non-authoritative" framing.
- Fold into the baseline+overlay structure from the author wave.

### repair
- Preserve explicit stop-and-escalate triggers (these are load-bearing for safety).
- Reframe surrounding prose as collaborative ("when you encounter X, here's what we expect").

### plan-reviewer
- Already rubric-based and low-command. Light refresh only.

### correctness-reviewer, coverage-reviewer, architecture-reviewer
- "HARD SCOPE CONSTRAINT" is load-bearing — specialist reviewers are expected to stay narrow. Keep the constraint; reframe the surrounding prose.
- Highest regression risk in the fleet: softening prose without preserving scope narrowness could cause specialist reviewers to bleed into each other's territory. Last wave for that reason.

### blind-comparator
- "Do NOT guess which strategy is which" is experimental-contamination prevention. Preserve as-is; legitimate use of hard negation.

---

## Migration Strategy

Three options considered. Recommending **Option B (phased rollout)**.

### Option A — Big-bang rewrite
Rewrite all 22+ prompts in one PR.
- **Pro:** Consistent tone across fleet from day one.
- **Con:** High blast radius. If a reframe introduces a regression (e.g., specialist reviewer bleeding scope), it affects every lane simultaneously with no control group.
- **Rejected:** fleet volume is too low to recover cleanly from a fleet-wide regression.

### Option B — Phased rollout (Recommended)
Four waves, each ~1 week apart, with operator review between waves. This plan specifies the first wave; subsequent waves are drafted as their own session plans after observing the prior wave.

**Wave 1 — Low-risk pilots (this plan's first-wave proposal):**
- `steward-analyst` (this lane) and `steward-ops`
- Rationale: both have structural tool guardrails that don't rely on prose discipline; ops is read-only so softening prose is strictly safe; analyst is research-heavy where collaborative framing matches the work directly.
- Expected churn: two PRs, one per lane, each touching exactly one file.

**Wave 2 — Central-plane lanes:**
- `steward-review`, `steward-orchestrator`
- After observing Wave 1 for one week. These are higher-leverage lanes so the operator reviews them explicitly before rollout.

**Wave 3 — Author/brws/flex deduplication + refresh:**
- First: structural refactor introducing shared baseline (no tone change).
- Then: one softening PR against the baseline.
- Fix the "Overflow" vs "primary" copy error in the deduplication PR.

**Wave 4 — Specialist reviewers + repair:**
- `correctness-reviewer`, `coverage-reviewer`, `architecture-reviewer`, `plan-reviewer`, `repair`, `blind-comparator`.
- Highest regression risk; last wave so operator has maximum signal from prior waves.

### Option C — A/B comparison
Run softened and unsoftened prompts side-by-side on matched tasks, compare outcomes.
- **Pro:** Quantitative evidence.
- **Con:** At ~10–40 PRs/day fleet volume and with heterogeneous tasks, no pilot window small enough to be politically viable would produce statistically significant results. Per `.claude/rules/deferred/05_rigor.md`, we should not pretend otherwise.
- **Rejected:** measurement infrastructure does not support a rigorous A/B at our volume.

---

## Validation

Honest labeling per `.claude/rules/deferred/05_rigor.md`: this is qualitative operator validation, not statistical inference.

### Per-wave validation protocol
After each wave, run for one calendar week, then:

1. **Transcript review:** sample 5–10 task transcripts from the refreshed lane(s) and 5–10 from a non-refreshed lane. Compare along three dimensions:
   - Did the lane ask a clarifying question when the task packet was ambiguous? (Uncertainty-surfacing is a trained behavior we're trying to unlock.)
   - Did the lane push back on out-of-scope expansion?
   - Did the lane complete its task lifecycle (ack → implement → validate → PR → completion message)?
2. **Operator judgment:** does interacting with the refreshed lane *feel* different? Operator writes a short (≤300-word) impression note after each wave.
3. **Regression check:** PR merge rate, review-blocker rate, and task-packet rejection rate for the refreshed lanes vs the prior week. Not statistically tested; large deltas (e.g., merge rate drops >30%) are the threshold for reverting the wave.

### What we are NOT claiming
- No significance testing, no confidence intervals, no power analysis.
- No before/after metric will be reported as a "proof" of the hypothesis — only as rough sanity checks.
- The success of this initiative is qualitative operator judgment + transcript review, and we say so.

### Rollback criteria
- A refreshed lane produces a CRITICAL post-merge review finding caused by the prompt change (e.g., specialist reviewer bleeding scope).
- A refreshed lane's PR merge rate drops >30% week-over-week.
- Operator judges the lane's behavior worse and can name a specific transcript demonstrating it.

Any of these reverts the wave; we regroup and revise the principles.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Softening prose inadvertently relaxes a load-bearing guardrail (e.g., specialist reviewer scope). | Structural guardrails (YAML frontmatter) are unchanged; specialist reviewers are the last wave precisely to catch this. |
| Author-lane deduplication introduces drift across 11 files. | Deduplication is its own PR, no tone change, pure refactor. Reviewed separately. |
| Claude Code doesn't support prompt includes / shared baselines. | Confirm the authoring surface during Wave 3 scoping. Fallback: script-based multi-file edit with a single source of truth in `plans/`. |
| Flurry of prompt PRs competes with other lane work for review attention. | Waves are explicitly spaced; one softening PR per wave (except Wave 3 refactor). |
| "Valued teammate" framing is read as instructive-of-personality rather than instructive-of-process. | Principles ground the language in process outcomes (uncertainty-surfacing, deviate-authority), not personality adjectives. |
| Measurement honesty: operator wants "proof it worked" but fleet volume can't deliver. | `.claude/rules/deferred/05_rigor.md`-compliant framing baked into this plan's Validation section from day one. |
| Issue #2677 references "feedback" about command language; we may be missing operator examples. | First-wave PR description to ask operator for the motivating transcripts so Wave 2+ prompts can reference them directly. |
| Prompt changes silently break `.claude/skills/*` workflow documentation that assumes certain agent phrasings. | Scan skills/ for references to specific prompt strings before each wave PR. |

---

## First-Wave Proposal

**Pilot lanes:** `steward-analyst` and `steward-ops`.
**Why these two:** both have structural tool guardrails (analyst: `disallowedTools: Agent`; ops: `disallowedTools: Edit/Write/Agent`) that don't rely on prose discipline. Ops is read-only so softer prose is strictly safe. Analyst is research-heavy where collaborative framing matches the work most directly.

**Per-lane intent:**

### steward-analyst
- Preserve: Research Protocol section, When To Use / When Not To Use, Delivery Modes section, Issue Package Standard, Handoff Standard.
- Change: opening paragraph (role identity first), 11 negations reframed to positive instructions with rationale, explicit uncertainty-surfacing sentence, explicit deviate-authority for pushing scope changes back to orchestrator.
- Non-goals: tool frontmatter, model assignment, Issue Package Standard content, Handoff Standard content.

### steward-ops
- Preserve: almost everything. This is the cleanest prompt in the fleet.
- Change: explicit uncertainty-surfacing sentence, explicit authority for read-only investigation, minor re-ordering to lead with role identity.
- Non-goals: tool frontmatter, model assignment, operator-tooling reference list.

**Expected deliverables:** two PRs (one per lane), each touching one file, each ~30–60 lines of diff. Each PR description cites this plan and the Principles section.

**Pilot observation window:** 7 calendar days after both PRs merge. Operator writes a short impression note. Sample 10 transcripts. Decide on Wave 2.

---

## Out of Scope (Explicit)

The following are **not** in scope for this plan or its follow-on waves:
- Tool frontmatter (`allowedTools`, `disallowedTools`) — structural guardrails stay exactly as-is.
- Model assignments (`model: sonnet` vs inherit) — not changed.
- `CLAUDE.md` itself (project-root or `.claude/CLAUDE.md`) — prompt refresh is bounded to `.claude/agents/*.md`.
- `.claude/skills/*.md` — skill definitions are separate and governed elsewhere.
- `.claude/rules/*.md` — rule files govern fleet conventions and are separate.
- Making this a governed initiative with its own plan hierarchy — this is a session-scoped shaping plan per `plans/sessions/` convention.
- Registering this work under an existing governing plan — it is hygiene work, not initiative work.
- Adding `MUST` / `NEVER` back into prompts after migration. If that emerges as needed, it gets its own shaping cycle with evidence.
- Rewriting any agent prompts *in this plan*. This plan produces only itself and the #2677 summary comment.

---

## References

**Anthropic official guidance:**
1. *Claude Code Subagents* — https://code.claude.com/docs/en/sub-agents
   (YAML frontmatter + Markdown system prompt model; tool restrictions; model selection.)
2. *Claude Prompting Best Practices* — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
   - "Think of Claude as a brilliant but new employee ..."
   - "Dial back any aggressive language. Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting like 'Use this tool when...'"
   - "Tell Claude what to do instead of what not to do."
   - Example of `NEVER use ellipses` being less effective than the rationale-bearing form.
3. *Claude Code Best Practices* — https://code.claude.com/docs/en/best-practices (308-redirect target from anthropic.com/engineering/claude-code-best-practices).
4. *Measuring Agent Autonomy* (Anthropic research) — https://www.anthropic.com/research/measuring-agent-autonomy
   - "We train Claude to ask clarifying questions when facing ambiguous tasks."
   - "Training models to recognize their own uncertainty and surface issues to humans proactively is an important safety property."

**Peer-reviewed research:**
5. Yin, Ziqi et al. "Should We Respect LLMs? A Cross-Lingual Study on the Influence of Prompt Politeness on LLM Performance." ACL 2024. — Impolite prompts degrade LLM performance across languages; overly polite does not guarantee improvement. Primary citation for collaborative-language cost/benefit.

**Local evidence:**
- `.claude/agents/*.md` structural inventory (captured during research phase; 23 files, 123 negation tokens, 5 collaborative tokens).
- `.claude/rules/deferred/05_rigor.md` — sample-size and statistical-validation policy underlying this plan's Validation section.
- `plans/sessions/TEMPLATE.md` — session-plan structure this plan conforms to.

---

## Plan

- [ ] Post structured summary comment on #2677 (top 5 findings, top 3 sources, recommended principles, migration strategy pick, first-wave targets).
- [ ] Commit this plan on branch `analyst/agent-prompt-refresh-plan`, rebase onto `origin/main`, open PR.
- [ ] Send completion message to orchestrator with plan path + #2677 comment URL.
- [ ] (Follow-up, not this packet) Operator reviews plan and #2677 comment; decides whether to green-light Wave 1.
- [ ] (Follow-up) If green-lit, spawn two Wave 1 packets (one per pilot lane).

## Files

- `plans/sessions/2026-04-20_agent_prompt_refresh_plan.md` — this file. Shaping artifact only; no code changes.

## Test Criteria

- **Pass condition:** Plan file committed on `analyst/agent-prompt-refresh-plan`, PR open, structured summary comment posted on #2677, orchestrator completion message sent for task `887fd7ee47e6`.
- **Verification command:** `gh pr view --json url,state,title && gh issue view 2677 --json comments --jq '.comments[-1].body' | head -50 && uv run python scripts/internal/ops.py task show 887fd7ee47e6`
- **Expected result:** PR state is `OPEN`; latest #2677 comment begins with "## Agent prompt refresh — analyst findings"; task `887fd7ee47e6` shows a `completion` message from `analyst-d`.

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
