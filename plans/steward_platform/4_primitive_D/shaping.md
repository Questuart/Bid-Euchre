# Primitive D — Archivist, Session Postmortem, and Changelog Review — Phase 0 Shaping Document

**Primitive:** D (inflow Phase 0; outflow Phase 1; changelog Phase 0)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-D (lines 444-490)
**Pattern:** §10.9 Pattern 11 (shape-then-execute dispatch)
**Author:** analyst-a
**Task packet:** `1408c8e00f63`
**Delivery mode:** PR mode — durable shaping artifact committed under `plans/steward_platform/`

---

## §1. Scope of this document

### §1.1 What this document specifies

This shaping doc turns governing plan §5-D from narrative prose into an
executable packet spec. It enumerates every Primitive D Phase 0 deliverable
(§5), binds each to a Pattern-10 verification surface (§3), specifies the
libraries, scripts, skills, KB artifacts, cron registrations, and event
emissions in enough detail that an author lane can execute Packet D-Exec
without re-designing intent (§4), wires a single execution packet with scope
lock and validation (§5), and flags Phase 2 decision inputs (§7) and
cross-primitive coordination hazards (§6.4).

### §1.2 What this document does NOT do

- It does not implement D. Execution ships in Packet D-Exec (§5) dispatched
  to an author lane after this shape is reviewed.
- It does not specify Primitive A's event schema, Primitive C's KB layout,
  or Primitive B's recipe/improvement-metric schemas. D writes into those
  surfaces; the surfaces themselves are owned elsewhere (see §2).
- It does not cover Phase 1 GC activation except as Phase 0 code-path
  scaffolding. The Phase 1 workflow (operator-approved deletions, ≥3
  proposals-accepted criterion) runs during the proving run and is tracked
  against §11-D kill criterion, not built during Packet D-Exec.
- It does not author the decision-inputs digest compiler
  (`scripts/internal/compile_decision_inputs.py` referenced in §15.4) —
  that is a governing-plan-infrastructure deliverable independent of D.
  Changelog review writes ledger entries under the `native-substrate-signal`
  tag that the digest will consume; the digest itself is out of scope.

### §1.3 Motivation

The archivist is the only primitive whose *raison d'être* is compounding
curation. Without it, every session's lessons, incidents, and
token-efficiency outliers leak. Changelog review is its external-facing
twin: without it, the platform drifts as Claude Code ships native
capabilities the steward continues to synthesize, and
`harness_assumptions.md` rots silently.

Phase 0 ships both inflow sides (lessons + changelog). GC outflow is split
to Phase 1 because the KB does not exist meaningfully at Phase 0 kickoff —
there is nothing stale to detect. The outflow code path is smoke-tested at
Phase 0 against seeded fake KB fixtures; activation waits for ≥2 weeks of
real KB accumulation during the proving run.

## §2. Binding references

### §2.1 Governing plan §5-D (lines 444-490)

Authoritative scope. Deviations from §5-D require orchestrator sanction,
not analyst sanction.

- Line 444: primitive title, phase split
- Lines 446-449: native-substrate integration (archivist subscribes to
  lifecycle hook streams, not parses logs)
- Lines 451-455: draft-7 changelog review scope addition
- Lines 461-476: Work bullets (scripts, outputs, skills, seeds)
- Lines 478-483: Phase 0 Readiness (5 items)
- Lines 485-490: Phase 1 Validation (5 items; F8 kill criterion)

### §2.2 ADR 010 (mcp-memory-service evaluation)

Filed at `plans/steward_platform/adrs/010-mcp-memory-service.md`. D does
**not** adopt autonomous "dream-inspired" memory consolidation. Promotion
is operator-gated. Phase 3 soft re-evaluation trigger: KB exceeds 20KB or
500 entries, or archivist inflow exceeds operator-review capacity sustained
≥1 week. Until then, candidate-to-promoted transitions are git-tracked
operator actions, not autonomous writes.

### §2.3 ADR 001 (Platform Pattern Reset)

Floor: agent-readability scorecard ≥7/10 across KB. D's generated candidate
files must meet that floor — templates (§4.1.2) are authored to score ≥7
on first run.

### §2.4 §10.9 Patterns touched

| Pattern | Where D interacts |
|---|---|
| Pattern 7 (Reversibility) | Every candidate → promoted transition has a git-based rollback; stale-marking has a git-based rollback; §4.3 rollback catalog |
| Pattern 8 (Observable-by-default) | Every archivist run emits `archivist_candidate_proposed`; every promotion emits `archivist_candidate_promoted`; every rejection emits `archivist_candidate_rejected`; every GC proposal emits `archivist_gc_proposed` |
| Pattern 9 (Load-bearing-ownership) | Every file D creates is enumerated in §5.1 Scope Declared; §5.3 validation lints catch drift |
| Pattern 10 (Verification surface) | Every §3 row names a surface from `verification_contract/shaping.md` §2 |
| Pattern 11 (Shape-then-execute) | This document is the shape; Packet D-Exec (§5) is the execution |

### §2.5 claude_code_changelog_implications.md

Seed corpus for `/review-claude-changelog`. Tier S/A/B/C inventory of Claude
Code native features (Jan-Apr 2026) lives there; the review skill's first
run reads this as its "historical baseline" and diffs forward from the
date-of-authoring.

### §2.6 Primitive A shaping (event schema)

- `1_primitive_A/shaping.md` §180: archivist lifecycle row claims 4 event
  types belong to D's emission surface
- `1_primitive_A/shaping.md` §286-289: event-schema rows for
  `archivist_candidate_proposed`, `archivist_candidate_promoted`,
  `archivist_candidate_rejected`, `archivist_gc_proposed`

D emits under A's canonical names. Note the Primitive C naming-mismatch
flag in §6.4.3 — does not block D-Exec.

### §2.7 Primitive C shaping (KB layout)

- `3_primitive_C/shaping.md` §4.1: KB directory structure. D writes to
  `knowledge/_candidates/`; C defines the promoted layout D's promoted
  outputs land in. D's seed file `knowledge/external_signal_sources.md`
  lives in the top-level `knowledge/` tree C curates.
- `3_primitive_C/shaping.md` §4.6 V7 precheck: blocks promoted commits
  without upstream archivist events. D supplies those events; coordination
  flagged in §6.4.3.

### §2.8 Primitive B shaping

- `2_primitive_B/shaping.md` §1256: D proposes orchestration-recipe
  candidates into `knowledge/_candidates/recipes/` (follow-up; not Packet
  D-Exec scope).
- `2_primitive_B/shaping.md` §1074: D may produce
  `knowledge/_candidates/<date>_improvement_metrics.md` for B.12 probes
  (deferred; operator-configurable follow-up).

### §2.9 verification_contract/

