# Recipe: Shape-then-execute Pattern 11 dispatch

## Version

`b11-recipe-shape-then-execute-v1.0`

## Context

Session 2026-04-23 demonstrated that novel, multi-file, multi-decision
work (steward platform Phase 0 primitives A–G) routes poorly through a
single-packet dispatch. Authors who received a single packet containing
both design decisions and implementation work consistently re-litigated
scope boundaries, doubled back on decisions that should have been fixed
at shaping time, and produced PRs with scope drift (e.g., Primitive B's
original packet drifted across B.1 / B.3 / B.6 / B.10 / B.11 concerns
without a shape to bound them).

Trace evidence:
- Verification-contract work landed cleanly once split into Packet 2a
  (shape) + Packet 2b (execute) — PRs #2759, #2762 — with 25 files /
  3804+ additions in 2b and zero author re-litigation.
- Primitive A pre-shape (PR #2771) followed the same pattern; execution
  packet downstream referenced the shape rather than re-deriving.
- Pattern 11 itself was codified in §10.9 of the governing plan after
  it had already emerged three times as the winning dispatch shape
  across Primitives A, B, and C pre-shapes (PR #2773).

## Decision

Decompose novel Phase 0 work into two packets:

1. **Shape packet** dispatched to an analyst lane. Deliverable: a
   shaping document matching Pattern 11's minimum sections (§10.9 of
   the governing plan) — Goal / Scope / Deliverables-with-verification-
   surface / Rationale / Risks / Rollback. The shape is authored with
   `max` effort and is the authoritative source for downstream design
   questions.
2. **Execute packet** dispatched to an author lane (or flex-as-author)
   after the shape merges. Scope-lock is to what the shape specifies;
   the author's prompt-policy clause (see `prompt_policy/author.md`
   §"Shape-is-authoritative") forbids in-line re-design.

Author escalates on gaps (missing surface, contradictory requirements,
unclear rollback path) via an orchestrator message rather than
silently correcting the shape. If the shape itself is wrong, the
orchestrator redispatches a shape-revision packet; the author does not
edit the shape from inside the execute packet.

Anti-patterns explicitly ruled out:
- **Mixed shape-and-execute in one packet.** Produces scope drift and
  re-litigation cost — the shape becomes a moving target as the author
  encounters friction.
- **Shape without verification surfaces per deliverable.** Allows the
  execute packet to ship without verifiable completion evidence
  (Pattern 10 violation). Every §N.M row in the shape names a surface.
- **Author silent correction of the shape.** Breaks the "shape is
  authoritative" contract; prevents B.12 improvement-mechanism
  evaluation from attributing outcomes to the shape vs. execution.

## Observed outcome

Session 2026-04-23: 25 files / 3804+ additions landed in Packet 2b
without author re-litigation. ~4× throughput gain vs. the previous
sequential design-in-author approach for novel infrastructure work.
Zero governing-plan clarifications required during Packet 2b
execution (historical rate for comparably-novel work: 2–4
clarifications per packet).

Broader session (2026-04-22c through 2026-04-23): 8 governing-plan
drafts + 4 analyst reviews + 1 plugin source-evaluation + 4 ADR
seeds landed across 11 merged PRs, with each draft cycle bounded
by a shape (prior draft + review) before the next revision —
confirming the pattern generalizes beyond Phase 0 primitive shaping
to governing-plan iteration itself.

## Reuse guidance

**Apply when:**
- Scope crosses >3 files and touches multiple primitives.
- Requires design decisions not fully specified in the governing
  plan or an existing ADR.
- Work is novel pattern/infrastructure (first instance of a new
  abstraction), not a straightforward extension of existing code.
- Operator cannot name the verification surface per deliverable
  without thinking for >30 seconds — that signals the work is
  shaping-work, not execution-work.

**Do NOT apply when:**
- Single-file obvious fix (typo, config bump, one-liner).
- Straightforward extension of an existing, documented pattern
  (e.g., adding a new route that mirrors an existing one).
- Design decisions are fully specified elsewhere (existing ADR,
  existing sub-plan, existing shape from a prior packet).
- The cost of two packets (context-switch, dispatch overhead) would
  exceed the cost of re-litigation — typically when total work is
  <1 hour.

The invariants that make this pattern effective:
- **Shape is authoritative** — the author treats the shape as a
  contract, not a suggestion.
- **Every deliverable names a verification surface** (Pattern 10).
- **Escalation is cheap** — the orchestrator accepts shape-revision
  packets without friction when the author surfaces a real gap.

Failure-modes that make it inappropriate:
- Shape author and execute author are the same lane with no time
  gap (the discipline of the hand-off is what forces the shape to
  stand alone).
- Shape is dispatched without a verification-plan section, so the
  author has no way to validate the work against the shape's own
  acceptance criteria.

## Downstream citations

- Pattern 11 §10.9 of `plans/steward_platform/governing_plan.md`
  (codification commit PR #2773).
- `plans/steward_platform/verification_contract/shaping.md` —
  Pattern 11 shape-then-execute dispatch applied to the verification
  contract itself (Packet 2a shape, Packet 2b execute).
- `.claude/rules/prompt_policy/author.md` §"Shape-is-authoritative
  (Pattern 11, §10.9 governing plan)".
- `.claude/rules/prompt_policy/analyst.md` §"Pattern 11 reference
  (§10.9 governing plan)".
- `plans/steward_platform/2_primitive_B/shaping.md` §8.3 (this
  recipe's seed-at-Phase-0-close rationale).
