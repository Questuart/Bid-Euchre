# Plan: Clarify Reporting Requirements in Arc D Execution Plan

**Date:** 2026-02-22
**Status:** SUPERSEDED — resolved by PR #401 (universal reporting mandate)
**Type:** Doc-only plan (updates `plans/arc_d_execution_plan.md`)
**Motivation:** PR #400 (R0b) shipped without notebook, rung report, or dashboard output.
The plan's own R0b DoD doesn't require them, but the global blind-test flow (§10 line 1780)
says "REPORT -> write rung report, update registry, regenerate arc dashboard" applies to
*every rung*. The R1b–R5b template (step 10, line 1627) also mandates these. This creates
a contradictory state that needs resolution.

---

## Resolution (PR #401)

The ambiguity was resolved by making reporting **universally required** for all
rungs, with no R0 exemption. R0 reporting was delivered retroactively in PR #401:

1. **Notebook:** `notebooks/arc_d/02_r0_baseline.py` (eval-only mode)
2. **Rung report:** `docs/04_reports/model_arc_r0_20260222.md`
3. **Dashboard:** `docs/04_reports/arc_d_v1/model_arc_d_dashboard.md`

The execution plan was updated with:
- Universal reporting mandate preamble before R{N}b template
- "No exceptions" clarification after blind-test flow
- Expanded Step 10 with exact commands for all three deliverables
- R0b DoD note confirming retroactive compliance

---

## Original Problem: Three Conflicting Signals

| Source | Line(s) | Says |
|--------|---------|------|
| R0b Definition of Done | 1520–1529 | No notebook, no rung report, no dashboard. Only JSON artifacts + registry. |
| R1b–R5b Template Step 10 | 1627–1629 | "Run notebook, generate rung report, regenerate arc dashboard" |
| Global Blind-Test Flow | 1769–1780 | "REPORT -> write rung report, update registry (idempotent), regenerate arc dashboard" — explicitly says "applies to every rung, both arms" |

**Root cause:** R0b was designed as a lightweight baseline lock, but the plan
never explicitly exempted R0 from the global REPORT step. Rather than add an
exemption, PR #401 resolved this by delivering R0 compliance retroactively and
making reporting universally mandatory.

---

## Original Changes (superseded by universal mandate)

The original plan proposed an R0 exemption approach. This was rejected in
review round 1 (Finding 1: "R0 exemption contradicts the mandate"). The
final resolution was the opposite: make reporting universal and deliver R0
compliance retroactively.

Changes 1–4 from this plan were replaced by the universal mandate language
now present in `plans/arc_d_execution_plan.md`.