- `verification_contract/map.md` lines 57-65: D deliverable rows D.1-D.4 +
  D.Phase0Readiness. This shaping preserves the map's surface choices.
- `verification_contract/shaping.md` §2 deliverable-class → surface-class
  default table; §4.3 analyst prompt-policy (every deliverable names a
  surface; final §Verification Plan required).

## §3. Deliverable → Pattern-10 surface table

Every row binds a sub-deliverable to a §10.9 Pattern-10 surface drawn from
the default table in `verification_contract/shaping.md` §2. "Strict
existence, lenient form" — no row is `TBD`.

| Row | Deliverable | Surface class | Verification surface | Acceptance | Owner | §4 spec |
|---|---|---|---|---|---|---|
| D.1 | Archivist library (lessons mode) | new module under `src/bid_euchre/ops/**` | `tests/unit/test_archivist.py` | pytest passes; ≥3 candidate-class cases from seeded fake events | author | §4.1 |
| D.1a | Archivist CLI wrapper | new module under `scripts/internal/**` | `tests/unit/test_archivist_cli.py` + `--help` exit-0 smoke | pytest passes; `--help` exits 0; `--dry-run` produces expected file path | author | §4.1.4 |
| D.1b | GC mode code-path scaffolding (Phase 0) | extension of D.1 library | `tests/unit/test_archivist.py::TestGCMode` (seeded fake KB fixture) | pytest passes; 5 gc_class values covered by test cases | author | §4.2 |
| D.1c | GC mode activation (Phase 1 outcome) | integration workflow | SC #15 — ≥3 proposals accepted across ≥2 categories during proving run | ratio logged in proving-run report | ops | §4.2.3 (design intent) |
| D.2 | Session postmortem library | new module under `src/bid_euchre/ops/**` | `tests/unit/test_session_postmortem.py` | pytest passes; postmortem-to-MEMORY.md shape match against fixture | author | §4.4 |
| D.2a | Session-end skill integration | modification to `.claude/skills/session-end/SKILL.md` | SKILL.md Phase-4.5 subsection + operator-review prompt: "handoff written + candidates queued" | skill text includes Phase 4.5; acceptance prompt resolves | analyst | §4.4.2 |
| D.3 | Changelog review library | new module under `src/bid_euchre/ops/**` | `tests/unit/test_changelog_review.py` (WebFetch mocked; offline HTML fixture) | pytest passes; schema validator accepts output | author | §4.5 |
| D.3a | Changelog review CLI wrapper | new module under `scripts/internal/**` | `tests/unit/test_changelog_review_cli.py` + `--help` exit-0 smoke | pytest passes; `--dry-run` produces expected file path | author | §4.5.3 |
| D.4 | `/run-archivist` skill | new `.claude/skills/**` entry | `SKILL.md` acceptance command ("output file exists; events emitted") + skill-manifest schema (V3 precheck) | V3 lint clean; skill invokable | analyst | §4.6.1 |
| D.4a | `/review-claude-changelog` skill | new `.claude/skills/**` entry | `SKILL.md` acceptance command + SC #19 (≥2×/week run cadence; ≥1 `native-substrate-signal` ledger entry in proving run) | V3 lint clean; cron-registered; run log satisfies SC #19 | ops | §4.6.2 |
| D.5 | `knowledge/external_signal_sources.md` seed | new KB-class artifact | `agent_readability_lint.py` clean + `INDEX.md` inclusion (deferred to C) + operator-review prompt ("seed has ≥5 URLs with category + last-scraped-date") | lint exits 0; operator-review prompt resolves | analyst | §4.8 |
| D.6 | Candidate-to-promotion rate ≥10% (Phase 0 Readiness) | outcome metric | proving-run KB promotion log (§11-D kill criterion) | ratio logged ≥10% during Phase 0 close | analyst | §4.7 (design intent) |

**Coverage:** 12 rows; every row has a concrete surface. Pattern-10 lint
(`agent_readability_lint.py check verification-contract`) runs clean.

## §4. Per-deliverable specs

### §4.1 Archivist library — lessons mode (D.1, D.1a)

#### §4.1.1 Module layout

```
src/bid_euchre/ops/archivist/
  __init__.py            # exports: run_lessons(), run_gc(), emit_candidate_event()
  lessons.py             # lessons-mode collector + templater
  gc.py                  # gc-mode collector + templater (Phase 0 scaffold; §4.2)
  templates.py           # shared markdown template blocks
  events.py              # thin wrapper over Primitive A event-writer
scripts/internal/archivist.py   # CLI wrapper; argparse + dispatch to library
```

Library-in-src, CLI-in-scripts split is the standard CLAUDE.md convention.

#### §4.1.2 Input sources (lessons mode)

| Source | Mechanism | Phase |
|---|---|---|
| Events (Primitive A JSONL) | Path via `ops.py config get events.path`; stream-read last N hours | Phase 0 — **gated on `ENABLE_D_EVENT_READ` until A lands** |
| Inbox messages | `scripts/internal/ops.py inbox --include-native --status acked --since <ts>` | Phase 0 |
| PR outcomes | `gh pr list --state merged --search "merged:>=<ts>" --json number,title,mergedAt,body` | Phase 0 |
| Task packet completions | `scripts/internal/ops.py task list --status completed --since <ts>` | Phase 0 |
| Session transcripts | Native lifecycle hook output stream if available; otherwise skipped with warning | Phase 0 — **graceful degradation** |

**Time-window convention:** lessons-mode scan windows default to "since
last archivist run" tracked in `knowledge/_candidates/.last_run_lessons`
(single-line ISO-8601 timestamp). First run looks back 24h.

#### §4.1.3 Output file schema

Path: `knowledge/_candidates/<YYYY-MM-DD>_lessons.md` (one per UTC date;
re-runs on same date append, do not overwrite).

```markdown
# Archivist Candidate — Lessons — <date>

**Run timestamp:** <ISO-8601>
**Source window:** <start> → <end>
**Source event count:** N
**Candidate count:** M

## Section 1 — Repeated patterns
<grouped by recurring trace signature; each group has pattern_id,
occurrence_count, example_trace_ids[], proposed_lesson>

## Section 2 — Token-efficiency outliers
<from token economy ledger; each row has lane, packet_id, token_delta,
proposed_lesson>

## Section 3 — Incident candidates
<failures / escalations / rollbacks; each has incident_id, trace_id,
proposed_lesson>

## Section 4 — Lesson candidates (explicit)
<operator annotations tagged "lesson-learned"; verbatim quote + trace_id>

## Verification: operator review
Each candidate has: proposed_lesson (≤3 sentences), evidence
(trace_id / PR URL / event_id), proposed_promotion_path (e.g.,
`knowledge/_promoted/lessons/<slug>.md`).
```

Agent-readability floor (§2.3): every section's heading + first ≤3
sentences pass the scorecard. Templates live in `templates.py` so the
authored file is deterministic and lint-checkable.

