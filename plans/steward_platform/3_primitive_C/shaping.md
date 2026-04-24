# Shaping: Primitive C Phase 0 Execution Spec — KB Structure + Agent-Readability Scorecard + Archivist Integration

**Date:** 2026-04-24
**Lane:** analyst-b
**Packet:** `abff1f5d146a` (Primitive C Phase 0 pre-shape — execution belongs to Packet C-Exec)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-C
**Sibling artifacts:**
- `plans/steward_platform/adrs/001-platform-reset.md` (agent-readability 7/10 floor; scorecard lifecycle; Platform-11/13 dismissal evidence)
- `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` (commit-policy binding: only promoted artifacts committed; archivist operator-gated)
- `plans/steward_platform/verification_contract/shaping.md` (Pattern 10 Verification Plan discipline + format exemplar)
- `plans/steward_platform/verification_contract/map.md` rows C.1–C.7 + C.Phase0Readiness (existing Primitive C coverage)
- `plans/steward_platform/1_primitive_A/shaping.md` (event-schema v1.0; C incident entries cite `incident_fingerprint` from `ops/event_taxonomy.py`)
- `scripts/internal/agent_readability_lint.py` (Pattern 10 sub-command already shipped; scaffold for Pattern 9; Pattern 11 to be added)
- `.claude/skills/create-plan/SKILL.md` (refusal-logic specification in place as stub; this shapes full implementation)

**Status:** DESIGN-SPEC — no code, KB artifacts, schemas, or ADRs authored in this document. Produces a Packet C-Exec execution-ready brief.

**Purpose:** Pre-shape Primitive C's Phase 0 execution so that the moment the Phase 0 kickoff gate opens (ADR 001 merged, ADR 006 merged, Packet 2b verification-contract scaffolding merged), an author lane can pick up a Packet C-Exec execution packet with zero additional shaping. Mirrors the Packet 2a → Packet 2b and Packet Pre-A → Packet 3 shape-then-execute patterns (§10.9 Pattern 11).

---

## §1. Scope of this document

This is a **shaping document**, not a sub-plan, ADR, or governing-plan edit. Its single output is an execution-ready specification for the Primitive C Phase 0 deliverables enumerated in `governing_plan.md` §5-C (Work + Phase 0 Readiness + Phase 1 Validation), bound to ADR 001 (agent-readability floor) and ADR 010 (commit policy + archivist operator-gated discipline).

### §1.1 What this document specifies

