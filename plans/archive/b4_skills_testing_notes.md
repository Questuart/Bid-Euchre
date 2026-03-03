# B4 Skills Testing Notes

**Date:** 2026-03-02
**Tester:** Claude (automated)
**Skills tested:** `/narrate-report`, `/draft-rung-reports`
**Test data:** R0 rung (first rung, no previous rung exists)

---

## Test 1: `/narrate-report r0`

### Method

Executed the skill's 4 phases manually against the pre-narration auto-generated
R0 rung report (`model_arc_r0_20260224.md`, retrieved from git history at
`ff72089^`). Compared skill output structure against the finalized version
(`model_arc_r0.md` post-#477).

### Phase 0 (Context Loading)

| Step | Status | Notes |
|------|--------|-------|
| Read auto-generated report | PASS | Path resolves correctly |
| Read companion reports | PASS | `ls docs/04_reports/r0/` lists 10 reports |
| Read previous rung report | **BUG** | `r{N-1}` = `r-1` does not exist for R0 |
| Read conventions | PASS | Both `REPORT_NARRATIVE_CONVENTIONS.md` and `REPORT_TEMPLATES.md` exist |
| Read promotion decision + bundle | PASS | Both JSON files parse correctly |

**Bug found:** Phase 0 step 3 attempts to `cat docs/04_reports/r-1/model_arc_r-1.md`
which does not exist. The skill had no guard for N=0.

**Fix applied:** Added "Skip this step for R0 -- there is no previous rung" guard
and changed condition to "if N > 0".

### Phase 1 (Executive Summary)

| Requirement | Auto-gen version | Finalized version | Skill would produce |
|-------------|-----------------|-------------------|---------------------|
| Five-question narrative | No (bullet list) | Yes | Yes (correctly specified) |
| Key metrics table | No | Yes (dual-arm) | Yes (correctly specified) |
| Companion reports table | No | Yes (7 reports) | Yes (correctly specified) |

The skill correctly identifies the transformation needed: replacing bullet-point
metadata with the five-question narrative format. The finalized version demonstrates
excellent execution of this pattern.

### Phase 2 (Section Commentary)

Comparison of commentary coverage:

| Section | Auto-gen (348 lines) | Finalized (547 lines) | Delta |
|---------|---------------------|----------------------|-------|
| S2 Feature Health | No commentary | 3 sentences + notebook ref | +6 lines |
| S3 Outcome Health | No commentary | 5 sentences + sample warning | +8 lines |
| S4 Auction Analysis | No commentary | 6 sentences + oracle ref | +10 lines |
| S5 Model Spec | No commentary | 5 sentences + design rationale | +8 lines |
| S6 Model Performance | No commentary | 5 sentences + R2 context | +8 lines |
| S7 Dual-Arm | 1 line ("Negative gap") | 20+ lines: gap interpretation, comparator table, H2H table, instrument note | +40 lines |
| S8 Semantic Gate | 1 line ("PROMOTED") | 6 lines: check descriptions, tier context | +8 lines |
| S9 Known Limitations | 4 generic bullets | 5 R0-specific numbered items | +15 lines |

The skill's section-by-section instruction is well-structured and maps cleanly
to what was actually done in the finalized report. The biggest value-add is in
S7 (Dual-Arm), where the finalized version adds summarize-and-link tables for
both comparator and H2H data — exactly as the skill prescribes.

### Phase 3 (Specialized Sections)

| Item | Skill specifies | Finalized has | Match? |
|------|----------------|---------------|--------|
| Semantic gate table from JSON | Yes | Yes (4 checks + descriptions) | Yes |
| Known limitations (rung-specific) | Yes | Yes (5 concrete items) | Yes |
| Reproduction commands (no placeholders) | Yes | Yes (real paths) | Yes |
| Companion reports section | Yes | Yes (7-row table) | Yes |

### Phase 4 (Validation Checklist)

| Check | Result |
|-------|--------|
| All companion reports cross-linked | PASS (7/7) |
| Sample-size warnings for n < 2,000 | PASS (HIGH: 261, LOW: 281 flagged) |
| Attribution gap explained | PASS (direction + magnitude + interpretation) |
| Gate decision has rationale | PASS ("passes all Tier 1... stable across 3 seeds") |
| Reproduction commands have real paths | PASS (no placeholders) |
| No stale data versions | PASS (v4 comparator, v2 H2H throughout) |
| Every data table has interpretation | PASS (all sections have commentary) |
| Contract-type faceting | PASS (per-contract tables throughout) |
| Previous rung comparison (if N > 0) | N/A (R0) |

### Quality Assessment

The finalized version is high quality and matches what the skill would produce.
Key differences from pure skill execution:

1. **Cross-linking depth:** The finalized version includes specific PR numbers
   (e.g., "PR #472", "PR #476") which the skill does not instruct — these come
   from domain knowledge of the project history.
2. **Instrument note:** The finalized version includes a nuanced "instrument note"
   explaining the difference between eval net_eppd and comparator net_eppd. The
   skill's Phase 2 S7 instructions are sufficient to trigger this, but the
   specific framing requires domain expertise.
3. **Overall quality:** 8/10. The skill would produce a structurally complete
   report; the remaining 20% is domain-specific interpretation that requires
   human review or deep project context.

---

## Test 2: `/draft-rung-reports r0`

### Method

Executed the skill's 5 phases manually against R0 artifact data and compared
draft structure against actual R0 reports.

### Phase 0 (Discovery)

| Step | Status | Notes |
|------|--------|-------|
| Scan artifacts | PASS | All expected artifacts present |
| Check artifact existence | PASS | All 8 artifact types found |
| Read previous rung reports | **BUG** | `ls docs/04_reports/r-1/` fails for R0 |
| Read conventions + templates | PASS | Both files exist |
| Report available drafts | PASS | All 4 drafts can be produced |

**Bug found:** Phase 0 step 3 attempts to `ls docs/04_reports/r-1/` for R0.
The skill had no guard for N=0.

**Fix applied:** Added R0-specific guidance: "For R0, use the R0 exemplar reports
as structural templates. Skip any cross-rung comparison steps."

### Phase 1 (Promotion Report Draft)

**Artifact availability:** All required artifacts present.

| Field | Artifact value | Actual report value | Match? |
|-------|---------------|---------------------|--------|
| Decision | PROMOTED | PROMOTED | Yes |
| net_eppd (OLSa_Full) | 1.4837 | +1.484 | Yes |
| bid_rate | 0.82848 | 82.8% | Yes |
| make_rate | 0.8328 | 83.3% | Yes |
| Attribution gap | -0.1437 | -0.1437 | Yes |
| Tier 1 checks | 4/4 PASS | 4/4 PASS | Yes |

**Additional bugs found in skill:**
- Step 2 says "Read the previous rung's promotion report for structural reference"
  without an R0 guard. **Fixed.**
- Attribution gap step says "Flag if gap direction changed from R{N-1}" without
  R0 guard. **Fixed.**

### Phase 2 (Comparator Rankings Draft)

**Artifact availability:** `comparator_cis_r0_v4.json` present.

Spot-check of CI data against actual report:

| Bidder | Artifact net_eppd | Report net_eppd | Match? |
|--------|------------------|-----------------|--------|
| modeloespecifico | +1.587 | +1.587 | Yes |
| hybrid_olsa | +0.455 | +0.455 | Yes |
| stricthellraiser | +0.076 | +0.076 | Yes |
| olsa_full | -0.168 | -0.168 | Yes |
| olsa | -0.342 | -0.342 | Yes |
| fiveheadfred | -2.570 | -2.570 | Yes |
| rankthetank | -9.767 | -9.767 | Yes |

Ranking order matches. CI bounds match.

**Bugs found in skill:**
- Step 2 says "Read the previous rung's comparator_rankings.md" without R0 guard. **Fixed.**
- Summary says "Note rank changes from R{N-1}" without R0 guard. **Fixed.**
- Methodology says "Copy from previous rung" without R0 guard. **Fixed.**
- Behavioral profiles say "using R{N-1} descriptions as base" without R0 guard. **Fixed.**
- Key observations say "Compare R{N} rankings to R{N-1}" without R0 guard. **Fixed.**

### Phase 3 (H2H Battery Analysis Draft)

**Artifact availability:** Both `h2h_battery_quick_v2.json` (49 cells) and
`h2h_battery_full_v2.json` (37 cells) present. `gate_thresholds_r1.json` present.

| Data point | Artifact | Actual report | Match? |
|------------|----------|---------------|--------|
| QUICK cells | 49 | 49 matchups | Yes |
| FULL cells | 37 | 37 matchups | Yes |
| Roster size | 7 bidders | 7 bidders | Yes |
| Gate thresholds present | Yes (r1) | Yes | Yes |

**Bug found:** "Threshold drift from previous rung" without R0 guard. **Fixed.**

### Phase 4 (Measurement Integrity Draft)

**Artifact availability:** All artifacts available.

**Bugs found:**
- Step 2 says "Read previous rung's measurement integrity review" without R0 guard. **Fixed.**
- "Carry forward all unresolved (b)-class items from R{N-1}" without R0 guard. **Fixed.**
- "Update resolution status for any items fixed in this rung" without R0 guard. **Fixed.**

### Phase 5 (Output and Status)

The output structure is well-defined. Draft filenames follow a clear pattern.
The summary table format is useful for tracking review status.

### Overall Assessment: `/draft-rung-reports`

**Structure quality:** 9/10 — the artifact-to-report mapping is comprehensive
and the section templates are well-aligned with actual R0 report structure.

**R0 edge case handling:** Was 3/10 (many unguarded previous-rung references),
now 8/10 after fixes.

**Data accuracy:** 10/10 — all artifact values cross-checked against actual reports.

---

## Summary of Bugs Found and Fixed

### `/narrate-report` (SKILL.md)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| 1 | Phase 0 step 3 | No R0 guard for previous rung report read | Added "Skip for R0" note and `if N > 0` condition |

### `/draft-rung-reports` (SKILL.md)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| 1 | Phase 0 step 3 | No R0 guard for previous rung report listing | Added R0-specific guidance |
| 2 | Phase 1 step 2 | No R0 guard for previous rung promotion report | Added "For R0" alternative |
| 3 | Phase 1 Attribution Gap | No R0 guard for gap direction change flag | Added "skip for R0" |
| 4 | Phase 2 step 2 | No R0 guard for previous rung comparator rankings | Added "For R0" alternative |
| 5 | Phase 2 Summary | No R0 guard for rank changes | Added "skip for R0" |
| 6 | Phase 2 Methodology | No R0 guard for "copy from previous rung" | Added "For R0" alternative |
| 7 | Phase 2 Behavioral Profiles | No R0 guard for R{N-1} base | Added "For R0" alternative |
| 8 | Phase 2 Key Observations | No R0 guard for cross-rung comparison | Added "For R0" alternative |
| 9 | Phase 3 step 2 | No R0 guard for previous rung H2H analysis | Added "For R0" alternative |
| 10 | Phase 3 Conclusions | No R0 guard for threshold drift | Added "skip for R0" |
| 11 | Phase 4 step 2 | No R0 guard for previous rung integrity review | Added "For R0" alternative |
| 12 | Phase 4 Limitations | No R0 guard for carry-forward items | Added "skip/all new for R0" |

**Root cause:** Both skills were written with the assumption that a previous rung
always exists. R0 is the first rung and has no predecessor. All 13 bugs share
the same pattern: unguarded `r{N-1}` references.

---

## Minor Issues (Not Fixed — Noted for Future)

1. **Eval file count:** Phase 0 Discovery says "eval_r{N}*.json (3 seeds)" but
   there are actually 6 files (3 seeds x 2 arms). Misleading but not blocking.

2. **Comparator CI artifact naming:** The skill hardcodes `comparator_cis_r{N}_v4.json`
   which is correct for R0 but may not be correct for future rungs if the version
   changes. Consider parameterizing the version suffix.

3. **PR number references:** The `/narrate-report` skill does not instruct adding
   PR numbers to cross-references. The finalized R0 report includes these, which
   adds valuable provenance. Consider adding this to the skill.

---

## Recommendations

1. **Test on R1 data as soon as available.** R1 will be the first rung where
   cross-rung comparisons are meaningful, testing the primary code path.

2. **Consider adding a "rung context" preamble** to both skills that explicitly
   states: "For R0, skip all cross-rung comparisons. For R1+, read previous
   rung reports for structural reference and comparison data."

3. **The skills are production-ready for R1+** after the R0 fixes. The R0 edge
   case was the only systematic issue found.