#### §4.1.4 CLI interface

```bash
uv run python scripts/internal/archivist.py --mode lessons [--since <ts>] [--dry-run] [--fixture <path>]
```

- `--mode lessons|gc` (required; dispatches to `lessons.py` or `gc.py`)
- `--since <ts>` (optional; overrides `.last_run_lessons` watermark)
- `--dry-run` (prints target path + candidate count; does not write)
- `--fixture <path>` (test-only; reads events from fixture instead of live ops)

Exit codes: 0 success; 1 empty scan (no candidates — not an error);
2 source unreachable; 3 write failure.

#### §4.1.5 Event emission (Pattern 8)

Every candidate section item emits `archivist_candidate_proposed` with:
- `candidate_path`: full path to the dated file
- `candidate_class`: `"lessons"`
- `source_event_ids`: list of trace/event IDs that triggered the candidate

Emission flag: `ENABLE_D_EVENT_EMISSION` env var, default `"0"`. Flag
flip is a 1-line follow-up PR after Primitive A Phase 0 lands (same
coordination pattern as Primitive C §6.3).

#### §4.1.6 Test surface (D.1 + D.1a)

`tests/unit/test_archivist.py`:
- `TestLessonsMode::test_templating_against_fake_events` — reads
  `tests/fixtures/archivist/fake_events.jsonl` (≥20 events covering all 4
  section-types); asserts output file shape, candidate counts, section
  headers
- `TestLessonsMode::test_empty_scan_exit_1` — no events → exit 1, no file
- `TestLessonsMode::test_since_watermark_advancement` — watermark file
  advanced after successful run
- `TestEventEmission::test_candidate_event_shape_when_flag_on` — mocks
  event writer; asserts payload matches Primitive A §4.4.1 row
- `TestEventEmission::test_no_emission_when_flag_off` — default state

`tests/unit/test_archivist_cli.py`:
- `test_help_exits_zero`
- `test_dry_run_prints_path_no_write`
- `test_missing_mode_exits_nonzero`
- `test_fixture_flag_reads_fixture`

### §4.2 Archivist library — GC mode (D.1b, D.1c)

#### §4.2.1 Phase 0 vs Phase 1 split

Phase 0 ships the **code path** — `gc.py` module, templates, CLI
`--mode gc` dispatch, seeded fake-KB fixture tests. No operator-facing
activation. The fake KB fixture (under `tests/fixtures/archivist/fake_kb/`)
constructs a synthetic `knowledge/` tree containing stale entries, dead
skills, obsolete policy versions, and orphan artifacts — one per
`gc_class` value so the code path is covered without requiring a real
2-week accumulation.

Phase 1 activation (outcome D.1c) is the proving-run workflow. SC #15
requires ≥3 accepted proposals across ≥2 categories. That criterion is a
proving-run observable, not a code deliverable. No Phase 0 work is blocked
on it; it tracks forward and is logged at Phase 0 close.

#### §4.2.2 Input sources (gc mode)

| Source | Mechanism |
|---|---|
| KB filesystem | `find knowledge/ -type f -name '*.md'` |
| Citation graph | `grep -rl <filename>` across PR bodies, task-packet descriptions, trace events |
| Skill invocation telemetry | Primitive A events with `event_type="skill_invoked"`; skills not matched since promotion → dead |
| Prompt-policy registry | B.3 registry index; versions marked `superseded=true` → obsolete |

#### §4.2.3 Output file schema

Path: `knowledge/_candidates/<YYYY-MM-DD>_gc.md`.

```markdown
# Archivist Candidate — GC — <date>

## Section 1 — Stale entries
<path, last-referenced date, N sessions since, proposed_action ("mark stale" | "delete")>

## Section 2 — Dead skills
<skill path, last-invoked date or "never since promotion", proposed_action>

## Section 3 — Obsolete prompt-policies
<policy path, superseding version, proposed_action>

## Section 4 — Orphan artifacts
<orphan path, missing referenced target, proposed_action>

## Section 5 — Expired evidence
<KB entry path, expired evidence link, proposed_action>

## Verification: operator review
Each proposal has: target_paths[], proposed_action, evidence, rollback path.
```

#### §4.2.4 Event emission

Every gc-section item emits `archivist_gc_proposed` with:
- `candidate_path`: the dated candidate file
- `gc_class`: one of `stale | dead-skill | obsolete-policy | orphan | expired`
- `target_paths`: list of KB paths proposed for action

#### §4.2.5 Test surface

`tests/unit/test_archivist.py::TestGCMode`:
- `test_stale_detection_fake_kb` — seeded fake KB has entry not referenced
  in simulated grep output; proposal emitted
- `test_dead_skill_detection_fake_events` — skill has no invocation events
  in fixture window; proposal emitted
- `test_obsolete_policy_detection_fake_registry` — superseded policy flagged
- `test_orphan_detection_missing_target` — orphan proposal emitted
- `test_expired_evidence_detection` — KB entry with expired-evidence
  annotation flagged
- `test_gc_class_coverage` — every `gc_class` value appears in test output

### §4.3 Promotion + rejection flow (operator action)

Not a code deliverable — a documented operator workflow. The
`/run-archivist` skill (§4.6.1) prints the workflow inline; the skill
file carries the canonical text.

**Workflow:**

1. Operator or analyst opens `knowledge/_candidates/<date>_<class>.md`
2. For each candidate: decide `promote` | `reject` | `skip`
3. **Promote** (Pattern 7 reversible):
   - Create target file at proposed_promotion_path
   - Move/copy content from candidate into promoted file
   - Annotate candidate entry with "PROMOTED → <path>"
   - Emit `archivist_candidate_promoted` (flag-gated) with
     `candidate_path`, `promoted_path`, `operator`
   - Commit as `docs(knowledge): promote <slug>`
   - Rollback = `git revert` or move content back into `_candidates/`
4. **Reject** (Pattern 7 reversible):
   - Annotate candidate with "REJECTED: <reason>"
   - Emit `archivist_candidate_rejected` with `candidate_path`,
     `rejection_reason`, `operator`
   - Commit as `docs(knowledge): reject archivist candidate — <reason>`
   - Rollback = `git revert`
5. **Skip** (no event, no commit; re-evaluated next cycle)

**Invariant:** no archivist-generated file reaches `knowledge/_promoted/`
except via this workflow. Primitive C V7 precheck enforces the invariant
at commit time (blocks promoted commits without upstream events).

### §4.4 Session postmortem (D.2, D.2a)

#### §4.4.1 Module layout

`src/bid_euchre/ops/session_postmortem.py` — single module; no subpackage
needed.

Functions:
- `collect_session_signals(session_id: str) -> SessionSignals` — reads
  events, PR activity, task completions in the session window