1. **KB structure** — exact file layout under `knowledge/`, per-file schema expectations, and the promoted/unpromoted boundary enforced by ADR 010's commit policy.
2. **Agent-readability scorecard** — the 10-item scorecard committed to (canonical list frozen in §3.2), the ≥7/10 floor per ADR 001, and the machine-check algorithm per scorecard item.
3. **Archivist integration** — the C↔D interface contract: who archives (D), who promotes (C), the review gate between them (operator-gated per ADR 010), and the three event types that span the boundary.
4. **`/create-plan` skill refusal logic** — grep patterns + deliverable-coverage algorithm + exact error-message format the skill emits on refusal.
5. **`agent_readability_lint.py` Pattern 9 + Pattern 11 sub-commands** — additions to the existing script (Pattern 10 `check verification-contract` already shipped per PR #2762). Specifies rule IDs, findings, the plan-walker shared-module contract, and how these checks interact with the `review_driver.py` V1–V6 prechecks.
6. **Commit policy** — precise path-class lists for tracked vs. gitignored, the promotion transition algorithm (untracked → tracked), and the rollback procedure if a promotion is retracted.
7. **Packet C-Exec execution spec** — files created, files modified, order of operations, validation commands, coordination notes, and success criterion.

### §1.2 What this document does NOT do

- Author any `knowledge/**` content, `.claude/skills/**` code, script extensions, or ADR 001/006 text. Packet C-Exec (plus any sub-slices the orchestrator decomposes it into) does that.
- Modify governing plan text. §5-C is the binding reference; this consumes it.
- Re-litigate ADR 001 or ADR 010 decisions. The ≥7/10 floor, the Platform-11/13 dismissal framing, the "only promoted artifacts committed" commit policy, and the "archivist operator-gated; no autonomous state mutation" discipline are all merged.
- Author the archivist itself (Primitive D scope). The C↔D interface contract is named; D's inflow implementation is Primitive D's responsibility.
- Specify Pattern 9's full rule set. Pattern 9 lands as a scaffold here; full rules follow in a Phase 0 sub-plan under Primitive C (per §13.2 risk #2 note in `verification_contract/shaping.md`: Pattern 9 + Pattern 10 share the plan-walker, which is why Pattern 9 lives in the same script rather than a sibling).

### §1.3 Motivation

Primitive C is the **durable-memory substrate** for the platform — NOTES, PLAYBOOKS, anti-patterns, incidents, ADRs, harness assumptions, INDEX, plus the scorecard, plus the agent-readability lint. §5-C has ≥8 distinct deliverables (per §5-C thematic-coherence note). A single monolithic author dispatch would exceed safe scope (§5-C explicitly opts out of F3's sub-deliverable table pattern because the bullets are mutually reinforcing, but execution still benefits from pre-shape). Pre-shaping C means:

- The Phase 0 kickoff gate doesn't stall waiting for author-lane design work.
- ADR 010's commit-policy boundary is resolved into concrete gitignore paths before the first commit lands under `knowledge/`, avoiding the "commit stuff first, formalize the policy later" failure mode.
- The archivist C↔D interface contract is specified before Primitive D's implementation begins (D is shaping-pending; shaping its inflow against a concrete C-side promotion surface is cheaper than negotiating post-hoc).
- The agent-readability scorecard's 10 items are committed with machine-check recipes, so preflight item 8 (§6.4) has a deterministic pass/fail evaluation rather than a subjective read.

---

## §2. Binding references

### §2.1 ADR 001 (Platform Pattern Reset)

- **Agent-readability floor ≥7/10** — canonical. Sub-plans under Primitive C may tighten to 8/10 or 9/10; may not loosen.
- **Scorecard lifecycle** — committed at Phase 0 kickoff; re-scored at Phase 0 Readiness, at Phase 1a preflight item 8, at Phase 1 end, and carried forward (not gated) into Phase 2.
- **Phase 1 ratchet** — end-of-Phase-1 score ≥ Phase 0 baseline AND ≥ floor (§5-C Phase 1 Validation).
- **ADR 001 filing location** — seeded at `plans/steward_platform/adrs/001-platform-reset.md`; migrates to `knowledge/adr/001-platform-pattern-reset.md` at Phase 0 close (or earlier when the KB skeleton lands). Both paths must resolve to the same content during the migration window.

### §2.2 ADR 010 (mcp-memory-service Evaluation)

- **Commit policy** — only promoted KB artifacts are committed. Inflow (archivist candidate output) is session-local; promotion is the commit-triggering gate.
- **Archivist operator-gated** — no autonomous state mutation. C's promotion requires operator review; D's inflow is candidate-generation only.
- **Reference MCP tool signatures** — signature compatibility preserved for Phase 3+ MCP-exposed KB interface possibility; no dependency taken.
- **Phase 3 soft re-evaluation trigger** — revisit if (a) `NOTES.md` > ~20 KB or ~500 entries OR (b) archivist inflow > 10 candidate lessons per nightly, sustained ≥1 week. Neither blocks Phase 0 or Phase 1.

### §2.3 Governing plan §5-C

- **KB classes (7 files + 1 directory)** — `NOTES.md`, `PLAYBOOKS.md`, `anti_patterns.md`, `incidents/<fingerprint>.md` (directory with per-incident files), `adr/<NNN>-<slug>.md`, `harness_assumptions.md`, `INDEX.md`, `_candidates/` (unpromoted inflow from D), plus `_promoted/` archive per ADR 010.
- **Worked-example obligation** — every KB schema introduced ships with ≥1 full worked example at file head.
- **Harness-assumption brittleness signal** — machine-observable (grep pattern, CI check, hook precondition). Natural-language signals are insufficient.
- **`compile_decision_inputs.py`** — already scaffolded per F6; not in scope of this shaping (lives under §15 + already enumerated in §5-C Work bullet). Referenced only where C interacts with its input.
- **`agent_readability_lint.py`** — already scaffolded per G1 (PR #2762); Packet C-Exec adds Pattern 9 + Pattern 11 sub-commands.

### §2.4 §10.9 Patterns touched

- **Pattern 7 (Reversibility-as-default):** every KB promotion has a rollback path (move back to `_candidates/` or delete `_promoted/` entry; §4.7).
- **Pattern 8 (Observable-by-default):** promotion events emit `kb_artifact_promoted` / `kb_artifact_unpromoted` events with `incident_fingerprint` or artifact-class correlation.
- **Pattern 9 (Load-bearing-ownership lint):** Packet C-Exec adds the concrete rule set to the scaffold already present in `agent_readability_lint.py`.
- **Pattern 10 (Verification surface per deliverable):** every §5-C Work bullet is covered by `verification_contract/map.md` rows C.1–C.7 + C.Phase0Readiness; this shape adds per-deliverable surface detail.
- **Pattern 11 (Shape-then-execute dispatch):** Packet C-Exec adds a `check pattern-11` sub-command that flags implementation PRs with novel multi-file scope not preceded by a shaping doc.

---

## §3. Deliverable → Pattern-10-surface table

Every Primitive C Phase 0 deliverable and its verification surface. Strict-existence / lenient-form per §10.9 Pattern 10.

| # | Deliverable (§N.M of §5-C) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|---|
| C.1.1 | `knowledge/NOTES.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + lint clean on schema | analyst | 1 worked example at file head; lint exits 0 |
| C.1.2 | `knowledge/PLAYBOOKS.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + lint clean | analyst | 1 worked example; lint exits 0 |
| C.1.3 | `knowledge/anti_patterns.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + schema field check (`trigger → harm → preferred alternative`) | analyst | ≥1 entry; lint verifies schema form |
| C.1.4 | `knowledge/incidents/` directory + worked example | new KB-class directory | per-file fingerprint matches `incident_fingerprint` in event schema v1.0 | analyst | ≥1 worked example; grep matches ops/event_taxonomy.py emission |
| C.1.5 | `knowledge/harness_assumptions.md` with ≥5 initial entries | new KB-class artifact | each entry's brittleness signal is machine-observable (grep pattern / CI check / hook precondition) | analyst | lint verifies `assumption → observation → brittleness signal → refresh trigger` fields present; brittleness-signal-is-machine-observable sub-check |
| C.1.6 | `knowledge/adr/` directory | new KB-class directory | per-ADR supersession field + Pattern 7 rollback citation | analyst | ADR 001 present (migrated from seed location); ≥2 additional Phase 0 ADRs per §5-C Readiness |
| C.1.7 | `knowledge/INDEX.md` regeneration script | new Python script under `scripts/internal/**` | `tests/unit/test_kb_index.py::test_index_regenerates_deterministically` + diff against `find knowledge/ -type f` | author | pytest passes; diff empty post-regeneration |
| C.2 | `knowledge/_candidates/` (unpromoted inflow; not committed) | gitignored directory | `.gitignore` entry + archivist promotion-event integration test | ops | `git check-ignore knowledge/_candidates/*` returns 0 exit |
| C.3 | `knowledge/_promoted/` (post-promotion archive; committed) | committed directory per ADR 010 | promotion-event emits `kb_artifact_promoted`; archive-entry present | analyst | grep matches event; artifact present |
| C.4 | `knowledge/agent_readability_scorecard.md` | new KB-class artifact + config | scorecard self-score script output + ADR 001 floor check | ops | score ≥7/10 at Phase 0 kickoff, re-verified at Readiness |
| C.5 | Scorecard runner `scripts/internal/agent_readability_score.py` | new Python script | `tests/unit/test_agent_readability_score.py` + integration run against live repo | author | pytest passes; runner emits 10 item-booleans + aggregate score |
| C.6 | `agent_readability_lint.py check pattern-9` sub-command | extension of existing module | `tests/unit/test_agent_readability_lint.py::TestPattern9` | author | pytest passes on seeded fixtures (positive + negative) |
| C.7 | `agent_readability_lint.py check pattern-11` sub-command | extension of existing module | `tests/unit/test_agent_readability_lint.py::TestPattern11` | author | pytest passes on seeded fixtures (positive + negative) |
| C.8 | `/create-plan` skill refusal logic (full implementation) | upgrade of existing `.claude/skills/**` stub | `SKILL.md` acceptance command + `tests/unit/test_create_plan_refusal.py` | author | skill refuses correctly on all 4 refusal conditions (§5); skill outputs the refusal message format exactly |
| C.9 | Commit-policy codification | `.gitignore` + `.claude/rules/deferred/30_data_contract.md` extension | rollback test (revert a `_promoted/` commit, confirm artifact un-promoted; re-promote, confirm event fired) | ops | `.gitignore` blocks `_candidates/`; `_promoted/` tracked; rollback test passes |
| C.10 | MEMORY.md compaction script `scripts/internal/memory_compact.py` | new Python script | `tests/unit/test_memory_compact.py` + seeded fixture smoke | author | pytest passes; compaction preserves high-priority entries by schema-defined rule |
| C.11 | Archivist C↔D interface contract docstring | docs in `knowledge/INDEX.md` + `scripts/internal/archivist.py` header | grep for interface-contract section in both files | analyst | both contain the contract block verbatim |
| C.12 | Scorecard sub-plan under Primitive C (F10 tightening path) | new sub-plan | `plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` existence + own Verification Plan | analyst | lint clean; sub-plan registered |
| C.P0R | Phase 0 Readiness checklist executed | outcome artifact | `plans/steward_platform/3_primitive_C/phase0_readiness.md` closeout with per-item grep-verifiable check | orch+analyst | all §5-C Readiness bullets verified; logged |

---

## §4. Per-deliverable specs

### §4.1 KB structure (C.1.*–C.3)

#### §4.1.1 Directory layout

```
knowledge/
├── INDEX.md                            # auto-generated; tracked
├── NOTES.md                            # freeform lessons; tracked (promoted content only)
├── PLAYBOOKS.md                        # runbooks; tracked
├── anti_patterns.md                    # "do not do X"; tracked
├── harness_assumptions.md              # dependencies on current harness behavior; tracked
├── agent_readability_scorecard.md      # 10-item scorecard + current score; tracked
├── external_signal_sources.md          # operator-curated changelog sources; tracked
│                                        (§14 open item 17 seed location)
├── adr/                                # architecture decision records; tracked
│   ├── README.md                       # index of ADRs
│   ├── 001-platform-pattern-reset.md   # migrated from plans/steward_platform/adrs/ at Phase 0 close
│   ├── 005-review-plugin.md            # ditto
│   ├── 006-auto-mode.md                # ditto
│   ├── 007-observability-plugin.md     # ditto
│   ├── 010-mcp-memory-service.md       # ditto
│   ├── B8-native-task-system.md        # ditto
│   └── G10-system-prompts-vs-agents.md # ditto
├── incidents/                          # per-incident fingerprinted files; tracked
│   └── <incident_fingerprint>.md       # one file per fingerprint (per §5-A event schema)
├── _candidates/                        # unpromoted archivist inflow; GITIGNORED
│   ├── <YYYY-MM-DD>_lessons.md
│   ├── <YYYY-MM-DD>_changelog.md
│   └── <YYYY-MM-DD>_gc.md              # Phase 1; outflow
└── _promoted/                          # post-promotion archive; tracked per ADR 010
    └── <YYYY-MM-DD>_<artifact_class>_<short_hash>.md
```

**Rationale for `_promoted/` vs in-place editing of NOTES/PLAYBOOKS/etc.:** ADR 010 §Decision mandates "only promoted artifacts committed" without dictating the on-disk shape. Two options:
- **Option A (adopted): in-place append to NOTES/PLAYBOOKS/anti_patterns + parallel `_promoted/` snapshot archive.** NOTES/PLAYBOOKS/anti_patterns remain the canonical reading surface (agent loads one file to get all lessons); `_promoted/` is the audit trail (when was this entry promoted, from which candidate, by which operator). Grep targets live content; history lives in `_promoted/`.
- **Option B (rejected): each promoted entry as a separate file under `_promoted/`, NOTES/PLAYBOOKS being only index files.** Rejected because grep patterns would span 100+ files as the KB grows, defeating agent-readability.

#### §4.1.2 File schemas

Each KB-class file ships with a worked example at file head (per §5-C obligation). Schemas:

| File | Required structure | Worked-example obligation |
|---|---|---|
| `NOTES.md` | `### <title>` headings; each followed by `**Context:** … **Lesson:** … **Source:** <PR/commit/session>` | ≥1 example per file head |
| `PLAYBOOKS.md` | `### <runbook name>` headings; each followed by `**When:** … **Steps:** 1. … 2. … **Verification:** …` | ≥1 example |
| `anti_patterns.md` | `### <anti-pattern name>` headings; each followed by `**Trigger:** … **Harm:** … **Preferred alternative:** …` | ≥1 example |
| `harness_assumptions.md` | `### <assumption name>` headings; each followed by 4 fields: Assumption / Observation supporting / Brittleness signal (machine-observable) / Refresh trigger | ≥1 example; §5-C already commits to "Session-death threshold" example |
| `incidents/<fingerprint>.md` | `### Incident <fingerprint>` heading; each followed by `**First seen:** … **Symptoms:** … **Root cause:** … **Fix:** … **Event trace:** <trace_id list>` | directory worked-example stub lands with Phase 0 kickoff |
| `adr/<NNN>-<slug>.md` | Status / Primitive / Supersedes / Seed source frontmatter; standard ADR sections (Context / Decision / Consequences / Alternatives / Open questions / Source evidence / Phase 2 Decision Inputs) | ADR 001 migrated + catalogue README |
| `INDEX.md` | auto-generated from the rest; per-class sections with links | regenerator script |

**Brittleness-signal machine-observable rule (C.1.5):** the lint script (C.6 pattern-9 sub-command) walks `harness_assumptions.md` and for each entry verifies the `Brittleness signal` field contains ≥1 of:
- a backtick-quoted grep pattern,
- a named CI check (`make <target>` or GitHub Actions job name),
- a named hook precondition (`.claude/hooks/<file>` + condition).

Entries whose signal is purely natural language (no backticks, no hook/check name) emit a WARN finding under a new rule ID `HA1` (harness-assumption signal not machine-observable).

#### §4.1.3 INDEX regeneration algorithm (C.1.7)

`scripts/internal/kb_index.py` (runnable as skill `/kb-index` or direct invocation):

1. Walk `knowledge/` excluding `_candidates/` (gitignored) and `_promoted/` (archive, not live content).
2. For each `.md` file at top level, emit a section in INDEX.md: filename, last-modified date from git, heading count.
3. For each directory (`adr/`, `incidents/`), emit a section listing entries with one-line summaries (first `###` heading + next 80 chars).
4. Emit a final `_promoted/` archive section: last 10 promotions (most recent first) from git log on `knowledge/_promoted/**`.
5. Write INDEX.md atomically (write to temp, fsync, rename).
6. Exit 0 on success; exit 1 on I/O error; exit 2 if a schema violation is detected mid-walk (e.g., a tracked `knowledge/*.md` file lacks a worked example).

**Determinism.** The regenerator must produce byte-identical INDEX.md for the same input tree (same git HEAD). The unit test (`tests/unit/test_kb_index.py::test_index_regenerates_deterministically`) runs the generator twice on a seeded fixture tree, diffs the outputs, asserts diff is empty.

**INDEX-staleness check (integration).** Phase 0 Readiness adds `diff INDEX.md <(regen INDEX.md)` as a grep-verifiable check; diff must be empty post-merge (confirms the generator is idempotent against the live tree and that no out-of-band edits have drifted INDEX).

### §4.2 Agent-readability scorecard — exactly 10 items + 7/10 floor (C.4, C.5)

**Canonical 10-item list** (frozen from §5-C Work bullet 3; committed to here; ADR 001 records the ≥7/10 floor; sub-plan may tighten but not loosen):

| # | Scorecard item | Pass criterion (machine-checkable recipe) |
|---|---|---|
| 1 | CLAUDE.md ≤ 200 lines | `wc -l < CLAUDE.md` ≤ 200 |
| 2 | Single canonical entry point for new sessions | `grep -c "^# " CLAUDE.md` at top = 1 (one H1 title); and `grep -l "## Project Overview" CLAUDE.md .claude/CLAUDE.md` finds ≥1 match (entry-point marker present) |
| 3 | Active governing plan findable in ≤2 hops from repo root | `grep -cE 'plans/[a-z_]+/governing_plan\.md' CLAUDE.md MEMORY.md` ≥ 1 (at least one root-level doc references an active governing plan directly) |
| 4 | All skills discoverable from `.claude/skills/` | every `.claude/skills/*/SKILL.md` has `name:` and `description:` frontmatter fields; no skill lives outside `.claude/skills/` |
| 5 | Lane registry authoritative not inferred | `.claude/rules/75_worktree_protection.md` exists AND enumerates ≥1 lane per pool (platform / browser / analyst / flex / control) |
| 6 | MEMORY.md indexes rather than recaps | ratio of `[link](path)` references in MEMORY.md > 0.1 per non-blank line (indexing); fail if MEMORY.md is pure prose recap |
| 7 | ADR index current | `grep -c '^\\| *\\[ADR' knowledge/adr/README.md` ≥ N where N = count of `knowledge/adr/[0-9].*\.md` files (plus `[A-Z][0-9]+-.*\.md` for pre-numeric ADRs like B8, G10) |
| 8 | KB INDEX current | `diff knowledge/INDEX.md <(scripts/internal/kb_index.py --stdout)` is empty |
| 9 | No orphan references in plans | `agent_readability_lint.py check pattern-9 plans/` exits 0 (no orphan cross-references to nonexistent files) |
| 10 | Rule files grep-discoverable from CLAUDE.md | every `.claude/rules/*.md` and `.claude/rules/**/*.md` is referenced from CLAUDE.md, .claude/CLAUDE.md, or another rule file (reachability graph has no disconnected nodes) |

**Runner spec (C.5, `scripts/internal/agent_readability_score.py`):**

- Invocable as `uv run python scripts/internal/agent_readability_score.py [--write | --stdout]`.
- `--write`: updates `knowledge/agent_readability_scorecard.md` with today's score + the 10 item booleans.
- `--stdout`: prints a machine-parseable block:
  ```
  agent_readability_score: 8/10
  item_1_claude_md_line_count: PASS (127 lines; limit 200)
  item_2_canonical_entry: PASS
  item_3_governing_plan_findable: PASS (plans/steward_platform/governing_plan.md)
  item_4_skills_discoverable: PASS (38 skills; 0 orphans)
  item_5_lane_registry_authoritative: PASS
  item_6_memory_indexes: FAIL (link-ratio 0.07; threshold 0.10)
  item_7_adr_index_current: PASS
  item_8_kb_index_current: PASS (diff empty)
  item_9_no_orphan_refs: PASS
  item_10_rules_grep_discoverable: FAIL (.claude/rules/orphan_rule.md not referenced)
  ```
- Exit code: 0 if score ≥ floor from ADR 001 (7/10); 2 if below floor; 1 on invocation error.
- Accepts `--floor N` override for sub-plan tightening (must be ≥7 per ADR 001 constraint; runner itself enforces this — `--floor 6` is rejected with an error message citing ADR 001).

**Scorecard file schema (`knowledge/agent_readability_scorecard.md`):**

```markdown
# Agent-Readability Scorecard

**Floor (per ADR 001):** ≥7/10
**Current score:** 8/10 (last run YYYY-MM-DD HH:MM UTC)
**Phase 0 baseline:** <recorded at Phase 0 Readiness>
**Phase 1 end score:** <recorded at Phase 1 end; must ≥ Phase 0 baseline>

## Items

| # | Item | Status | Detail |
|---|---|---|---|
| 1 | CLAUDE.md ≤ 200 lines | PASS | 127 lines |
| ... | ... | ... | ... |

## Run log

- YYYY-MM-DD: <score>/10 — <brief> — <operator/lane> — <trigger>
```

**Floor-lockdown note.** ADR 001 §D3 states the floor is ≥7/10; sub-plans may tighten to 8/10 or 9/10. The runner enforces this by rejecting `--floor` values below 7 with an explicit error citing ADR 001. This is a **defense-in-depth** measure against accidental loosening via a script invocation.

### §4.3 Archivist C↔D interface contract (C.11)

**Problem statement.** Primitive D owns the archivist (nightly + end-of-session inflow script). Primitive C owns the KB that receives promoted artifacts. The interface between them is ADR 010's operator-gated promotion step. Without an explicit contract, D could silently assume in-place editing of NOTES/PLAYBOOKS/anti_patterns (violating ADR 010 commit policy) OR C could assume D-side candidate-file schemas that D doesn't actually produce.

**Interface contract (committed verbatim to both `scripts/internal/archivist.py` docstring header AND `knowledge/INDEX.md`):**

```markdown
## Archivist C↔D Interface Contract

**D writes to:** `knowledge/_candidates/<YYYY-MM-DD>_<kind>.md`
  where <kind> ∈ {lessons, changelog, gc}

**D does NOT write to:** anything else under `knowledge/`.
  D MUST NOT edit NOTES.md, PLAYBOOKS.md, anti_patterns.md, harness_assumptions.md,
  incidents/*, adr/*, or INDEX.md. These are operator-promoted surfaces.

**C reads from:** `knowledge/_candidates/*.md` (session-local; gitignored)
**C writes to:** `knowledge/NOTES.md` or `knowledge/PLAYBOOKS.md` or
  `knowledge/anti_patterns.md` (appended under operator direction) AND
  `knowledge/_promoted/<YYYY-MM-DD>_<class>_<hash>.md` (archive entry).

**Gate between them:** operator review of candidate files via `/run-archivist`
  skill or direct edit. No automatic promotion. No autonomous state mutation
  (binding constraint from ADR 010 §Decision).

**Event emission on promotion (C-side):**
  - `kb_artifact_promoted` (event_type per Primitive A schema v1.0; fields:
    artifact_class, source_candidate_path, promoted_path, operator_id,
    trace_id, promoted_at)
  - `kb_artifact_unpromoted` — emitted on rollback (§4.7)

**Event emission on candidate generation (D-side):**
  - `archivist_candidate_generated` (fields: candidate_path, candidate_count,
    trigger, archivist_mode, generated_at)

**Failure modes:**
  - D writes outside `_candidates/`: C-side lint flags; archivist refuses to
    run until resolved.
  - C promotes without emitting event: Pattern 8 (Observable-by-default) lint
    flags in post-merge review.
  - Operator promotes a candidate file D hasn't written (fake candidate):
    `kb_artifact_promoted` event has no matching `archivist_candidate_generated`
    upstream event; review-driver precheck V7 (added in §4.6) flags.
```

**Whose review gate.** Operator-gated per ADR 010. The `/run-archivist` skill presents candidates; the operator (or orchestrator on the operator's behalf if explicitly sanctioned — e.g., during an auto-mode session with `autoMode.environment` permitting KB promotion) edits to promote. **No auto-promotion path exists.** This is a hard invariant, enforced by:
- `archivist.py` refusing to write anywhere other than `_candidates/`
- the `kb_artifact_promoted` event carrying a mandatory `operator_id` field (cannot be auto-generated; a missing `operator_id` → event rejected by the event-schema validator)
- review-driver V7 precheck (§4.6) blocking PRs that add `_promoted/` entries whose upstream `archivist_candidate_generated` event is missing

### §4.4 `/create-plan` skill refusal logic (C.8)

The existing SKILL.md stub (PR #2762) specifies the refusal conditions in prose. Packet C-Exec lifts them into a codified acceptance test + runner check. Full spec:

#### §4.4.1 Refusal conditions (4 cases, ordered by detection)

| # | Condition | Detection algorithm | Refusal message fragment |
|---|---|---|---|
| R1 | `## Verification Plan` section is missing | `grep -c '^## Verification Plan' <path>` = 0 | "Missing `## Verification Plan` section" |
| R2 | Section is present but table is empty (header row only) | Within the §Verification Plan block, count table rows excluding header + separator; if = 0 | "`## Verification Plan` section is empty (header row only)" |
| R3 | Any row contains a placeholder token in the Verification surface column | regex over rows: `TBD|TODO|FIXME|XXX` (case-insensitive) in column 3 | "Row for deliverable `<name>` carries placeholder surface `<val>`" |
| R4 | Any Work bullet lacks a matching row (in same file OR global map) | Run `agent_readability_lint.py check verification-contract <path>` and fail if VC3 findings present | "Work bullet §<N.M> has no Verification Plan row and no map.md coverage" |

#### §4.4.2 Exact refusal message format

The skill MUST emit the refusal in this exact format (tested by `tests/unit/test_create_plan_refusal.py`):

```
/create-plan REFUSED: Pattern 10 (§10.9) requires a complete Verification Plan section.

Refusal reasons:
  R<N>: <fragment from §4.4.1 table>
  [additional R<N> lines if multiple conditions fire]

See the worked example in plans/_templates/sub_plan.md §Verification Plan.
See Pattern 10 table at §10.9 of plans/steward_platform/governing_plan.md for
deliverable-class → surface-class defaults.

No plan file was written. Fix the above and re-invoke /create-plan.
```

Exit code (if skill is scripted): 2. If skill is operator-invoked interactively, the refusal message is displayed and no file is created.

#### §4.4.3 Acceptance command (added to SKILL.md)

```bash
# Acceptance — must be runnable by any lane to verify the skill refuses correctly
uv run python -m pytest tests/unit/test_create_plan_refusal.py -v
# Expected: 4 tests pass (one per refusal condition R1-R4)
```

The acceptance command replaces the current stub's "manual checklist" framing. Packet C-Exec lifts refusal into an executable test.

### §4.5 `agent_readability_lint.py` extensions (C.6, C.7)

The existing script (PR #2762) has:
- `check verification-contract` — Pattern 10 rule set, lives + shipped, with rules VC1/VC2/VC3.
- `check load-bearing-ownership` — Pattern 9 scaffold (returns empty findings).

Packet C-Exec adds the concrete Pattern 9 rule set AND a new `check pattern-11` sub-command. Both consume the shared plan-walker core (§13.2 risk #2 of verification_contract/shaping.md codified this shared-module decision).

#### §4.5.1 Pattern 9 — `check load-bearing-ownership` (C.6)

**Rule set:**

| Rule ID | Condition | Severity |
|---|---|---|
| LBO1 | `§N.M` cross-reference to a script/module/file (via backtick path or inline `scripts/**`/`src/**`/`.claude/**` reference) in any plan §N.M section, where that target has no owning-primitive Work bullet or Readiness criterion | BLOCK |
| LBO2 | Plan text mentions a script/skill/hook by name (`/<skill>`, `<script.py>`) and that artifact exists in the repo, but has no reverse-link (no plan section enumerates it) | WARN |
| LBO3 | A script/module/file exists in `scripts/internal/**`, `src/bid_euchre/ops/**`, or `.claude/skills/**`, is referenced in at least one plan §N.M section, but the reference is in an `_archive/` or `draft<N>` file only (no live-plan enumeration) | WARN |

**Algorithm:**
1. Walk `plans/**/*.md` excluding `_archive/` and files matching `draft\d+`.
2. Extract all backtick-quoted paths and inline script/skill references (`scripts/internal/<x>.py`, `.claude/skills/<x>/`, `src/bid_euchre/<x>.py`, `/<skill-name>`).
3. For each reference, resolve it to a filesystem path (if the file exists).
4. Walk the *same* plan set, collecting `§N.M Work` and `§N.M Readiness/Phase 0 Readiness` bullets.
5. For each reference from step 3, require ≥1 Work or Readiness bullet that mentions the target (or its basename) by backtick or inline name.
6. Missing → LBO1 (BLOCK) if the reference is in §5-X, §6.4, or §13 (high-leverage sections); LBO2/LBO3 otherwise.

**Unit-test fixtures (`tests/unit/test_agent_readability_lint.py::TestPattern9`):**
- Positive (clean): fixture plan with a script reference that has matching Work bullet → no findings.
- Negative-LBO1: fixture plan referencing a script in §5 with no Work bullet → LBO1 finding.
- Negative-LBO2: script exists, referenced in prose, no plan enumeration → LBO2.
- Archive-only: reference in `_archive/draft3.md` only → LBO3 if no live enumeration.

#### §4.5.2 Pattern 11 — `check pattern-11` (C.7)

**Purpose.** Flag implementation PRs whose scope crosses ≥3 files or touches ≥2 primitives without being preceded by a shaping doc. This codifies the §10.9 Pattern 11 "shape-then-execute dispatch" discipline as a run-against-existing precheck (run-against-existing because the lint operates on the live repo, not the PR diff — per shaping doc §3.2(iii) lineage).

**Rule set:**

| Rule ID | Condition | Severity |
|---|---|---|
| P11_1 | `plans/steward_platform/<N>_primitive_<X>/` directory exists AND contains an execution-packet-shaped PR reference (per git log) but NO `shaping.md` sibling file | BLOCK |
| P11_2 | A PR's merge commit adds ≥3 files under `src/bid_euchre/**` OR `scripts/internal/**` OR `.claude/skills/**` AND PR body does not cite a shaping doc under `plans/**/shaping.md` or `plans/**/_sub_plan.md` AND the added files span ≥2 primitives (per §10.9 Pattern 6 per-surface owner header) | WARN |
| P11_3 | A `plans/**/shaping.md` file exists with a "Packet" reference (`Packet <id>`) AND no follow-up PR cites that packet as its implementing PR for >30 days | WARN |

**Note on scope.** `check pattern-11` is **run-against-existing**, not PR-diff-based. It walks the repo state on a given HEAD and flags structural violations. The PR-diff-based Pattern 11 precheck (i.e., "this specific PR adds 5 files and didn't cite a shaping doc") lives in `review_driver.py` V7 precheck (§4.6), which is the PR-time enforcement surface. The two surfaces are complementary (defense-in-depth).

**Algorithm for P11_2 (post-hoc repo walk):**
1. `git log --since=<N days> --pretty=format:'%H' --name-only` yields PRs and their touched files.
2. For each PR merge commit, count added files under the trigger paths.
3. If ≥3, search PR body (via `gh pr view`) for `plans/**/shaping.md` or `plans/**/_sub_plan.md` references.
4. If no reference and file-set spans ≥2 owning primitives, emit P11_2.

Emit WARN (not BLOCK) for post-hoc because retroactive fixes are impractical; the signal drives a "we should have shaped this" feedback loop, not a merge block.

**Unit-test fixtures (`tests/unit/test_agent_readability_lint.py::TestPattern11`):**
- Positive: shaping.md exists in primitive directory, execution PR cites it → no findings.
- Negative-P11_1: primitive directory exists without shaping.md → P11_1 finding.
- Negative-P11_2: fixture PR adds 5 files across 2 primitives, no shaping citation → P11_2 (via mocked git log).
- Negative-P11_3: shaping.md with "Packet abc" reference, mocked git log shows no follow-up cite → P11_3.

#### §4.5.3 Shared plan-walker contract

The `walk_plans()` function + `DeliverableBullet`, `VerificationRow` dataclasses in `agent_readability_lint.py` are the single source of truth for plan parsing across Patterns 9, 10, and 11. Per §13.2 risk #2 of `verification_contract/shaping.md`:

> Both rule sets consume the same plan-walker core and the same row-parser primitives. Breaking or regressing the plan-walker *silently degrades all three Pattern enforcements at once.*

Packet C-Exec adds dedicated plan-walker unit tests (`tests/unit/test_agent_readability_lint.py::TestPlanWalker`) that run independently of Pattern 9/10/11 tests and must pass before any rule-specific test runs. This is the shared-module test isolation discipline called out in shaping §13.2.

### §4.6 review-driver `V7` precheck (commit-policy enforcement, coordinated with existing V1–V6)

The `verification_contract/shaping.md` §3.4 table defines V1–V6 (Pattern 10 merge-time checks). Packet C-Exec adds **V7** — a commit-policy precheck specific to Primitive C's ADR 010 binding:

| Check ID | Condition | Severity | Action |
|---|---|---|---|
| V7 | PR adds a file under `knowledge/_promoted/**` AND no `archivist_candidate_generated` event exists upstream (via event-stream query over last 30 days) matching the promoted artifact's class + approximate timestamp | **BLOCK** | Fail precheck with message: "Promoted KB artifact has no archivist candidate upstream. Either (a) produce the candidate via `/run-archivist`, then promote, OR (b) mark the PR as a manual-promotion exception with explicit operator sanction in the PR body" |

**Rationale.** Without V7, a contributor could bypass the archivist inflow entirely and land `_promoted/` entries directly. ADR 010's "operator-gated promotion" constraint would degrade to "operator wrote a file and committed it" with no candidate audit trail. V7 enforces the audit trail.

**Event-schema integration.** V7 queries the event schema (Primitive A) for `archivist_candidate_generated` events. Primitive A's Phase 0 Readiness includes emitting this event from the archivist. V7 ships disabled (feature flag `ENABLE_V7_COMMIT_POLICY`) until Primitive A's archivist event emission is live — this coordination is noted in §6.3 below.

### §4.7 Commit policy (C.9)

ADR 010 §Decision: "only promoted KB artifacts are committed."

**Tracked paths (committed):**
- `knowledge/NOTES.md`, `PLAYBOOKS.md`, `anti_patterns.md`, `harness_assumptions.md`, `agent_readability_scorecard.md`, `external_signal_sources.md`, `INDEX.md`
- `knowledge/adr/**/*.md`
- `knowledge/incidents/**/*.md`
- `knowledge/_promoted/**/*.md` (post-promotion archive; audit trail)

**Gitignored paths (NOT committed):**
- `knowledge/_candidates/**` (archivist inflow; session-local)
- `knowledge/_scratch/**` (if ever introduced; also session-local)

**`.gitignore` entries (added by Packet C-Exec):**
```
# KB — unpromoted archivist inflow (per ADR 010: only promoted artifacts committed)
knowledge/_candidates/
knowledge/_scratch/
```

**Promotion transition algorithm (untracked → tracked):**

When an operator promotes a candidate:

1. Operator invokes `/run-archivist --promote <candidate-path>` OR edits NOTES/PLAYBOOKS/anti_patterns directly.
2. Archivist appends to the target file, computes `<hash>` (short SHA of the promoted content), and writes `knowledge/_promoted/<YYYY-MM-DD>_<class>_<hash>.md` with frontmatter citing the source candidate path + operator ID + trace ID.
3. Archivist emits `kb_artifact_promoted` event (Primitive A schema).
4. `git add knowledge/NOTES.md knowledge/_promoted/<new-file>` (both paths stage in a single commit).
5. Commit message: `kb(promote): <artifact_class> — <short description> (candidate: <candidate-path>)`
6. Review-driver V7 precheck verifies the upstream `archivist_candidate_generated` event exists.

**Rollback (un-promotion):**

1. Operator invokes `/run-archivist --unpromote <promoted-path>` (or manual process: `git revert <promotion-commit>`).
2. Revert commit removes the `_promoted/` entry AND reverts the NOTES/PLAYBOOKS append.
3. If via skill: source candidate file is re-created under `_candidates/<YYYY-MM-DD>_unpromoted.md` for re-review.
4. Emit `kb_artifact_unpromoted` event with `reverted_promotion_event_id` pointing at the original promotion event.

**Pattern 7 conformance.** Rollback is one-command (`git revert <sha>` OR `/run-archivist --unpromote`); rollback emits an event; rollback is deterministic.

**Rollback test (Packet C-Exec validation):**
```bash
# Part of Packet C-Exec integration validation
# Forward: promote a fixture candidate
uv run python scripts/internal/archivist.py --promote data/fixtures/kb/test_candidate.md
# Expect: NOTES.md has +1 entry; _promoted/ has +1 file; kb_artifact_promoted event fires
# Reverse: un-promote
uv run python scripts/internal/archivist.py --unpromote knowledge/_promoted/<the-file>.md
# Expect: NOTES.md entry removed; _promoted/ entry removed; kb_artifact_unpromoted event fires
```

---

## §5. Packet C-Exec execution spec

Concrete enough that an author lane can execute without additional shaping. The orchestrator may choose to decompose C-Exec into sub-packets (C-Exec.1 / .2 / .3) if scope exceeds comfortable single-PR size; §5.5 suggests a decomposition.

### §5.1 Scope declared (Packet C-Exec)

**Files created (new):**

- `knowledge/NOTES.md` (with worked example)
- `knowledge/PLAYBOOKS.md` (with worked example)
- `knowledge/anti_patterns.md` (with ≥1 worked example)
- `knowledge/harness_assumptions.md` (with ≥5 entries per §5-C Readiness)
- `knowledge/INDEX.md` (initial, generated by runner)
- `knowledge/agent_readability_scorecard.md` (initial scorecard, score recorded)
- `knowledge/external_signal_sources.md` (seed content per §14 open item 17)
- `knowledge/adr/README.md` (ADR catalog index)
- `knowledge/adr/001-platform-pattern-reset.md` (migrated copy from `plans/steward_platform/adrs/001-platform-reset.md`)
- `knowledge/incidents/_example_fingerprint.md` (worked example; uses a historical fingerprint)
- `scripts/internal/kb_index.py` (INDEX regeneration)
- `scripts/internal/agent_readability_score.py` (scorecard runner)
- `scripts/internal/memory_compact.py` (MEMORY.md compaction)
- `tests/unit/test_kb_index.py`
- `tests/unit/test_agent_readability_score.py`
- `tests/unit/test_memory_compact.py`
- `tests/unit/test_create_plan_refusal.py` (refusal-logic test)
- `tests/unit/test_agent_readability_lint.py` — extended with `TestPattern9` and `TestPattern11` classes (if file doesn't exist yet, Packet C-Exec creates it alongside existing test scaffolding)
- `data/fixtures/kb/test_candidate.md` (rollback-test fixture)
- `data/fixtures/plans/` (Pattern 9/11 lint test fixtures; scaffolded per test)
- `plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` (C.12 — sub-plan placeholder; may tighten floor later)
- `plans/steward_platform/3_primitive_C/phase0_readiness.md` (C.P0R — closeout artifact with per-item grep-verifiable check)

**Files modified:**

- `scripts/internal/agent_readability_lint.py`:
  - Replace `check_load_bearing_ownership` scaffold with the concrete rule set (LBO1/LBO2/LBO3).
  - Add `check pattern-11` sub-command with rules P11_1/P11_2/P11_3.
  - Add `HA1` rule for harness-assumption brittleness-signal machine-observable check (invoked from Pattern 9 run).
- `scripts/internal/review_driver.py`:
  - Add `V7` commit-policy precheck (behind feature flag `ENABLE_V7_COMMIT_POLICY`, default off until Primitive A archivist event emission is live).
- `.claude/skills/create-plan/SKILL.md`:
  - Lift the "Stub (Packet 2b)" section into codified refusal-logic implementation.
  - Add the acceptance command per §4.4.3.
- `.gitignore`:
  - Add `knowledge/_candidates/` and `knowledge/_scratch/`.
- `.claude/rules/deferred/30_data_contract.md`:
  - Extend to reference ADR 010 commit policy for KB; cite the tracked vs. gitignored path split.
- `scripts/internal/archivist.py` (coordination with Primitive D):
  - If the file exists at Packet C-Exec dispatch: add the C↔D interface contract block as docstring header (§4.3).
  - If it does NOT exist: Packet C-Exec creates a stub `archivist.py` with only the docstring header contract — Primitive D shaping later fills the implementation. This avoids circular dependency (C needs the contract documented; D needs C's KB structure first).
- `plans/steward_platform/verification_contract/map.md`:
  - Extend C.1–C.7 rows with more granular C.1.1–C.1.7 coverage (per §3 table above).
- `MEMORY.md`:
  - Note the migration of ADR 001 → `knowledge/adr/001-platform-pattern-reset.md` with a back-reference at the old seed location.

### §5.2 Order of operations (Packet C-Exec)

1. **Branch + scope lock.** Create `primitive-c/kb-scaffolding-execution` from `origin/main`. Read this shaping doc, §5-C of governing plan, ADR 001, ADR 010.
2. **KB skeleton files** (C.1.1–C.1.5) — author with worked examples per §4.1.2 schemas. No promotion events yet; files land as tracked content.
3. **ADR migration** (C.1.6) — copy `plans/steward_platform/adrs/001-platform-reset.md` → `knowledge/adr/001-platform-pattern-reset.md`; add `adr/README.md` catalog index; leave the seed location pointing at the KB home with a migration note.
4. **INDEX regeneration script** (C.1.7) — write `kb_index.py` + unit test. Run it; commit the generated `INDEX.md`.
5. **Scorecard runner** (C.4, C.5) — write `agent_readability_score.py` + unit tests per §4.2 recipes. Run it; commit scorecard file with initial score (≥7/10 floor must be met for Phase 0 Readiness; if actual score is <7/10, EXCL: escalate to orchestrator — see §6.4 coordination).
6. **Commit-policy** (C.9) — add `.gitignore` entries; extend `30_data_contract.md`. Create `data/fixtures/kb/test_candidate.md` for rollback smoke. Execute rollback test (§4.7) as integration validation; paste output into PR body.
7. **Lint extensions** (C.6, C.7) — implement Pattern 9 rules + Pattern 11 rules + `HA1`. Add unit tests under `tests/unit/test_agent_readability_lint.py::TestPattern9` and `::TestPattern11`. Run `uv run python -m pytest tests/unit/test_agent_readability_lint.py -v` — all tests pass.
8. **Self-run lint** — run `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/`; `... check load-bearing-ownership plans/`; `... check pattern-11 plans/`. All three exit 0 or only WARN (never BLOCK).
9. **/create-plan refusal codification** (C.8) — update SKILL.md; add `tests/unit/test_create_plan_refusal.py`; run it.
10. **review_driver V7 stub** (§4.6) — add V7 precheck code path behind `ENABLE_V7_COMMIT_POLICY` flag (default off). Smoke-test by enabling flag locally with a mocked event stream.
11. **MEMORY.md compaction** (C.10) — write `memory_compact.py` + unit test; run compaction against current MEMORY.md in dry-run mode.
12. **Archivist interface contract** (C.11) — if `scripts/internal/archivist.py` doesn't exist, create stub with docstring contract only; if it exists, append docstring.
13. **Phase 0 Readiness closeout** (C.P0R) — author `plans/steward_platform/3_primitive_C/phase0_readiness.md` with grep-verifiable check for each §5-C Readiness bullet.
14. **Sub-plan placeholder** (C.12) — author `plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` per template (may be empty body with TBD-but-not-placeholder sections; the sub-plan itself tightens in a follow-up if the floor needs to move to 8/10 or 9/10).
15. **Rebase + validate** — `git fetch origin main && git rebase origin/main && make check-gated`. Run as foreground (never background per CLAUDE.md warning).
16. **Open PR.** Title: `feat+docs(steward-platform): implement Primitive C Phase 0 scaffolding — KB structure + scorecard + lint extensions + commit policy (Packet C-Exec)`. Body includes `## Verification Performed` with lint/test output per §5.3.

### §5.3 Validation commands (Packet C-Exec Tier 2)

```bash
# Unit
uv run python -m pytest tests/unit/test_kb_index.py -v
uv run python -m pytest tests/unit/test_agent_readability_score.py -v
uv run python -m pytest tests/unit/test_memory_compact.py -v
uv run python -m pytest tests/unit/test_create_plan_refusal.py -v
uv run python -m pytest tests/unit/test_agent_readability_lint.py -v
# Expected: all pass; Pattern 9 + Pattern 11 test classes present + green

# Integration
uv run python scripts/internal/kb_index.py --stdout | diff knowledge/INDEX.md -
# Expected: diff is empty

uv run python scripts/internal/agent_readability_score.py --stdout
# Expected: score >= 7; exit 0

uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/
uv run python scripts/internal/agent_readability_lint.py check load-bearing-ownership plans/
uv run python scripts/internal/agent_readability_lint.py check pattern-11 plans/
# Expected: all three exit 0 (or exit 2 with only WARN findings per --warnings-ok)

# Rollback test
uv run python scripts/internal/archivist.py --promote data/fixtures/kb/test_candidate.md
uv run python scripts/internal/archivist.py --unpromote knowledge/_promoted/<generated-file>.md
# Expected: forward emits kb_artifact_promoted; reverse emits kb_artifact_unpromoted;
#   NOTES.md returns to pre-promotion state byte-identical

# Negative-path (exercises /create-plan refusal)
uv run python -m pytest tests/unit/test_create_plan_refusal.py::test_r1_missing_section -v
uv run python -m pytest tests/unit/test_create_plan_refusal.py::test_r3_placeholder_surface -v
# Expected: both pass (refusal fires correctly)

# Tier 2
make check-gated
# Expected: full validation passes (foreground, concurrency-capped per CLAUDE.md)
```

### §5.4 Coordination notes (Packet C-Exec)

- **Dependency on Primitive A (event schema):** The `kb_artifact_promoted` / `kb_artifact_unpromoted` / `archivist_candidate_generated` events require the event schema (Primitive A Phase 0) to be live. Packet C-Exec ships event emissions in the archivist and scorecard runners **guarded by `ENABLE_KB_EVENT_EMISSION` feature flag (default off)**. When Primitive A Phase 0 ships, a follow-up flips the flag on. Same pattern for V7 precheck (`ENABLE_V7_COMMIT_POLICY` flag).
- **Dependency on Primitive D (archivist):** The `archivist.py` module may or may not exist at Packet C-Exec dispatch. If not, Packet C-Exec creates a stub with only the interface contract docstring. D's shaping packet (separate, orchestrator-dispatched) consumes this stub as its interface.
- **Non-overlap with Primitive A Phase 0 execution (Packet 3):** Packet C-Exec modifies `ops/event_taxonomy.py` only by reading its emitted event types (via import or string reference); it does not define new event types — those are Primitive A's scope. Rebase vigilance required if Packet 3 lands first with a modified event catalog.
- **Non-overlap with verification_contract (Packet 2b shipped):** Packet C-Exec extends `agent_readability_lint.py` — the Pattern 10 sub-command shipped in Packet 2b remains unchanged; Packet C-Exec adds two sibling sub-commands (`load-bearing-ownership`, `pattern-11`) and one rule helper (`HA1`). All share the plan-walker; Packet C-Exec adds plan-walker unit tests if absent.
- **ADR 001 migration:** Packet C-Exec migrates the seed file to `knowledge/adr/001-platform-pattern-reset.md` and leaves a 3-line migration note at the seed location (`plans/steward_platform/adrs/001-platform-reset.md`) pointing at the new canonical path. The existing file becomes a stable redirect (not deleted) until the next Phase 0 cleanup sub-plan decides whether to delete.

### §5.5 Suggested decomposition (if Packet C-Exec scope exceeds comfortable single-PR size)

The orchestrator may decompose Packet C-Exec into three sub-packets dispatched in sequence:

| Sub-packet | Scope | Estimated size |
|---|---|---|
| **C-Exec.1** — KB skeleton + commit policy | §5.1 items 2, 3, 4 (KB files + ADR migration + INDEX script + .gitignore) + rollback test | ~15 files, ~600 lines |
| **C-Exec.2** — Scorecard + lint extensions | §5.1 items 5, 7, 8 (scorecard runner + Pattern 9/11 lint + HA1 + fixtures) | ~10 files, ~800 lines |
| **C-Exec.3** — Skill + review-driver V7 + compaction + archivist contract | §5.1 items 9, 10, 11, 12 (/create-plan upgrade + V7 + MEMORY compaction + archivist stub) + closeout artifacts | ~10 files, ~500 lines |

Sub-packets are **sequentially dependent** (C-Exec.2 needs C.1 KB skeleton for scorecard item 8 "KB INDEX current" to pass; C-Exec.3 needs C.2 for review-driver V7 to match event types the lint discovered). If orchestrator dispatches in sequence, coordination cost is low. Parallel dispatch is **not recommended** — rebase conflicts on `agent_readability_lint.py` + `.claude/skills/create-plan/SKILL.md` are likely.

### §5.6 Packet C-Exec success criterion

> Packet C-Exec (or its decomposition C-Exec.1+.2+.3) is complete when:
> (a) all files in §5.1 are created or modified per spec,
> (b) §5.3 validation commands all pass,
> (c) agent-readability scorecard runs cleanly and scores ≥7/10 per ADR 001 floor,
> (d) rollback test passes (forward promotion + reverse un-promotion produces matching events + byte-identical NOTES.md after reverse),
> (e) the C↔D interface contract is present verbatim in both `archivist.py` docstring and `knowledge/INDEX.md`,
> (f) PR merged with `## Verification Performed` section pasting lint output + scorecard output + rollback test output.
>
> After Packet C-Exec merges, Primitive C Phase 0 Readiness is ready for evaluation against the §5-C Readiness checklist. Phase 0 closeout artifact (§5.1 `phase0_readiness.md`) records the per-item evaluation.

---

## §6. Self-review against "spawn reviewer agent" step

### §6.1 Constraint encountered

Same structural constraint as `verification_contract/shaping.md` §13 and `1_primitive_A/shaping.md`: the analyst lane's YAML frontmatter structurally disallows the `Agent` tool (enforced mechanically). Substitute: outline stress-test before drafting, documented below for orchestrator audit.

### §6.2 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| Every §5-C Work bullet has a spec row in §3 deliverable table | §3 enumerates C.1.1–C.1.7, C.2, C.3, C.4–C.7, C.8–C.12, C.P0R | ✓ (18 rows covering §5-C Work bullets + Readiness bullets) |
| Pattern 10 table applied to every deliverable | §3 surface column populated per Pattern 10 table from §10.9 | ✓ (no row blank) |
| Agent-readability scorecard has exactly 10 items | §4.2 table counts 10 rows | ✓ |
| Each scorecard item has a machine-checkable recipe | §4.2 Pass-criterion column is grep/wc/diff/script for every row | ✓ |
| 7/10 floor from ADR 001 explicitly cited and defended | §4.2 "Floor-lockdown note" + runner enforces `--floor ≥ 7` | ✓ |
| Commit policy binds to ADR 010 | §4.7 cites ADR 010 §Decision; tracked/gitignored split matches | ✓ |
| Archivist C↔D contract specifies who-writes-what-where | §4.3 lists D-writes, C-writes, gate, events on both sides, 3 failure modes | ✓ |
| /create-plan has all 4 refusal conditions codified with exact message format | §4.4.1 (4 rows) + §4.4.2 (exact format) | ✓ |
| Pattern 9 rule set lands with ≥2 rule IDs | §4.5.1 has LBO1/LBO2/LBO3 + HA1 | ✓ (4 rules) |
| Pattern 11 rule set lands with ≥2 rule IDs | §4.5.2 has P11_1/P11_2/P11_3 | ✓ |
| Packet C-Exec spec covers scope + order + validation + coordination | §5.1 scope + §5.2 order + §5.3 validation + §5.4 coordination + §5.5 decomposition + §5.6 success criterion | ✓ |
| Phase 2 Decision Inputs subsection present | §7 below | ✓ |
| Verification Plan section present | §8 below | ✓ |

### §6.3 Risks surfaced during self-review (orchestrator decision)

1. **Scorecard item 6 "MEMORY.md indexes rather than recaps" threshold is arbitrary (link-ratio > 0.1).** If current MEMORY.md scores below 0.1, item 6 fails at Phase 0 kickoff and the whole scorecard may drop below 7/10. **Mitigation:** §5.2 step 5 flags EXCL to orchestrator if initial score <7/10; orchestrator decides to (a) ratchet MEMORY.md pre-score or (b) tune the threshold in C.12 sub-plan. Suggest Packet C-Exec author pre-measures at branch start.
2. **C↔D interface assumes `archivist.py` can be stubbed.** If Primitive D's shaping (dispatched separately) produces a different file layout (e.g., `src/bid_euchre/archivist/__init__.py` instead of `scripts/internal/archivist.py`), C's stub location conflicts. **Mitigation:** §5.4 coordination note names the stub path; if D's shaping picks a different path, D-side shaping PR revises the contract pointer in C (cheap one-line edit).
3. **Event emission feature flags create a "dark launch" pattern.** C ships event emission behind flags (default off) because Primitive A Phase 0 may not have landed. Risk: flag never flipped, events never fire, Pattern 8 compliance silently decays. **Mitigation:** phase0_readiness.md checklist includes an item "feature flag `ENABLE_KB_EVENT_EMISSION` is set to true" that gates Phase 0 Readiness declaration. Concrete: add a grep for `ENABLE_KB_EVENT_EMISSION = True` (or equivalent) in the settings file.
4. **V7 precheck coordination with Primitive A.** V7 requires the `archivist_candidate_generated` event stream. If V7 ships before A's archivist event emission, it blocks legitimate `_promoted/` commits. **Mitigation:** V7 ships with flag default off (§4.6). Flag flip is a separate 1-line PR post Primitive A landing.
5. **Pattern 11 `check pattern-11` is retroactive.** Flagging existing PRs that violated the shape-then-execute discipline is not actionable (can't re-shape a merged PR). Risk: the lint is a noise generator. **Mitigation:** P11_2 is WARN, not BLOCK. P11_3 (30-day stale shaping) gives an actionable signal — a shaping doc without follow-up is either obsolete (retire) or stale (re-dispatch). P11_1 (primitive dir without shaping.md) is BLOCK because new primitive dirs MUST ship with shaping.

### §6.4 Coordination-timing risks

- **ADR 001 migration timing.** If the migration to `knowledge/adr/001-platform-pattern-reset.md` happens before `knowledge/` directory exists, migration fails. Order is fixed in §5.2: KB skeleton (step 2) before ADR migration (step 3). Author lane must not reorder.
- **Scorecard baseline recording.** Phase 0 kickoff scorecard is the baseline against which Phase 1 end-score is compared (§5-C Phase 1 Validation). Recording must happen at Packet C-Exec merge, not before. §5.2 step 5 (scorecard runner) runs the scorecard and writes to `knowledge/agent_readability_scorecard.md`; the merge commit captures the baseline.

### §6.5 Orchestrator option

If the orchestrator wants independent adversarial review before Packet C-Exec dispatch, dispatch a separate packet to any flex lane (not analyst-b, for recusal) with the prompt: "Review `plans/steward_platform/3_primitive_C/shaping.md` for (1) scorecard machine-check recipe adequacy, (2) archivist C↔D contract completeness, (3) commit-policy rollback-test executability, (4) Pattern 9 + Pattern 11 rule-set false-positive risk, (5) Packet C-Exec decomposition granularity." Recommended but not blocking.

---

## §7. Phase 2 Decision Inputs

**Portability readiness:** Primitive C is portable-by-design once the 10-item scorecard is committed. The scorecard itself is a general KB-discipline measurement instrument — every bullet generalizes to non-Bid-Euchre repos (CLAUDE.md line count, KB INDEX currency, skill discoverability, orphan references). The `knowledge/` layout + ADR 010 commit policy are also generic. One Bid-Euchre-specific item: scorecard item 5 "Lane registry authoritative" is tested via `.claude/rules/75_worktree_protection.md`; cells without a worktree-based lane model would adapt the test. Source: §4.2 scorecard table; per-item Pass criterion uses generic file-shape assertions.
**Meta-layer need:** no new meta-layer surface introduced by Primitive C beyond the ADR catalog (which is part of C itself). `knowledge/adr/` is per-cell; no cross-cell ADR aggregation proposed at this shaping stage. If Phase 2 decides portability-is-a-deliverable, the scorecard map could serve as the portability checklist; that's a Phase 2 decision input, not a Primitive C construction deliverable.
**Kill signal for primitive(s) named:** N/A at shaping. If Packet C-Exec lands and the scorecard falls below 7/10 at Phase 0 Readiness, §11-C kill criterion (existing: "<3 promoted lessons cited downstream during proving run → collapse to single NOTES.md per repo") does not fire on scorecard grounds alone — the scorecard is a Readiness gate, the kill criterion is a usage-based outcome. This shaping doc does not introduce new kill criteria.
**Re-evaluation needed in Phase 3:** yes, conditional on — (a) ADR 010's soft re-evaluation triggers firing (NOTES.md > 20 KB / 500 entries, OR archivist inflow > 10 candidate lessons/nightly sustained ≥1 week); (b) Pattern 9 or Pattern 11 lint false-positive rate >5% sustained (authors regularly invoke `--warnings-ok` bypass); (c) scorecard score in Phase 1 exactly equals Phase 0 baseline AND no C.12 sub-plan tightened the floor (indicates write-discipline decay). Any single trigger routes to the Phase 2 Decision-inputs digest with "revisit Primitive C assumptions" framing.
**Surprise finding:** The C↔D contract surfaces a previously-unnamed invariant: `kb_artifact_promoted` events must carry a mandatory `operator_id`, and the event-schema validator must reject events missing it. Without this, the "operator-gated promotion" ADR 010 constraint degrades to "some lane wrote a file." This validator-rejection rule is a Pattern 8 (Observable-by-default) extension and should be added to §5-A Phase 0 Readiness as a cross-reference — flagged for Primitive A shape pickup.
**Disposition:** open (pending orchestrator dispatch of Packet C-Exec or its decomposition)

---

## §8. Verification Plan

_Required per Pattern 10 (§10.9 governing plan). Every §N.M deliverable row in this shaping doc ties to a named verification surface. Strict existence, lenient form._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §3 Deliverable→surface table (C.1.1–C.P0R) | shaping-doc artifact | `agent_readability_lint.py check verification-contract plans/steward_platform/3_primitive_C/` | analyst | lint exits 0 |
| §4.1 KB structure spec | shaping-doc artifact | Packet C-Exec integration test: `diff <(find knowledge -maxdepth 2 -type f \| sort) <(expected-layout.txt)` | author | diff is empty for post-C-Exec-merge layout |
| §4.1.3 INDEX regeneration algorithm | new script spec | `tests/unit/test_kb_index.py::test_index_regenerates_deterministically` | author | pytest passes; byte-identical output on two consecutive runs |
| §4.2 Scorecard 10 items | shaping-doc artifact | `tests/unit/test_agent_readability_score.py::test_ten_items_present` | author | pytest asserts exactly 10 items enumerated by runner |
| §4.2 ≥7/10 floor lockdown | config constraint | `tests/unit/test_agent_readability_score.py::test_floor_below_seven_rejected` | author | runner rejects `--floor 6` with explicit ADR 001 citation |
| §4.3 Archivist C↔D interface contract | docs + integration | `grep -c 'Archivist C↔D Interface Contract' scripts/internal/archivist.py knowledge/INDEX.md` | analyst | both files contain the block (count ≥2) |
| §4.4 /create-plan refusal logic | `.claude/skills/**` upgrade | `tests/unit/test_create_plan_refusal.py` (4 tests, one per refusal condition) | author | all 4 tests pass |
| §4.5.1 Pattern 9 rule set (LBO1–LBO3 + HA1) | extension of existing script | `tests/unit/test_agent_readability_lint.py::TestPattern9` | author | positive + 3 negative fixtures pass |
| §4.5.2 Pattern 11 rule set (P11_1–P11_3) | extension of existing script | `tests/unit/test_agent_readability_lint.py::TestPattern11` | author | positive + 3 negative fixtures pass |
| §4.5.3 Shared plan-walker contract | shared-module discipline | `tests/unit/test_agent_readability_lint.py::TestPlanWalker` | author | walker tests pass independently of rule-set tests |
| §4.6 review-driver V7 precheck | extension of existing script | `tests/unit/test_review_driver.py::TestV7CommitPolicy` | author | V7 fires when `_promoted/` file lacks upstream `archivist_candidate_generated` event |
| §4.7 Commit policy (tracked/gitignored split) | config + rules extension | `git check-ignore knowledge/_candidates/` exits 0 AND `git check-ignore knowledge/_promoted/` exits 1 (non-ignored) | ops | both assertions hold |
| §4.7 Promotion transition + rollback | integration workflow | forward-then-reverse rollback test (§5.3 "Rollback test" block) | author | `kb_artifact_promoted` + `kb_artifact_unpromoted` events fire; NOTES.md byte-identical pre-promotion vs. post-reverse |
| §5.1 C.1.5 harness_assumptions ≥5 entries | KB-class artifact | `grep -c '^### ' knowledge/harness_assumptions.md` ≥ 5 AND `check load-bearing-ownership` + HA1 rule exit 0 | analyst | ≥5 entries; every brittleness signal machine-observable |
| §5.1 C.1.6 ADR 001 migration | file migration | `diff plans/steward_platform/adrs/001-platform-reset.md knowledge/adr/001-platform-pattern-reset.md` post-migration; seed location carries 3-line migration note | analyst | content identical; migration note present at seed |
| §5.1 C.10 MEMORY compaction script | new Python script | `tests/unit/test_memory_compact.py` + seeded fixture smoke | author | pytest passes; compaction preserves high-priority entries |
| §5.1 C.12 scorecard sub-plan placeholder | new sub-plan artifact | `agent_readability_lint.py check verification-contract plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` | analyst | lint exits 0 (sub-plan has own Verification Plan) |
| §5.1 C.P0R Phase 0 Readiness closeout | outcome artifact | every §5-C Readiness bullet has a grep-verifiable check in `phase0_readiness.md`; `grep -c '^- \[.\]' phase0_readiness.md` ≥ 9 (one per §5-C Readiness bullet) | orch+analyst | all checklist items verified; count matches §5-C |
| §5.2 Order of operations | execution discipline | post-Packet-C-Exec PR body cites the order (audit trail) | author | PR body lists steps 1-16 with per-step evidence |
| §5.3 Validation commands | Tier 2 validation | `make check-gated` passes as foreground command | author | gated run exits clean |
| §5.5 Packet decomposition | shaping-doc artifact | orchestrator dispatches C-Exec as single or 3-sub-packet sequence per §5.5 | orch | dispatched per decision; recorded in task-queue metadata |
| §5.6 Packet success criterion | shaping-doc artifact | §5.3 all pass + PR merged + scorecard ≥7/10 baseline recorded | orch | all conditions hold |
| §6.2 Completeness criteria stress-test | self-review | operator or flex-lane review per §6.5 (optional; not blocking) | orch (optional) | review complete if dispatched |

**Surface-class defaults** — see Pattern 10 table at §10.9 of `plans/steward_platform/governing_plan.md` for the full deliverable-class → default-surface mapping. Placeholder tokens (TBD/TODO/FIXME/XXX) in the Verification surface column would cause `/create-plan` refusal and `check verification-contract` lint failures; none present above.

---

## §9. References

- `plans/steward_platform/governing_plan.md` §5-C — primary target of Primitive C Phase 0 scope
- `plans/steward_platform/governing_plan.md` §10.9 Patterns 7/8/9/10/11 — binding patterns
- `plans/steward_platform/governing_plan.md` §13 SC #16, #17 — agent-readability scorecard + lint-clean success criteria
- `plans/steward_platform/governing_plan.md` §14 open items 6, 7, 11, 17 — KB INDEX tooling, Phoenix (for A↔C coordination), ADR 001 content, external signal sources seed
- `plans/steward_platform/adrs/001-platform-reset.md` — 7/10 floor; scorecard lifecycle; Platform-11/13 dismissal framing
- `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` — commit policy; archivist operator-gated
- `plans/steward_platform/verification_contract/shaping.md` — Pattern 10 exemplar; V1–V6 precheck taxonomy (§3.4); §13.2 shared-module risk codification
- `plans/steward_platform/verification_contract/map.md` — C.1–C.7 + C.Phase0Readiness rows (extended by Packet C-Exec to C.1.1–C.1.7)
- `plans/steward_platform/1_primitive_A/shaping.md` — event schema v1.0; `incident_fingerprint` source; shaping-doc format exemplar
- `.claude/rules/deferred/30_data_contract.md` — existing commit-policy home (extended by Packet C-Exec)
- `.claude/rules/deferred/60_review_gate.md` — V1–V6 precheck severity; V7 added by Packet C-Exec
- `.claude/skills/create-plan/SKILL.md` — current refusal-logic stub (upgraded by Packet C-Exec)
- `scripts/internal/agent_readability_lint.py` — Pattern 10 + Pattern 9 scaffold (extended by Packet C-Exec with concrete Pattern 9 + Pattern 11 rule sets)
- Task packet: `abff1f5d146a` (Primitive C shaping — this document)
