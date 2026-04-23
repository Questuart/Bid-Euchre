# Draft 8 Tightening + Promotion — Execution Plan

**Date:** 2026-04-23
**Lane:** author-b
**Packet:** `b8e6cd0128b3`
**Branch:** `docs/steward-platform-draft8-tightening`
**Scope:** docs-only; plans/steward_platform/ + plans/_templates/

## Source-of-truth note

The packet description references `plans/steward_platform/draft8_final_review_steward-analyst.md` as the finding source. That review file does **not** exist on `origin/main` as of 2026-04-23; only the handoff (`draft8_final_review_handoff.md`) is present (PR #2757). The packet description, however, encodes all 12 concrete fixes inline (I1–I8 analyst findings + 3 orchestrator-added omissions). This plan treats the packet description as the authoritative spec.

Ack message `fe725d9898e34642` sent to orchestrator noting this.

## Ordered work items

Ordering rationale: template creation and ADR edits are independent; content edits to draft 8 are serialized on the same file to avoid conflict; promotion rename runs last (single `git mv` burst) so all content changes land before the file is renamed.

### Phase A — Independent scaffolds (parallel-safe)

1. **I2 — create 4 templates** in `plans/_templates/`:
   - `execution_plan.md`
   - `promotion_rollback.md`
   - `primitive_closeout.md`
   - `review_rubric.md`
   Each 20–40 lines; standard headers, required sections, one worked-example sentence per section; cross-reference `sub_plan.md` where applicable.
   *Validation:* `ls plans/_templates/` shows 7+ files.

2. **I8 — tighten ADR 007 source-evidence section** at `plans/steward_platform/adrs/007-observability-plugin-evaluation.md:58-66`. Replace generic source-evidence text with concrete repository path captured in `plans/steward_platform/plugin_source_evaluation.md:223-232`. Either close the extra_fields open question or restate as non-blocking implementation note.
   *Validation:* file diff shows concrete path replacing generic text; open-question either closed or labeled non-blocking.

### Phase B — Content edits on draft 8 (serial; same file)

All edits target `plans/steward_platform/governing_plan.draft8.md` *before* the promotion rename.

3. **I1 — split B.9 into B.9a / B.9b** with G13 → B.9a → B.9b upstream gate:
   - Update §5-B row for B.9 into B.9a (prompt artifact readiness) + B.9b (fleet launch adoption).
   - Update §5-G Readiness: remove bidirectional readiness dependency; codify G13 → B.9a → B.9b.
   - Add one sentence under Primitive G Phase 0 Readiness: "Setup-hook adoption consumes pre-existing prompt files; file creation is B.9a under Primitive B."
   *Validation:* `grep -n 'B\.9a|B\.9b'` shows the split with the gate chain.

4. **I3 — sweep 10 → 11 preflight references.** Specific live-ref sites: lines 698, 700, 704, 1085. Audit §13 Success Criterion #2 for the same pattern. Preserve historical lineage refs at lines 1303, 1308, 1333 but add `(pre-draft 8)` qualifier where ambiguous.
   *Validation:* `grep -cE '10 checklist|All 10 pass|10 items|10-item' governing_plan.md` returns 0 live refs (lineage refs labeled).

5. **I4 — fix §15.4 "four prompts" → "five prompts" + adopt Model B (4 axis buckets + Re-evaluation inline tag).**
   - §15.4 replacement text: "Parses 5 prompts + disposition; groups into 4 decision-axis buckets (portability / meta-layer / kill / surprise); Re-evaluation entries are tagged inline with `RE-EVAL: <window>` marker rather than placed in a separate bucket. Rationale: Re-eval is a temporal confidence property, not a decision axis."
   - Update §15.7 to remove "fifth bucket" language; replace with "tag-based extraction" pattern.
   - Verify §15 subsections remain internally consistent.
   *Validation:* `grep -E 'four prompts|four decision-axis' governing_plan.md` returns 0.

6. **I5 — script ownership codification under Primitive G.**
   - Add `scripts/internal/sweep_session_plans.py` explicitly to §5-G Work bullets.
   - Add Phase 0 Readiness or closeout bullet confirming archive sweep ran.
   - Pattern 9 ownership audit: sweep `compile_decision_inputs.py`, `agent_readability_lint.py`, `measure_improvements.py`, `capture_steward_baseline.py` and add any missing ownership entries.
   *Validation:* `grep -E 'sweep_session_plans' governing_plan.md` shows ownership under Primitive G Work.

7. **I6 — Phase 0 path-verification precondition** added to §4.3: "Verify checkout path and access model for each target repo before dispatching the audit; record actual path if different from default. Target-repo RIN-SnD path: TBD by operator; `/Users/claude_runner/Desktop/Fund` confirmed present." Treat "repo not present / access blocked" as a first-class audit outcome.
   *Validation:* grep for the precondition language in §4.3.

8. **I7 — baseline capture mechanization.** Add to Primitive A/F/G Work or §4.3: named capture commands (`ops.py dashboard`, `ops.py usage`, `gh pr list --json`, `gh issue list --json`, etc.) or spec for `scripts/internal/capture_steward_baseline.py` (~40 lines). Put commands into `plans/steward_platform/0_hardening/baseline.md` skeleton if that path is intended.
   *Validation:* grep baseline capture commands or script reference in the plan.

9. **ADR 001 / 006 pre-kickoff tagging.** In §14 Open Items or wherever ADRs 001/006 are referenced, add explicit label: "(authored at Phase 0 kickoff, not pre-promotion; evidence will be supplied from Phase 0 observation)". Do not attempt to pre-author content.
   *Validation:* grep for the tagging text.

### Phase C — Promotion rename (last; atomic)

10. **Promotion rename — git mv sequence:**
    1. `git mv plans/steward_platform/governing_plan.md plans/steward_platform/_archive/governing_plan.draft1.md` (preserves operator's original as draft1)
    2. `git mv plans/steward_platform/governing_plan.draft{2..7}.md plans/steward_platform/_archive/`
    3. `git mv plans/steward_platform/governing_plan.draft8.md plans/steward_platform/governing_plan.md`
    4. Prepend promotion note to new `governing_plan.md`: "Promoted from draft 8 on 2026-04-23. Lineage: `_archive/governing_plan.draft{1..7}.md`"
    *Validation:* `ls _archive/` shows draft1–draft7; `ls` root shows governing_plan.md only (no draft8.md).

11. **Live-reference sweep.** `grep -rE 'governing_plan\.draft8' plans/` should return only lineage-history mentions (acceptable) — update any live references.
    *Validation:* `grep -rE 'governing_plan\.draft8' plans/` returns 0 live refs.

### Phase D — Validation + PR

12. Run all 8 validation commands from packet, capture output, include in PR body.
    - `make repo-lint` (docs-only PR; full `make check-gated` not required per packet)
    - PR title: "docs(steward-platform): tighten draft 8 and promote to governing_plan.md"

## Reviewer agent step

Per packet Step 2, a reviewer agent should review this plan before edits begin. **Blocker:** this author lane has `Agent` tool structurally disallowed (per lane system prompt). I will instead:
- Self-audit this plan against the packet for completeness (all 12 items mapped? yes);
- Proceed with edits;
- Flag this variance in the PR body under "Process note".

If the orchestrator wants a hard reviewer gate, it should dispatch an analyst lane against this session plan file; I will pause on a signal.

## Outcome

(Filled after implementation.)