- `render_memory_entry(signals: SessionSignals) -> str` — produces the
  markdown block for MEMORY.md (per existing Phase-4 template in
  `.claude/skills/session-end/SKILL.md`)
- `render_candidate_entry(signals: SessionSignals) -> str` — produces a
  `knowledge/_candidates/<date>_lessons.md` section containing
  postmortem-derived lesson signals
- `run_postmortem(session_id: str, memory_md_path: Path, candidates_dir: Path) -> None`
  — orchestrates: collect + render + append to MEMORY.md + append-or-create
  candidate file + emit `archivist_candidate_proposed`

#### §4.4.2 Session-end skill integration

Modify `.claude/skills/session-end/SKILL.md` Phase 4 (Write Session
Handoff to MEMORY.md) by inserting Phase 4.5 between Phase 4 and Phase 5:

> **### Phase 4.5 — Feed Archivist Candidate Queue**
>
> Immediately after the MEMORY.md handoff commit is authored (but before
> pushing), invoke:
>
> ```
> uv run python scripts/internal/archivist.py --mode postmortem --session-id <id>
> ```
>
> This appends a postmortem-derived section to
> `knowledge/_candidates/<date>_lessons.md` covering this session's
> incidents, token outliers, and explicit lessons. The appended section
> ships in the same MEMORY.md commit so handoff + candidate arrive
> together.
>
> If the archivist invocation fails, **do not** block shutdown — log the
> failure to the pane transcript and proceed to Phase 5. Failed
> postmortems are caught by the next nightly archivist run.

The skill modification is small (a 10-15 line insertion + reference update).
No breakage of the existing Phase 4 flow.

#### §4.4.3 PreCompact hook (optional; **out of Packet D-Exec scope**)

Noted as follow-up: a `.claude/hooks/pre-compact-archivist.sh` hook could
invoke `scripts/internal/archivist.py --mode postmortem` before context
compaction fires. Defer to Packet D-Exec-2 or a subsequent follow-up; not
blocking Phase 0 Readiness.

#### §4.4.4 Test surface

`tests/unit/test_session_postmortem.py`:
- `test_render_memory_entry_against_template_fixture` — asserts output
  matches the existing session-end Phase-4 template shape
- `test_render_candidate_entry_section_shape` — asserts section fits the
  lessons-file schema (§4.1.3)
- `test_run_postmortem_writes_both_outputs` — mocks filesystem; asserts
  MEMORY.md appended AND candidate file written
- `test_run_postmortem_graceful_on_missing_session_id` — graceful fail,
  exit-1, no partial writes

### §4.5 Changelog review (D.3, D.3a)

#### §4.5.1 Module layout

```
src/bid_euchre/ops/changelog_review/
  __init__.py            # exports: run_review(), scrape_source()
  scraper.py             # source-list walker + WebFetch invocations
  schema.py              # candidate-entry schema + validator
scripts/internal/changelog_review.py   # CLI wrapper
```

#### §4.5.2 Source list (ordered; short-circuit on cache-hit)

1. `https://code.claude.com/docs/en/changelog` — official rolling changelog
2. `https://code.claude.com/docs/en/whats-new` — weekly rollup landing
3. Per-week discoverable pages (`whats-new/2026-wNN`) — walked back from
   current ISO week until 404
4. `https://github.com/anthropics/claude-code/releases` — tagged release
   notes; complements the docs pages
5. `https://docs.anthropic.com` blog — ecosystem-context (model cards,
   long-context announcements affecting harness assumptions)
6. Plugin registry indexes (per §10.9 Pattern 2 native-substrate-first
   preference order)
7. Operator-curated URLs from `knowledge/external_signal_sources.md` (§4.8)

Per-source scraping: WebFetch with a deterministic prompt ("extract
features, dates, and relevant tier signals per the schema at
plans/steward_platform/claude_code_changelog_implications.md §5"). Results
cached in-run to avoid double-fetch when sources cross-reference each
other.

#### §4.5.3 CLI interface

```bash
uv run python scripts/internal/changelog_review.py [--since <ISO-date>] [--sources-file <path>] [--dry-run] [--fixture-dir <path>]
```

- `--since <ISO-date>` — look back from this date; default "last run
  timestamp" in `knowledge/_candidates/.last_run_changelog`
- `--sources-file <path>` — override default `knowledge/external_signal_sources.md`
- `--dry-run` — prints scraped source count + candidate count; no write
- `--fixture-dir <path>` — test-only; reads HTML from fixture directory
  instead of WebFetch

Exit codes: 0 success with candidates; 1 empty scan; 2 all sources
unreachable (WebFetch failures); 3 write failure.

#### §4.5.4 Output file schema

Path: `knowledge/_candidates/<YYYY-MM-DD>_changelog.md`.

```markdown
# Changelog Review Candidate — <date>

**Run timestamp:** <ISO-8601>
**Sources scraped:** <count>/<total>
**Source results:** <list with each URL + "OK|404|timeout">
**Candidate count:** N

## Candidate 1 — <feature name>
- **Source URL:** <canonical link>
- **Affected primitive(s):** <A | B | C | D | E | F | G | H>
- **Stales harness assumption:** <no | yes — entry_id: <id>>
- **Tier recommendation:** <S | A | B | C> (per claude_code_changelog_implications.md rubric)
- **Native-substrate-signal:** <no | yes>   <!-- §15.3 tag -->
- **Operator decision:** <accept | defer | reject>   <!-- filled post-review -->
- **Decision date:** <ISO-date>   <!-- filled post-review -->
- **Follow-up:** <PR link | issue link | n/a>

## Candidate 2 ...

## Verification: operator review
Each candidate has: feature name, source URL, affected primitive,
staleness annotation, tier, decision fields.
```

#### §4.5.5 Native-substrate-signal integration (§15.3)

When a candidate meets either condition, the candidate entry carries
`Native-substrate-signal: yes`:
1. **Stales harness assumption:** candidate corresponds to a native
   capability the steward currently synthesizes via custom code
2. **Explicit native-first preference:** candidate is a new Claude Code
   primitive in the Tier S/A range per §2.5 rubric

These entries are additionally tagged for consumption by
`compile_decision_inputs.py` (§15.4 — upstream infrastructure, not a D
deliverable). The tag is a literal line `Native-substrate-signal: yes`
inside the candidate entry; the digest compiler greps for it.

#### §4.5.6 Test surface

`tests/unit/test_changelog_review.py`:
- `test_scrape_against_fixture_html` — `--fixture-dir` populated with 3
  canned HTML files matching source-list positions 1-3; assert parser
  extracts ≥3 features with required schema fields
- `test_harness_assumption_staleness_detection` — fake
  `knowledge/harness_assumptions.md` contains entry "X"; fixture HTML
  announces native "X" equivalent; candidate marks staleness
- `test_native_substrate_signal_tag_when_stales` — staleness → signal tag
  `yes`
- `test_tier_recommendation_populated` — per rubric
- `test_source_failure_graceful_degradation` — 1 source 404s, 1 times out,
  1 succeeds → exit 0 with partial output + documented source_results
- `test_all_sources_unreachable_exit_2` — all sources fail → exit 2

`tests/unit/test_changelog_review_cli.py`: same shape as §4.1.6 — `--help`,
`--dry-run`, fixture flag.

### §4.6 Skills (D.4, D.4a)

#### §4.6.1 `/run-archivist` skill

File: `.claude/skills/run-archivist/SKILL.md`

Required structure (matches existing skill conventions):
- YAML frontmatter with `name: run-archivist` and description
- `## When to Use` — nightly cron, end-of-session hook, ad-hoc operator curation
- `## Arguments` — `--mode lessons|gc|postmortem` (default lessons)
- `## Workflow` — 4 steps: invoke CLI → review output file → promote/reject
  candidates → commit decisions
- `## Promotion Workflow` — full §4.3 inline (canonical location)
- `## Gotchas` — `ENABLE_D_EVENT_EMISSION` flag state; re-run-same-day behavior
- `## References` — this shaping doc + §5-D governing plan

Acceptance command (review-driver V3 skill-manifest precheck):
`uv run python scripts/internal/archivist.py --mode lessons --dry-run`
exits 0 and prints expected target path.

#### §4.6.2 `/review-claude-changelog` skill

File: `.claude/skills/review-claude-changelog/SKILL.md`

Required structure:
- YAML frontmatter with `name: review-claude-changelog` and description
- `## When to Use` — `/loop 3d` cron + ad-hoc when Claude Code ships
  material update
- `## Arguments` — `--since <ISO-date>`, `--sources-file <path>`, `--dry-run`
- `## Workflow` — invoke CLI → review candidates → fill decision fields →
  commit
- `## Harness Assumption Integration` — describes how stale-flagging works
  and points to `knowledge/harness_assumptions.md` workflow
- `## Native-Substrate-Signal Tag` — references §15.3
- `## Gotchas` — WebFetch quota; source reachability variance
- `## References`

Acceptance command: `uv run python scripts/internal/changelog_review.py
--dry-run` exits 0 and prints expected target path.

SC #19 acceptance (measured at Phase 0 close): ≥2 runs per week during
the proving-run observation window; ≥1 candidate file contains at least
one `Native-substrate-signal: yes` entry. Tracked by ops via run-log.

### §4.7 Cron scheduling + re-arm-on-restart hazard

Cron registrations (operator actions, not file deliverables):

| Cron | Lane | Cadence | Command | Durability |
|---|---|---|---|---|
| Nightly lessons archivist | ops | 24h | `/loop 24h /run-archivist --mode lessons` | session-scoped |
| Changelog review | ops | 72h | `/loop 3d /review-claude-changelog` | session-scoped |
| End-of-session postmortem | any lane | on session-end | `.claude/skills/session-end/SKILL.md` Phase 4.5 | event-triggered |

**Re-arm-on-restart hazard:** `CronCreate` (which backs `/loop`) is
session-scoped. Fleet restarts (rate-limit, operator-ordered, or orchestrator
respawn) lose all crons. The existing convention (per MEMORY.md operator
notes): after restart, the orchestrator re-arms durable crons as part of
the post-restart recovery sequence. Not a Primitive D deliverable per se,
but **coordination note** for the orchestrator: adding two new crons
extends the re-arm list (§6.4.2).

Phase 0 Readiness line "Archivist inflow runs nightly" (§5-D line 479) is
met by the cron + re-arm convention, not by D owning durable scheduling.
If durable cron scheduling becomes a platform need, it is a new primitive
or a governing-plan-infrastructure deliverable — flagged as Phase 2
decision input (§7 prompt #2).

### §4.8 `knowledge/external_signal_sources.md` seed (D.5)

#### §4.8.1 Schema

```markdown
# External Signal Sources

Operator-curated sources scraped by `/review-claude-changelog` in addition
to the official Claude Code changelog.

## Sources

### <category tag>

- **URL:** <canonical link>
- **Type:** <rss | atom | html | twitter-list | other>
- **Last scraped:** <ISO-date | "never">
- **Rationale:** <one sentence why this source produces steward-relevant signal>

### ...
```

#### §4.8.2 Seed content (minimum per governing plan §1245)

Categories + seed URLs (to be confirmed with operator at dispatch time;
authoritative list is whatever the operator commits in D-Exec):

| Category | Seed entries |
|---|---|
| `anthropic-official` | Claude Code release page, Anthropic blog (model cards), docs.anthropic.com |
| `operator-community` | Boris Cherny Opus 4.7 thread (TBD URL); davidad `--system-prompt-file` thread (TBD URL); operator's curated X/Twitter list URL (G8-scalable aggregate, not per-thread) |
| `plugin-registry` | `github.com/anthropics/claude-code-plugins` (if exists at D-Exec time); other registry indexes |
| `workflow-commentary` | Operator-selected digests |

**Minimum seed count:** 5 entries across ≥3 categories (operator-review
surface acceptance criterion per D.5 row).

#### §4.8.3 Integration with `harness_assumptions.md`

`changelog_review.py` reads `knowledge/harness_assumptions.md` (a
Primitive C deliverable) on every run and compares each scraped feature
against every harness-assumption entry. A match ("native X now ships; we
synthesize X") flags the assumption as stale and annotates the candidate
file. The operator then decides whether to: (a) retire the assumption
+ adopt native, (b) refresh the assumption with a new "still synthesizes
because..." justification, (c) defer.

**Coordination with C:** `knowledge/harness_assumptions.md` is owned by
C.2 (`verification_contract/map.md` row). D reads; C writes the register
itself. If C has not landed at D-Exec dispatch time, D's staleness check
degrades gracefully (no register → skip staleness annotation; all
candidates get `Stales harness assumption: no`). Unit test covers this
degradation path.

## §5. Packet D-Exec execution spec

### §5.1 Scope declared (strict Pattern 9 enumeration)

**CREATE** (new files — orderless within the list):

```
src/bid_euchre/ops/archivist/__init__.py
src/bid_euchre/ops/archivist/lessons.py
src/bid_euchre/ops/archivist/gc.py
src/bid_euchre/ops/archivist/templates.py
src/bid_euchre/ops/archivist/events.py
src/bid_euchre/ops/session_postmortem.py
src/bid_euchre/ops/changelog_review/__init__.py
src/bid_euchre/ops/changelog_review/scraper.py
src/bid_euchre/ops/changelog_review/schema.py
scripts/internal/archivist.py
scripts/internal/changelog_review.py
.claude/skills/run-archivist/SKILL.md
.claude/skills/review-claude-changelog/SKILL.md
knowledge/external_signal_sources.md
knowledge/_candidates/.gitkeep
tests/unit/test_archivist.py
tests/unit/test_archivist_cli.py
tests/unit/test_session_postmortem.py
tests/unit/test_changelog_review.py
tests/unit/test_changelog_review_cli.py
tests/fixtures/archivist/fake_events.jsonl
tests/fixtures/archivist/fake_kb/         # directory + several .md fixtures
tests/fixtures/changelog_review/fake_official.html
tests/fixtures/changelog_review/fake_whats_new.html
tests/fixtures/changelog_review/fake_github_release.html
```

**MODIFY** (surgical; diff-minimal):

```
.claude/skills/session-end/SKILL.md
    — insert Phase 4.5 subsection between existing Phase 4 and Phase 5
      (15-line addition; no change to existing Phase 4 or Phase 5 text)
knowledge/INDEX.md
    — add entry for external_signal_sources.md IF Primitive C INDEX
      generator has shipped; otherwise defer (§6.4.4)
```

**NOT IN SCOPE** (explicit Pattern 9 anti-scope):

```
src/bid_euchre/ops/archivist/pre_compact.py  # §4.4.3 deferred
.claude/hooks/pre-compact-archivist.sh       # §4.4.3 deferred
scripts/internal/compile_decision_inputs.py  # governing-plan-infra, not D
Primitive A event-writer shared helper        # A owns; D uses
knowledge/harness_assumptions.md              # C owns; D reads only
knowledge/_promoted/** layout                 # C owns
Primitive C V7 precheck rename                # C shaping correction, §6.4.3
Primitive B.11 recipe candidate schema        # B owns
Primitive B.12 improvement-metrics schema     # B owns
Durable (non-session) cron scheduling         # Phase 2 decision input §7
```

### §5.2 Order of operations

Within Packet D-Exec, the author lane should progress:

1. **Library skeleton + templates** — `src/bid_euchre/ops/archivist/*`
   modules (empty function stubs) + `templates.py` with markdown blocks
2. **Lessons-mode logic + unit tests** — implement `lessons.py` + CLI
   dispatch; write `test_archivist.py::TestLessonsMode` cases against
   `fake_events.jsonl` fixture
3. **GC-mode scaffolding + unit tests** — implement `gc.py` + seeded
   fake-KB fixture; `TestGCMode` cases
4. **Archivist CLI wrapper** — `scripts/internal/archivist.py` + `test_archivist_cli.py`
5. **Session postmortem library + test** — `session_postmortem.py` + `test_session_postmortem.py`
6. **Session-end skill modification** — 15-line Phase 4.5 insertion
7. **Changelog review library + scraper + schema** — `changelog_review/*`
8. **Changelog review CLI + test** — `scripts/internal/changelog_review.py`
   + `test_changelog_review.py` + `test_changelog_review_cli.py` with
   fixture HTML files
9. **Skill files** — `/run-archivist` + `/review-claude-changelog` `SKILL.md`
10. **Seed file** — `knowledge/external_signal_sources.md` with ≥5 entries
    across ≥3 categories
11. **`knowledge/_candidates/.gitkeep`** — placeholder to commit empty dir
12. **INDEX.md update (conditional)** — if C has shipped; else defer
13. **Rebase** — `git fetch origin main && git rebase origin/main`
14. **Tier 2 validation** — `make check-gated` in foreground
15. **Commit + PR**

Each step's validation is the unit tests it authors; moving to the next
step requires the preceding step's tests green.

### §5.3 Validation commands (Tier 2)

Before `gh pr create`:

```bash
# Rebase
git fetch origin main && git rebase origin/main

# Targeted unit tests (Tier 1 check during iteration)
uv run python -m pytest tests/unit/test_archivist.py \
                       tests/unit/test_archivist_cli.py \
                       tests/unit/test_session_postmortem.py \
                       tests/unit/test_changelog_review.py \
                       tests/unit/test_changelog_review_cli.py -v

# CLI smoke
uv run python scripts/internal/archivist.py --help
uv run python scripts/internal/archivist.py --mode lessons --dry-run --fixture tests/fixtures/archivist/fake_events.jsonl
uv run python scripts/internal/changelog_review.py --help
uv run python scripts/internal/changelog_review.py --dry-run --fixture-dir tests/fixtures/changelog_review/

# Review-driver V3 skill-manifest precheck on 2 new skills
uv run python scripts/internal/review_driver.py --check-skills-only \
  .claude/skills/run-archivist/ \
  .claude/skills/review-claude-changelog/

# Pattern-10 verification-contract lint (should still pass; map.md unchanged
# but now-visible rows must resolve)
uv run python scripts/internal/agent_readability_lint.py check verification-contract

# Full Tier 2
make check-gated
```

All must exit 0.

### §5.4 Coordination notes (for orchestrator at dispatch)

Listed in §6.4. Packet D-Exec proceeds independently of A/B/C landing
because:
- Event emission is flag-gated (default off)
- Harness-assumption read is graceful-degrading (missing file → skip)
- INDEX.md update is conditional-defer
- V7 precheck naming-fix is a C shaping correction, not a D blocker

### §5.5 Decomposition guidance (if single PR exceeds comfortable review size)

Author lane may split into up to 4 PRs at author-lane discretion (scope-lock
per sub-packet):

| Sub-packet | Deliverables | Est. file count |
|---|---|---|
| D-Exec-1 | Archivist library + CLI + both test files + fixtures | ~10 files created, ~4 modified-internal |
| D-Exec-2 | Session postmortem + test + skill modification | ~3 files created, ~1 modified |
| D-Exec-3 | Changelog review library + CLI + fixtures + tests + external_signal_sources seed | ~10 files created |
| D-Exec-4 | `/run-archivist` + `/review-claude-changelog` skills + INDEX update | ~2-3 files created/modified |

Single-PR shipping is preferred if review bandwidth permits (one-concept-per-PR
rule is met — "Primitive D Phase 0 bringup" is the concept). Default to
single PR; decompose only if review feedback demands.

### §5.6 Packet D-Exec success criterion

**All of:**

1. Every §5.1 CREATE file exists on merge
2. Every §5.1 MODIFY surgical-diff landed
3. Every §5.3 validation command exits 0
4. Review-driver V3 precheck clean on both new skills
5. Review-driver V1 (unit-test surface) cites each new test path
6. PR body includes `## Verification Performed` section with paste of
   all §5.3 output
7. Orchestrator confirms A-emission flag state verified `off` at merge
   time (guard against premature emission without A's event-writer)
8. CHANGELOG.md or equivalent session note records D Phase 0 inflow +
   changelog skill as shipped; governing-plan checkpoints updated

## §6. Self-review against "spawn reviewer agent" step

### §6.1 Constraint encountered

Analyst lanes run single-agent — no sub-agent reviewer spawn. Self-review
substitutes per analyst-lane protocol. This section stress-tests the
shape against the completeness-criteria recurring gap list (governing
plan §10.9 anti-pattern list: load-bearing-but-floating, surface-TBD,
scope creep, coordination skip).

### §6.2 Completeness stress-test

| Check | Status | Evidence |
|---|---|---|
| Every §5-D Readiness bullet maps to at least one deliverable row | ✅ | Readiness-1 (nightly) → D.1 + §4.7; Readiness-2 (GC code path smoke) → D.1b; Readiness-3 (candidate formats committed) → §4.1.3 + §4.2.3 templates; Readiness-4 (`/run-archivist` skill) → D.4; Readiness-5 (rollback path validated) → §4.3 + Pattern 7 catalog rows |
| Every deliverable row names a Pattern-10 surface | ✅ | §3 table, 12 rows, zero TBD |
| Every file D creates is enumerated in §5.1 CREATE | ✅ | 23 CREATE entries |
| Every file D modifies is enumerated in §5.1 MODIFY with diff shape | ✅ | 2 MODIFY entries (session-end skill + conditional INDEX) |
| Pattern 8 emissions enumerated with flag-gating | ✅ | §4.1.5, §4.2.4, §4.3 — 4 event types with flag-gating pattern |
| Pattern 7 rollback paths enumerated | ✅ | §4.3 (promotion/rejection); §5.1 (every new file is git-reversible); §4.7 (crons are operator-enumerable by `CronList`) |
| Pattern 9 load-bearing ownership | ✅ | §5.1 Scope Declared is the Pattern-9 enumeration; no file referenced in §4 is missing from §5.1 |
| Pattern 11 shape-then-execute | ✅ | This doc is the shape; Packet D-Exec spec is §5; no in-line execution |
| Cross-primitive coordination enumerated | ✅ | §6.4.1 (A), §6.4.2 (ops crons), §6.4.3 (C V7 rename), §6.4.4 (C INDEX) |
| Phase 2 Decision Inputs present | ✅ | §7 with 5 prompts |
| §Verification Plan present | ✅ | §8 enumerating every §N.M row |
| Governing plan §5-D quoted verbatim on native-substrate motivation | ✅ | §2.1 references lines 446-449 |
| ADR 010 (mcp-memory-service) constraint honored | ✅ | §2.2 + no autonomous promotion path in §4.3 |
| ADR 001 agent-readability floor ≥7/10 | ✅ | §4.1.3 template section header discipline |
| Kill criterion (F8) mapped | ✅ | §4.2.3 + D.1c row in §3 |

### §6.3 Risks surfaced (orchestrator decision)

**Risk 1 — Primitive A event-emission flag default drift.** If
`ENABLE_D_EVENT_EMISSION` gets flipped to `1` before A's event-writer
helper lands, archivist runs fail on write attempts.
- *Mitigation:* flag default `0`; flag-flip PR sits in author-b queue post
  A landing; acceptance criterion §5.6 item 7 catches premature flip.
- *Residual:* low — default-off + explicit merge-time check.

**Risk 2 — WebFetch rate limits on changelog scraping.** Cadence `/loop 3d`
+ 7-source list ≈ 14 WebFetch calls/week. Per-host quotas may apply.
- *Mitigation:* source-list order short-circuits on cache-hit; failure
  exit code 2 is observable.
- *Residual:* low — 14 calls/week is well under typical limits.

**Risk 3 — Session-end skill modification conflict with parallel ops
work.** The session-end skill is live infrastructure. If ops lane
simultaneously modifies it, merge conflict possible.
- *Mitigation:* §5.2 order puts session-end modification early; §5.3
  rebase catches drift.
- *Residual:* low.

**Risk 4 — Archivist fake-event fixture brittleness.** Primitive A's
final event schema may differ from the shape fixture encodes.
- *Mitigation:* fixture schema matches A shaping §4.4.1 exactly at
  D-Exec dispatch time; flag-gated emission means a schema drift shows
  up only after the flag-flip PR, at which point we regenerate the fixture.
- *Residual:* moderate — fixture regeneration is a known follow-up.

**Risk 5 — `knowledge/external_signal_sources.md` seed quality.**
Seed URLs (Boris Cherny thread, davidad thread) are third-party pages that
may 404 or change shape.
- *Mitigation:* `--fixture-dir` test path uses canned HTML; live scraping
  failures exit code 2 and are visible.
- *Residual:* low — operator-edited file per §4.8.2.

### §6.4 Coordination-timing risks

#### §6.4.1 Primitive A event emission

D emits 4 event types into A's schema. A's Phase 0 is parallel (not a
blocker). D-Exec ships with `ENABLE_D_EVENT_EMISSION=0`; flag flip is a
1-line PR scheduled after A's event-writer merges. This is the same
pattern Primitive C uses for `kb_artifact_promoted` / `V7` precheck
(C shaping §6.3).

#### §6.4.2 Ops lane cron re-arm

Two new session-scoped crons: `/loop 24h /run-archivist --mode lessons`
and `/loop 3d /review-claude-changelog`. Operator convention (MEMORY.md)
re-arms durable crons on fleet restart. Adding 2 more to the re-arm list
is a 2-line update to the ops post-restart runbook — not in Packet D-Exec
scope (ops runbook owned by ops lane). Flagged in the D-Exec PR body
as orchestrator-action at merge time.

#### §6.4.3 Primitive C V7 precheck naming

Primitive C shaping §4.6 + §286, §302, §421, §425, §457, §595, §656, §697
references the event name `archivist_candidate_generated`. Primitive A
shaping §286 names the same event `archivist_candidate_proposed`. A owns
the schema; D emits under A's name.

**Action required:** Primitive C shaping rows must be corrected to
`archivist_candidate_proposed` before C Packet ships the V7 precheck at
the canonical name. This is a C shaping drift fix — out of Packet D-Exec
scope. Flagged here so the orchestrator can route the correction to
analyst-a or analyst-c during C shape review.

#### §6.4.4 Primitive C INDEX.md generator

D.5 adds `knowledge/external_signal_sources.md`. For INDEX.md completeness,
that file must appear in C's auto-regenerated INDEX. If C's INDEX
generator has landed at D-Exec merge time, the INDEX update ships in
D-Exec. If not, the update is deferred to the next C INDEX regeneration
run — canary scenario §98 (verification_contract/shaping.md §293)
catches INDEX staleness post-merge.

#### §6.4.5 Primitive B.11 + B.12 follow-ups

D may eventually propose orchestration-recipe candidates into
`knowledge/_candidates/recipes/` (B.11) and improvement-metric candidates
into `knowledge/_candidates/<date>_improvement_metrics.md` (B.12). Neither
is Phase 0 scope. Noted as follow-up: once B.11 and B.12 schemas land,
extend archivist with `--mode recipes` and `--mode improvement-metrics`
sub-modes mirroring §4.1 / §4.2. Not blocking.

### §6.5 Orchestrator option

If the orchestrator judges Packet D-Exec too large for a single author
slice, §5.5 decomposition guidance offers 4 sub-packets. No shape
deviation required for decomposition — each sub-packet inherits this
shape's scope assignments.

## §7. Phase 2 Decision Inputs

Per §15.2 schema — 5 prompts with disposition. Seeded open.

### §7.1 Prompt 1 — Portability readiness

**Prompt:** Does archivist scale to multi-machine / distributed storage?

**Seed answer:** No. Archivist assumes local git working tree + local
events JSONL. Multi-machine deployment requires event consolidation + KB
mirroring — a new primitive or Primitive H portability extension.

**Disposition:** open — re-evaluate at Phase 1 proving-run close if KB
size or event volume suggests distribution need.

### §7.2 Prompt 2 — Meta-layer need

**Prompt:** Is durable (non-session-scoped) cron scheduling a platform
need surfaced by D?

**Seed answer:** Yes — the re-arm-on-restart hazard (§4.7, §6.4.2) is
real for both D crons and other lane crons. The cost is distributed across
the fleet, not specific to D. A durable scheduler primitive (or native
lifecycle-hook-based replacement) is a candidate.

**Disposition:** open — re-evaluate if the re-arm convention breaks
during the proving run (e.g., missed nightly archivist runs). Linked to
§6.4.2.

### §7.3 Prompt 3 — Kill signal

**Prompt:** What Phase 0 close observation would kill D's scope as
configured?

**Seed answer:** Candidate-to-promoted ratio <5% during the Phase 0 close
window = archivist producing noise operator ignores. Remediation: tighten
templates, shrink candidate scope, or shift to on-demand-only (drop
nightly cron). F8 criterion ≥10% at Phase 0 Readiness is the soft signal;
<5% is the hard kill.

**Disposition:** open — metric measured via §4.7 + proving-run KB
promotion log.

### §7.4 Prompt 4 — Re-evaluation needed

**Prompt:** What signals re-evaluating ADR 010 (mcp-memory-service
rejection)?

**Seed answer:** KB exceeds ~20KB or ~500 entries (per ADR 010 §"Phase 3
soft re-evaluation trigger"), OR archivist inflow exceeds operator-review
capacity sustained ≥1 week. Either trigger surfaces the decision to
orchestrator for Phase 3 review.

**Disposition:** open — metric observed via `find knowledge/ -type f |
wc -l` and operator-promotion-latency in candidate files.

### §7.5 Prompt 5 — Surprise finding

**Prompt:** If changelog review finds native Claude Code ships an
archivist-equivalent feature, what is the stewardship decision?

**Seed answer:** Retire bespoke archivist in favor of native adoption;
migrate KB + promotion workflow to native surface. This is the
native-substrate-first preference §10.9 Pattern 2 codifies.

**Disposition:** open — triggered if any `Native-substrate-signal: yes`
candidate entry affects Primitive D itself rather than other primitives.

## §8. Verification Plan

Every §3 row enumerated with its surface (per §4.3 analyst prompt-policy
requirement). Surfaces match `verification_contract/shaping.md` §2 table
defaults.

| Row | Surface | Class per §2 table | Runner |
|---|---|---|---|
| D.1 | `tests/unit/test_archivist.py` | unit test | pytest |
| D.1a | `tests/unit/test_archivist_cli.py` + `--help` exit-0 | unit test + named command | pytest + bash |
| D.1b | `tests/unit/test_archivist.py::TestGCMode` | unit test | pytest |
| D.1c | SC #15 proving-run log | outcome metric | ops dashboard + KB promotion log grep |
| D.2 | `tests/unit/test_session_postmortem.py` | unit test | pytest |
| D.2a | session-end SKILL.md Phase-4.5 section + operator-review prompt | skill-manifest schema + operator review | review-driver V3 + operator |
| D.3 | `tests/unit/test_changelog_review.py` | unit test | pytest |
| D.3a | `tests/unit/test_changelog_review_cli.py` + `--help` exit-0 | unit test + named command | pytest + bash |
| D.4 | `.claude/skills/run-archivist/SKILL.md` acceptance command | skill-manifest schema | review-driver V3 |
| D.4a | `.claude/skills/review-claude-changelog/SKILL.md` acceptance command + SC #19 run log | skill-manifest schema + outcome metric | review-driver V3 + ops run log |
| D.5 | `agent_readability_lint.py` clean + operator-review prompt "≥5 URLs with category + last-scraped" | KB-class artifact lint + operator review | agent_readability_lint + operator |
| D.6 | proving-run KB promotion log (§11-D kill criterion ≥10%) | outcome metric | KB promotion log grep |

**Pattern-10 Coverage for D section:** 12/12 rows carry named surfaces.
`verification_contract/map.md` §Primitive D block (5 rows as written)
covers the top-level summary; this shaping expands into 12 sub-rows for
execution tractability. Net effect: `verify_map_coverage.py` on map.md
remains green; internal-to-shape rows are walked by
`agent_readability_lint.py check pattern-11` (Primitive C deliverable).

## §9. References

- `plans/steward_platform/governing_plan.md` §5-D (lines 444-490), §10.9
  Patterns 7/8/9/10/11, §15.2, §15.3, §15.4
- `plans/steward_platform/adrs/` — ADR 001 (platform pattern reset), ADR
  010 (mcp-memory-service evaluation)
- `plans/steward_platform/1_primitive_A/shaping.md` §4-6 (event schema),
  §180 (archivist lifecycle row), §286-289 (event rows)
- `plans/steward_platform/2_primitive_B/shaping.md` §1074 (B.12
  improvement metrics), §1256 (B.11 recipe archive — D follow-up)
- `plans/steward_platform/3_primitive_C/shaping.md` §4.1 (KB layout), §4.6
  (V7 precheck — naming-coordination), §286-302 (event references), §6.3
  (flag-gating pattern)
- `plans/steward_platform/verification_contract/map.md` lines 57-65
  (Primitive D rows)
- `plans/steward_platform/verification_contract/shaping.md` §2 (surface
  table), §4.3 (analyst prompt-policy), §10 (sub-plan skeletons)
- `plans/steward_platform/claude_code_changelog_implications.md` §5
  (changelog review spec), §6 (external-signal sources)
- `plans/steward_platform/canary_scenarios/dogfood.md` lines 97-98
  (archivist canary observables)
- `.claude/skills/session-end/SKILL.md` (existing session-end skill; D.2a
  modification target)
- `.claude/rules/prompt_policy/analyst.md` §"Verification-surface-at-shaping"
  — this document's authoring policy
- `CLAUDE.md` § Source Layout — library-in-src / CLI-in-scripts split
  rationale
