# Shaping: Verification Contract + Canary Scenario (Packet 2a)

**Date:** 2026-04-23
**Lane:** analyst-a
**Packet:** `b3c2cf5c5f74` (Packet 2a — shaping only; execution belongs to Packet 2b)
**Parent plan:** `plans/steward_platform/governing_plan.draft8.md`
**Siblings in flight:** Packet 1 (author-b, disjoint scope: §5-B prompt-policy + §15 template sections)
**Status:** DESIGN-SPEC — no plan / template / ADR / sub-plan edits in this artifact.
**Purpose:** Produce a shaping document concrete enough that an author-lane execution packet (Packet 2b) can be authored from it with zero additional shaping work.

---

## §1. Scope of this document

This document specifies exactly the plan-text edits and deliverable scaffolds needed to:

1. Encode a new `Pattern 10 — Verification surface per deliverable (strict-existence / lenient-form)` into `§10.9` of the steward platform governing plan.
2. Split the current (Phase 1–only) Primitive H into `H.0` (Phase 0 mini-canary) and `H.1` (Phase 1 full reliability suite).
3. Add Success Criteria #21 (verification-contract map coverage) and #22 (Phase 0 canary) to `§13`.
4. Extend the §12 Risks table with a new row (canary becomes silent green check).
5. Spec the full dogfood canary scenario, its enforcement, and its telemetry.
6. Spec two new sub-plan skeletons (`verification_contract/sub_plan.md`, `canary_scenarios/dogfood.md`).
7. Spec six+ independent enforcement surfaces (template, skill refusal, lint, prompt-policy, commit-footer, review-driver precheck, canary) with per-surface failure-mode coverage.
8. Produce the exact Packet 2b author-execution spec.

### §1.1 Motivation (one paragraph)

The draft 8 plan already gates at multiple layers (Phase 0 Readiness, Phase 1 Validation, `§6.4` Preflight, `§13` Success Criteria, `§11` Kill Criteria, `§4.3` Baseline, Pattern 7 Rollback). None of them *uniformly* mandates a verification surface per deliverable at *plan-time*. The failure mode is silent-running features: a skill, hook, or script ships; runs in background; nobody asserts against its output; drift goes undetected until it is already load-bearing failure. Pattern 10 closes this gap by making verification-surface enumeration a plan-authoring obligation — same discipline that `Goal #16` made for agent-readability and Pattern 9 made for load-bearing-ownership.

### §1.2 Relationship to existing patterns

| Existing pattern | Covers | Gap Pattern 10 fills |
|---|---|---|
| Pattern 7 (Reversibility-as-default) | *rollback* path at change-time | does not mandate a *forward* verification surface |
| Pattern 8 (Observable-by-default) | *trace emission* from durable changes | does not mandate an *assertion* on that trace |
| Pattern 9 (Load-bearing-ownership lint) | *enumeration* in owning primitive | does not mandate the Work bullet carry a verification surface |
| Goal #16 + agent-readability scorecard | *loadability* of artifacts | does not mandate that the deliverable described has a way to prove it works |

Pattern 10 is the forward-verification complement to Pattern 7's rollback-verification and Pattern 8's emit-verification. Together the three form: *change → prove → observe → reverse*.

---

## §2. Pattern 10 — final text

**Location:** `§10.9` of `plans/steward_platform/governing_plan.md` (or `governing_plan.draft8.md` pre-promotion), inserted after Pattern 9.

**Final text (verbatim insertion):**

> **Pattern 10 — Verification surface per deliverable (strict-existence / lenient-form, draft 8 follow-on).**
> Every plan deliverable — every §N.M Work bullet, every Phase 0/1 Readiness criterion, every preflight item, every sub-plan deliverable row — names a *verification surface*. Existence of the named surface is strict: no deliverable ships or is declared ready without one. Form of the surface is lenient: the named surface is matched to the deliverable class, not forced into pytest uniformity. The discipline prevents the silent-running-feature failure mode (a skill/hook/script/policy ships, runs in the background, accrues drift, and is only noticed after it is already load-bearing). Pattern 10 is the forward-verification complement to Pattern 7 (rollback-verification) and Pattern 8 (emission-verification).
>
> **Acceptable verification-surface forms, by deliverable class:**
>
> | Deliverable class | Default surface | Acceptable alternatives |
> |---|---|---|
> | New Python module under `src/**` or `scripts/internal/**` | unit test under `tests/unit/test_<name>.py` referenced by path | integration test; named runnable command with documented expected output |
> | New `.claude/hooks/**` file | rollback test (disable-hook path exercised) referenced by path | conditional-hook smoke; canary-scenario coverage |
> | New `.claude/skills/**` entry | named runnable acceptance command in `SKILL.md` | canary-scenario coverage; operator-review prompt with explicit pass criterion |
> | New `.claude/rules/**` file | operator-readable review prompt embedded in the rule | — |
> | New plan/sub-plan §N.M row or table cell | `verification_contract/map.md` row (self-referencing Pattern 10) | — |
> | New KB entry (`knowledge/**`) | `INDEX.md` inclusion + lint pass | — |
> | New adapter under `src/bid_euchre/ops/adapters/**` | unit test + integration test against default cell | smoke via canary scenario |
> | Config change (`.claude/settings.json`, `permissions.allow`) | rollback test (revert-commit smoke) | — |
> | Prompt-policy edit (B.3) | trace-ID or incident-fingerprint cited in commit; rollback via version pin | — |
> | Event schema addition (Primitive A v1.N) | replay-harness compatibility assertion | — |
> | ADR | (see note below) | — |
>
> **ADR note (preserves strict-existence).** ADRs document *decisions*, not *runnable code*; pytest is inapplicable. Their named verification surface is the Pattern 7 rollback path (ADR supersession route), combined with the commit citation or trace evidence in the ADR's `Source evidence` section. This keeps strict-existence intact ("every deliverable has a named surface") without forcing a runtime assertion where none makes sense.
>
> **Enforcement surfaces.** Six+ independent surfaces enforce Pattern 10; see `plans/steward_platform/verification_contract/shaping.md` §3 for the catalog. No single surface is load-bearing; each catches a distinct failure mode. Enforcement is defense-in-depth, modeled on §10.9 closing paragraph: "No pattern is aspirational-only; each has at least one mechanization path."
>
> **Plan-authoring obligation (single-pattern framing).** The plan-authoring discipline (every new deliverable row names its verification surface *at plan-time*, not post-hoc) is Pattern 10 itself, not a separate Pattern 11. Pattern 10 is one *property* (deliverables have verification surfaces) with multiple *enforcement surfaces* (plan template, skill refusal, lint, prompt-policy, commit lint, review-driver precheck, canary suite). This mirrors Pattern 9's structure (property: load-bearing ownership; enforcement: lint).

### §2.1 Pattern-10-vs-Pattern-11 framing call

**Decision: single Pattern 10, not split into Pattern 10 + 11.**

Two candidate framings were considered:

**Option A (adopted):** One pattern with multiple enforcement surfaces. Rationale: the plan-authoring obligation and the codebase-property are *the same property observed at different times* (creation-time vs runtime). Splitting would produce a Pattern 11 whose content is entirely mechanistic enforcement of Pattern 10's property — redundant with Pattern 9's existing property-plus-enforcement shape.

**Option B (rejected):** Pattern 10 = "every codebase deliverable has a runnable verification"; Pattern 11 = "every *plan* deliverable names its verification surface at plan-time." Rationale for rejection: creates a seam where a reviewer could check 10 but not 11 (or vice versa) and conclude compliance despite a hole. A single pattern with mandatory enforcement at both plan-time and PR-time is structurally safer.

The Packet 2b author should *not* relitigate this unless they discover a concrete case where a deliverable can satisfy one framing but not the other.

---

## §3. Enforcement layers (defense in depth)

Pattern 10 is enforced by seven independent surfaces. Each catches a distinct failure mode. Packet 2b must land or scaffold all seven; each has a named owner in §6.

### §3.1 Enforcement catalog

| # | Surface | Where it sits | What it enforces | Failure mode it catches |
|---|---|---|---|---|
| i | `plans/_templates/sub_plan.md` + `execution_plan.md` + `primitive_closeout.md` — required `## Verification Plan` section | Creation-time (plan authoring) | Author cannot finalize a template-instantiated plan without naming verification surfaces per deliverable | "Plan author forgot to think about verification" |
| ii | `.claude/skills/create-plan/SKILL.md` refusal logic | Creation-time (skill-driven plan authoring) | `/create-plan` refuses to output a plan whose `Verification Plan` section is (a) missing, (b) empty, (c) stub placeholder (TBD/TODO/FIXME/XXX), (d) missing coverage of any deliverable enumerated in the plan's Work section | "Plan author used template but left placeholder in" |
| iii | `scripts/internal/agent_readability_lint.py` extension | Run-against-existing (periodic / CI) | Every `§N.M` Work bullet or Readiness bullet in `plans/**/*.md` has a matching row in the plan's Verification Plan section; every sub-plan deliverable has a matching row in `verification_contract/map.md` | "Plan was authored pre-Pattern 10 and never retrofitted" + "Post-authoring drift" |
| iv | Prompt-policy registry entries (B.3) for orchestrator / author / analyst | Behavioral (trace-cited policy version) | Lanes default to articulating verification surface at packet-shaping time (orchestrator), at implementation time (author), at shaping-doc-authoring time (analyst) | "Author implements without naming the surface" + "Analyst shapes without specifying the surface" |
| v | Commit-message `Verification:` footer lint | Commit-time | Commits that add a new deliverable (per trigger-path list §3.3) carry a `Verification: <surface>` footer naming the surface | "Author commits without linking impl to surface" |
| vi | `scripts/internal/review_driver.py` convention precheck extension | PR-time | BLOCK on merge if: plan deliverable row lacks a verification surface; the verification surface named is inappropriate for the deliverable class; the surface referenced does not exist | "Author wrote a fake/incorrect surface name" + "Plan change landed without surface enumeration" |
| vii | Dogfood canary scenario (§5) | Runtime (weekly + on-change) | The verification surfaces themselves catch a known regression class, observably via dashboard telemetry | "Verification surfaces exist but silently don't catch anything" (meta-check) |

**Coverage completeness analysis:**

| Failure mode | Caught by |
|---|---|
| Plan author forgets verification entirely | i, ii |
| Plan has Work bullet but no matching Verification Plan row | ii, iii |
| Plan has Verification Plan row but points to non-existent test/command | iii, vi |
| Author implements but forgets the surface | iv, v |
| Author cites a fake/wrong surface | vi |
| Surface exists but silently passes on everything | vii |
| Plan authored before Pattern 10 and never retrofitted | iii |
| Verification surface bit-rot (was valid, ceased to be) | iii, vii |

No single surface is load-bearing. `agent_readability_lint.py` (iii) and `review_driver.py` (vi) are the highest-leverage pair; losing either degrades enforcement meaningfully but does not silently break the pattern.

### §3.2 Per-surface home and integration detail

**(i) Templates:** Each template adds a top-level section (`## Verification Plan`) with required sub-structure. See §6.

**(ii) `/create-plan` skill:** Lives at `.claude/skills/create-plan/SKILL.md`. Currently does *not* exist (verified via `ls .claude/skills/create-plan/`). Packet 2b creates it. Refusal is a hard stop with a guidance message pointing at the template worked example. Skill is invoked from any lane via `/create-plan <kind> <path>`.

**(iii) `agent_readability_lint.py`:** Lives at `scripts/internal/agent_readability_lint.py` per draft 8 §5-C. Does not yet exist (enumerated as planned in `rework_spec.md` §4). Packet 2b's initial version ships with the Pattern 9 load-bearing-ownership lint *and* the Pattern 10 verification-surface-enumeration lint. Both lints share a plan-walker core. Rule set runs as subcommand `agent_readability_lint.py check verification-contract`.

**(iv) Prompt-policy language:** Lives under the prompt-policy registry established in Primitive B.3 (`.claude/rules/prompt_policy/<lane>.md` or equivalent). See §4 for exact per-lane text. Packet 1 (author-b, in flight) already carries the B.3 registry scaffolding; Packet 2b layers Pattern 10 clauses onto whatever B.3 home Packet 1 lands.

**(v) Commit-footer lint:** Extends existing commit-message prechecks in `scripts/internal/review_driver.py` rather than adding a new pre-commit hook. Rationale: existing PR-time lint surface is the lowest-churn integration point; pre-commit hooks sprawl faster (and `.claude/hooks/` is already consolidation-target per rework spec §5). Trigger paths §3.3.

**(vi) Review-driver precheck:** Extends the same `review_driver.py` convention prechecks as (v). Adds check IDs per §3.4.

**(vii) Canary:** Lives at `tests/reliability/canaries/dogfood_v1.py` + `.claude/skills/run-canary/SKILL.md`. Wired to weekly cron via `/loop 7d /run-canary` in the ops lane and to conditional-hook triggers on material platform changes. Full spec in §5.

### §3.3 Commit-footer lint trigger paths

Any commit whose diff matches one or more of the following patterns **must** carry a `Verification: <surface-id>` footer:

1. Adds a new file under `src/**`
2. Adds a new file under `scripts/internal/**`
3. Adds a new file under `.claude/hooks/**`
4. Adds a new file under `.claude/skills/**`
5. Adds a new file under `src/bid_euchre/ops/**`
6. Modifies `plans/_templates/**`
7. Modifies a §5 sub-deliverable row in `plans/steward_platform/governing_plan*.md` (grep pattern: `^\| B\.\d+ ` or `^\| [A-H] — `)
8. Adds a `§N.M` section to any `plans/**/*.md`, `.claude/skills/**/*.md`, `knowledge/**/*.md`
9. Adds a new ADR under `knowledge/adr/**` or `plans/steward_platform/adrs/**`
10. Modifies `.claude/settings.json`, `permissions.allow`, `.claude/rules/prompt_policy/**`

Detection is path-glob + regex over the PR's `git log` across the base-to-head range. False-positive tolerance: allow the footer on any commit in the range, not only the introducing one (authors may add the footer as a follow-up commit within the same PR).

**Failure-mode message:** `Verification footer missing. This diff introduces or modifies a plan deliverable (§3.3 of verification_contract/shaping.md). Add a 'Verification: <surface>' commit-message footer naming the surface per Pattern 10 (§10.9 governing plan). Acceptable surface forms: see the Pattern 10 table.`

### §3.4 Review-driver precheck check IDs and severity

Per `.claude/rules/deferred/60_review_gate.md` taxonomy:

| Check ID | Condition | Severity | Action |
|---|---|---|---|
| V1 | Plan change adds a §5 sub-deliverable row without a matching Verification Plan entry | **BLOCK** | Fail precheck; message names the missing row |
| V2 | New deliverable file landed (per §3.3 trigger paths) and no commit in PR range carries a `Verification:` footer AND PR body `Verification Performed` section is empty | **BLOCK** | Fail precheck |
| V3 | New deliverable landed; verification surface named in PR body or commit footer does not exist at the path/ID cited | **BLOCK** | Fail precheck |
| V4 | New deliverable class and named surface class mismatch per §2 table (e.g., new `.claude/hooks/**` file, verification = "operator review" without rollback test) | **WARN** | Pass with follow-up issue; auto-file `fix:process` |
| V5 | Commit adds new file under `§3.3` trigger paths and has no `Verification:` footer, but PR body has `Verification Performed` section with matching content | **INFO** | Pass silently; recorded in review report only |
| V6 | Plan or sub-plan section adds a `§N.M` Work bullet but `verification_contract/map.md` has no row for it | **WARN** | Pass with follow-up issue; authors can backfill map |

**Deliverable-class → verification-class expectation map:** as in §2 Pattern 10 table.

---

## §4. Prompt-policy language (B.3 extensions)

Exact text to add to each lane's prompt-policy entry in `.claude/rules/prompt_policy/<lane>.md` (or whatever registry home Packet 1 lands). Language is additive; does not replace existing policy content.

### §4.1 Orchestrator prompt-policy clause

```
## Verification-surface-at-packet-shape (Pattern 10, §10.9)

When shaping a task packet whose scope creates or modifies a plan deliverable, a
codebase file under src/**, scripts/internal/**, .claude/hooks/**,
.claude/skills/**, or a prompt-policy edit, include a named verification surface
in the packet's Validation field. Use the Pattern 10 table (§10.9 of the
governing plan) to pick a default surface for the deliverable class; deviate
only with explicit rationale in the packet description.

Acceptable surfaces include: unit test path; integration test path; named
runnable command with expected output; operator-review prompt with specific
pass criterion; canary-scenario coverage reference; event-schema query with
expected shape; rollback-test path.

Never dispatch a packet whose Validation field is empty or says only "tests
pass." If you cannot name the surface, the task is shaping-work and belongs
in the analyst lane, not an author lane.
```

### §4.2 Author prompt-policy clause

```
## Verification-surface-at-slice-close (Pattern 10, §10.9)

Before marking any slice complete, confirm the verification surface named in
the task packet's Validation field actually ran and emitted the expected
signal. If the surface is:
  - a named test: run it; paste pass output in the PR body Verification
    Performed section
  - a named command: run it; paste output
  - a review prompt: include the prompt + observed result in PR body
  - an event-schema query: include the query + matching event record shape
  - a canary reference: name the canary run ID + link to its dashboard
    snapshot
  - a rollback test: execute forward-then-reverse; paste both outputs

Commits that introduce a new file matching the §3.3 trigger-path list carry
a 'Verification: <surface>' footer. The surface identifier must resolve to
a real path or command — review_driver.py will BLOCK on fake identifiers.

If you cannot verify the surface (missing dependency, surface not yet
implemented upstream), escalate via blocker message to orchestrator rather
than proceeding.
```

### §4.3 Analyst prompt-policy clause

```
## Verification-surface-at-shaping (Pattern 10, §10.9)

When drafting a shaping document, sub-plan, or execution plan, every
proposed deliverable names a verification surface using the §2 table of
`plans/steward_platform/verification_contract/shaping.md`.

"Operator review" is a valid surface form but must specify *what* the
operator is looking for (the specific observable, the pass threshold, the
triggering condition). A shaping doc that says "operator will verify" with
no specified observable is insufficient.

Deliverables whose verification surface is genuinely unclear at shaping
time are flagged explicitly with `Verification: TBD — blocking for
<reason>` so the orchestrator can choose to (a) shape further, (b) accept
the surface-gap as a known risk, or (c) reject the deliverable until the
surface is specifiable.

Shaping docs end with a `## Verification Plan` section enumerating every
§N.M deliverable row and its surface, same shape as the templates in
plans/_templates/.
```

### §4.4 Common (ops + review) clause (optional, less load-bearing)

```
## Verification-surface-awareness (Pattern 10 supplementary)

When observing a PR, packet, or event stream, surface verification-surface
gaps explicitly. Missing or hand-wavy surfaces are triage-worthy signals
on par with missing rollback paths (Pattern 7) or missing emission
(Pattern 8).
```

---

## §5. Canary scenario specification — Steward Dogfood Canary

### §5.1 Summary

**Name:** `dogfood-v1` (canary ID pattern: `dogfood-v1-<YYYY-MM-DD>-<HHMM>`)
**Home:** `tests/reliability/canaries/dogfood_v1.py` + `plans/steward_platform/canary_scenarios/dogfood.md` (sub-plan)
**Cadence:** weekly (`/loop 7d /run-canary` in ops lane) + on-demand (`/run-canary`) + conditional-hook triggered on material platform changes
**Pass target:** ≥4 consecutive weekly passes required before Phase 0 closeout can be declared (SC #22 gate)

### §5.2 Bounded task spec

The canary executes one bounded, deliverably-small self-improvement task end-to-end through every substrate surface that a real task would exercise.

**Task description (operator-readable):**

> Add a `last_verification_run` field to `src/bid_euchre/ops/dashboard.py` TUI output showing the timestamp and pass/fail state of the most recent canary run. Create a unit test asserting the field renders. File a mini-ADR under `knowledge/adr/` recording the field's purpose. Open a PR. Merge after CI + review passes. Confirm the archivist (Primitive D) creates a candidate entry referencing the canary's trace ID within 24h. Execute rollback: revert the merge; confirm dashboard reverts; confirm `canary_rollback_complete` event fires.

Scope is chosen to exercise: planning (packet creation) → dispatch (ops task queue) → author execution (branch, edit, test, commit) → review (review_driver.py full loop) → merge (post-merge-notify.sh hook) → archivist (Primitive D candidate generation) → KB (INDEX regeneration) → rollback (Pattern 7 path).

Task is small enough (1 file edit + 1 test + 1 ADR stub + 1 PR) that failures isolate to substrate behavior, not task complexity.

### §5.3 Pass metrics (9 grep-verifiable checks)

Canary passes *iff all 9* assertions hold for a single `canary_id` within the elapsed-time window.

| # | Assertion | Grep / query |
|---|---|---|
| 1 | `canary_run_start` event emitted with canary_id | event stream: `event_type=canary_run_start AND canary_id=dogfood-v1-<id>` |
| 2 | Task packet transitioned created → dispatched → completed within window (default 6 hours, operator-configurable) | `ops.py task show <packet_id>` → status=completed; timestamps bounded |
| 3 | PR exists, CI green, `reviewing-changes` status ∈ {success, warn}, was merged | `gh pr view <pr> --json state,mergeable,statusCheckRollup` |
| 4 | `task_completed` event emitted for the canary packet with matching canary_id | event stream query |
| 5 | Archivist candidate file at `knowledge/_candidates/<date>.md` contains canary_id reference | grep `<canary_id>` in file |
| 6 | `knowledge/INDEX.md` regeneration succeeded post-merge (no stale INDEX relative to KB filesystem) | diff `INDEX.md` against `find knowledge/ -type f` result |
| 7 | Dashboard renders the new `last_verification_run` field | scrape `ops.py dashboard` TUI snapshot; regex-match the field label + a timestamp |
| 8 | Rollback PR (revert) opened, CI green, merged; `canary_rollback_complete` event emitted | `gh pr` + event stream query |
| 9 | `canary_run_complete` event emitted with `success=true` and `elapsed_seconds` field populated | event stream query |

**Expected-event-type hash:** canary runner computes a hash of `{event_type, canary_id}` pairs observed during a run. Deviations from the last green run's hash fail the canary *loudly* with a `canary_event_schema_drift` signal, even if the 9 pass-metric assertions all hold — prevents silent schema drift. Mitigates §7 risk row (see §7).

### §5.4 Failure behaviors

**Soft fail (canary-slow):**
- Trigger: all 9 assertions pass but elapsed-time exceeds soft-warn threshold (default 2× median of last N successful runs, N=4)
- Action: file a GitHub issue with label `canary-slow`; do not escalate via ops alert push
- Dashboard: `canary_last_status = slow`

**Hard fail (canary-fail):**
- Trigger: one or more of the 9 pass-metric assertions unmet, OR expected-event-type hash mismatch
- Action: file a GitHub issue with label `canary-fail`, priority high; escalate via ops alert push; operator Telegram notification
- Dashboard: `canary_last_status = fail`; streak counter resets to 0

**Silent fail (canary-silent):**
- Trigger: no canary run recorded in `ops.py dashboard canary_last_pass` for ≥14 days
- Action: ops monitor raises `canary-silent` alert; escalate to operator via Telegram
- Dashboard: `canary_last_status = silent`

**Expected-event-type hash mismatch (canary_event_schema_drift):**
- Trigger: pass-metric assertions pass but observed `{event_type}` set differs from last-green-run hash
- Action: file issue labeled `canary-schema-drift`; do not escalate push (not an outage — is a signal)
- Dashboard: `canary_last_status = schema-drift`; streak does *not* increment

### §5.5 Cadence

- **Weekly cron:** `/loop 7d /run-canary` installed in the ops lane at Phase 0 kickoff. Cron spec: `0 9 * * MON` via ops `/loop` mechanism (per `.claude/skills/loop/SKILL.md`).
- **On-demand:** any lane invokes `/run-canary` to trigger a run; useful during Phase 0 as primitives land (verify the canary still passes after each primitive closeout).
- **Conditional-hook (material-platform-change):** triggered on any PR merging to:
  - `.claude/skills/**`
  - `.claude/hooks/**`
  - `src/bid_euchre/ops/core/**`
  - `scripts/internal/review_driver.py`
  - `src/bid_euchre/ops/dashboard.py` (self-aware — dashboard changes trigger dashboard-assertion re-verification)
  - `.claude/rules/prompt_policy/**` (any prompt-policy registry commit)
  - Any `§N.M` modification in `plans/steward_platform/governing_plan*.md`

  Hook implementation: native conditional hook subscribing to merge events, filtered to the above path-globs. Hook invokes `/run-canary --trigger=material-change --changed-paths=<list>`.

### §5.6 Dashboard integration

`ops.py dashboard` renders a `Canary` row:

```
Canary  last_pass: 2026-04-20 09:14  streak: 4  status: success  elapsed: 312s
```

Fields:

- `canary_last_pass` (datetime): last `canary_run_complete` with `success=true`
- `canary_pass_streak` (int): consecutive successes since last non-success
- `canary_last_status` (enum: success | slow | fail | silent | schema-drift): most recent terminal state
- `canary_last_elapsed` (seconds): for trending

**Sub-metric sparklines** (mitigation for §7 risk row): dashboard panel sub-row shows mini-sparklines for `elapsed_seconds`, `event_count`, `archivist_lag_seconds`, `kb_index_regeneration_ms` across the last 8 runs. Drift visible before threshold breaches.

### §5.7 Event schema additions (Primitive A v1.N additive)

Per `§5-A` event-schema-versioning policy: additive changes are v1.N compatible with the replay harness.

New event types added:

| Event type | Fields |
|---|---|
| `canary_run_start` | canary_id, trigger (cron / on-demand / material-change), canary_version (dogfood-v1), started_at, lane_id |
| `canary_run_complete` | canary_id, success (bool), elapsed_seconds, pass_metrics (dict of 9 booleans), event_type_hash, completed_at |
| `canary_run_fail` | canary_id, failed_assertions (list of numeric indices per §5.3), elapsed_seconds, failed_at |
| `canary_rollback_complete` | canary_id, rollback_pr, reverted_at |

---

## §6. Template additions

All three templates add a required `## Verification Plan` section. Packet 2b creates the two new templates; edits the existing one.

### §6.1 `plans/_templates/sub_plan.md` (edit existing)

Current file exists. Add after the Work section and before Rollback:

```markdown
## Verification Plan

_Required per Pattern 10 (§10.9 governing plan). Every deliverable below
ties to a named verification surface. Strict existence; lenient form._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| (row per Work bullet or Readiness criterion) | (per §10.9 Pattern 10 table) | (path or command) | (lane) | (observable pass) |

**Worked example:**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2 `scripts/internal/verify_map_coverage.py` | new Python script | `tests/unit/test_verify_map_coverage.py::test_coverage_threshold` | author | pytest passes; coverage computed is ≥90% on seeded fixture |
| §3 `verification_contract/map.md` authoring | new KB-class artifact | `INDEX.md` inclusion + `agent_readability_lint.py check verification-contract` clean | analyst | lint exits 0 |
| §4 feature flag `ENABLE_MAP_LINT` | config change | rollback test: flip flag off, re-run lint, expect degraded-but-non-fatal mode | ops | documented in §Rollback |

**Surface-class defaults** — see Pattern 10 table at `§10.9` of
`plans/steward_platform/governing_plan.md` for the full deliverable-class
→ default-surface mapping.
```

### §6.2 `plans/_templates/execution_plan.md` (new file)

Packet 2b creates. Same `## Verification Plan` section as §6.1, with the worked example tailored to an execution-plan context (usually: "PR N validates X" shape). Execution plans may omit per-slice rows if all slices roll up to a single surface, but must state this explicitly.

### §6.3 `plans/_templates/primitive_closeout.md` (new file)

Packet 2b creates. The primitive-closeout template has a `## Verification Plan` section where each **Readiness** criterion (plural, per primitive) is a row and each row's "Acceptance condition" column cites the *actual observed result* (not the plan-time target). This gives Phase 2 decision-gate analysts a closeout-artifact view of "what verification surface was actually demonstrated" per primitive.

### §6.4 Section interaction with §15.2 Phase 2 Decision Inputs

The Verification Plan section sits *before* the Phase 2 Decision Inputs section. Both are required; the digest script (`compile_decision_inputs.py`) does not care about Verification Plan content but the `agent_readability_lint.py check verification-contract` sub-command does.

---

## §7. §12 Risk table — new row

Add to `§12 Risks` after the existing last row (plugin-ecosystem adoption risks, draft 8):

> | Canary becomes silent green check (draft 8 follow-on, Pattern 10 enforcement) | Medium likelihood, high impact. The dogfood canary passes weekly without actually exercising the verification surfaces it purports to test — becomes a silent green checkbox while real verification discipline decays. **Mitigations:** (1) canary assertions include an **expected-event-type-set hash**; mismatches fail loudly even when the 9 pass-metric assertions themselves succeed (see `§5.3` of `verification_contract/shaping.md`); (2) dashboard panel renders sub-metric **sparklines** (elapsed_seconds, event_count, archivist_lag, INDEX regen time) per canary run — operator sees drift before threshold breach (see `§5.6`); (3) **quarterly `/canary-review` skill** forces operator to audit: did recent canary passes catch known failure modes? If not, add assertions or retire the canary. Documented in `plans/steward_platform/canary_scenarios/dogfood.md` §Audit. |

---

## §8. Success Criteria additions (§13)

Insert after SC #20 (current final item):

### §8.1 SC #21 — Verification-contract map coverage

> 21. **Verification-contract map coverage.** `plans/steward_platform/verification_contract/map.md` is committed and covers ≥90% of plan deliverables: every `§5` primitive sub-deliverable row, every `§5-X` Phase 0 Readiness bullet, every `§5-X` Phase 1 Validation bullet, every `§6.4` preflight item, every `§14` Open Item once resolved into a concrete deliverable. Map columns: `Deliverable | Class | Verification surface | Owner | Acceptance condition`. Acceptance: the `agent_readability_lint.py check verification-contract` sub-command exits clean against the live plan tree at Phase 0 close AND the orchestrator records map review at Phase 0 kickoff with a commit linking to the review note.

### §8.2 SC #22 — Phase 0 mini-canary (dogfood)

> 22. **Phase 0 dogfood canary passing streak.** The `dogfood-v1` canary scenario (`plans/steward_platform/canary_scenarios/dogfood.md`) runs weekly starting Phase 0 week 1 AND achieves **≥4 consecutive weekly passes** before Phase 0 closeout can be declared. Failures file follow-up issues automatically (`canary-fail` / `canary-slow` / `canary-silent` / `canary-schema-drift` labels per `§5.4` of `verification_contract/shaping.md`). Phase 0 closeout is blocked if streak is <4 or if the last run's status is not `success`. Dashboard `canary_last_pass` + `canary_pass_streak` serve as the operator-readable gate display.

---

## §9. Primitive H split — H.0 / H.1

### §9.1 Motivation

Draft 8 places all of Primitive H in Phase 1 (concurrent with the proving run), on the rationale that the replay harness needs live proving-run events to reconstruct against. That rationale holds for *replay*, *failure-injection*, *postmortem-generator*, and the *full* 3–5-task canary suite. It does not hold for *one bounded canary scenario running weekly on existing substrate*, which is exactly the discipline Pattern 10 needs to demonstrate at Phase 0.

The split:

- **H.0 — Phase 0 mini-canary.** One bounded scenario (dogfood-v1). Starts running in Phase 0 week 1. Gates Phase 0 closeout via SC #22.
- **H.1 — Phase 1 full reliability suite.** Replay harness, ≥3 failure-injection scenarios, postmortem generator, expanded canary suite (3–5 scenarios, *including the dogfood canary*), idempotency checklist, portability-dry-run reuse design intent.

### §9.2 Bullet assignment (which current H bullets go where)

Current Primitive H Work bullets (`§5-H`):

| # | Bullet | H.0 | H.1 |
|---|---|---|---|
| 1 | `tests/reliability/replay.py` harness | | ✓ |
| 2 | Failure-injection scenarios (≥3) | | ✓ |
| 3 | Automated postmortem generator | | ✓ |
| 4 | Rollback-validation coverage for Phase 1 changes | | ✓ |
| 5 | Canary task suite (3–5 canonical tasks) — *split* | one bounded scenario: dogfood-v1 | expand to full 3–5 task suite, including dogfood-v1 already running |
| 6 | Idempotency checklist for side effects | ✓ (file lands Phase 0; PR-template integration also Phase 0) | (ongoing discipline Phase 1) |
| 7 | Phase 2 portability-dry-run reuse (design intent) | | ✓ |

**H.0 gets:** bullet 5 (single-scenario), bullet 6 (file + template integration)
**H.1 gets:** bullets 1, 2, 3, 4, 7, and the *expansion* of bullet 5

Idempotency checklist lands Phase 0 because the file itself is a static PR-review checklist — no runtime dependency on Phase 1 events. PR template integration likewise is Phase 0 config work.

### §9.3 Phase 0 Readiness (H.0) — new section

Insert into `§5-H` governing plan text as a new sub-section before current "Phase 1 Readiness":

```
Phase 0 Readiness (H.0):
- dogfood-v1 canary implemented per plans/steward_platform/canary_scenarios/dogfood.md
- /run-canary skill registered and invokable from any lane
- Weekly cron installed in ops lane (/loop 7d /run-canary)
- Conditional hook wired for material-platform-change triggers (§5.5 trigger-path
  list in verification_contract/shaping.md)
- All 9 pass metrics grep-verifiable on a test-driven seeded run
- Dashboard integration live: canary_last_pass, canary_pass_streak,
  canary_last_status, canary_last_elapsed visible in `ops.py dashboard`;
  sparklines render
- Event schema v1.N additive: canary_run_start, canary_run_complete,
  canary_run_fail, canary_rollback_complete registered in the unified schema
- Failure-mode routing live: canary-slow, canary-fail, canary-silent,
  canary-schema-drift issues auto-file with correct labels
- Rollback path validated: the canary itself can be disabled (feature flag
  ENABLE_CANARY_CRON off; weekly cron removable) without leaving dangling
  scheduled state
- Idempotency checklist committed at .claude/rules/idempotency_checklist.md
- PR template at .github/pull_request_template.md includes idempotency
  checklist section
- ≥4 consecutive weekly passes recorded (gates Phase 0 closeout per SC #22)
```

### §9.4 Phase 1 Readiness (H.1) — edit

Current "Phase 1 Readiness" section content stays, minus the "canary task suite (3–5 tasks) and one trigger path wired" bullet (that moved to H.0 as dogfood-v1). H.1 Readiness now reads:

```
Phase 1 Readiness (H.1, mid-Phase-1, before proving run produces its main evidence):
- Replay harness exists and can reconstruct at least 1 lifecycle (may use a non-proving-run seed task).
- At least 2 failure-injection scenarios implemented; both pass.
- Automated postmortem generator template committed and smoke-tested.
- Canary task suite expanded to 3–5 tasks (dogfood-v1 already running from H.0;
  add 2–4 more per operator selection).
- Idempotency checklist actively cited in PR reviews during Phase 1.
```

### §9.5 Phase 1 Validation (H.1) — edit

Existing `§5-H` Phase 1 Validation content remains. Add one bullet:

```
- dogfood-v1 canary continues passing weekly through Phase 1; no regression
  in canary_pass_streak > 2-week window; any canary fail during Phase 1
  produces a postmortem artifact per the automated generator.
```

### §9.6 §10.7 Phase-membership table update

Current §10.7 design-coupling note references H as a whole Phase 1 primitive. Update:

```
Primitive H is split across phases (draft 8 follow-on): H.0 is Phase 0
(mini-canary, gating Phase 0 closeout via SC #22); H.1 is Phase 1 (replay
harness, failure-injection, postmortem, expanded canary suite, portability
dry-run intent). The §10.7 portability-decision readiness criterion
references H.1 Phase 1 Validation specifically; H.0 passing does not by
itself qualify portability readiness.
```

### §9.7 §11-H kill criterion split

Current `§11` kill table row for H is single-row. Split into H.0 + H.1:

```
| H.0 — Dogfood canary (Phase 0) | Canary fails to achieve ≥2 weekly passes in any 4-week window during Phase 0 → canary scope is ill-chosen or substrate is unstable; demote to simpler event-diff assertion OR re-scope canary to a narrower task. |
| H.1 — Reliability lab + expanded canary (Phase 1) | <2 replay scenarios pass or <3 failure-injection scenarios exercised (at least one post-hoc analyst-selected); OR expanded canary suite never runs on a material platform change during the proving run → demote to a simpler event-diff assertion set; postmortem generator + canary expansion deferred. Demotion blocks §10.7 portability-decision readiness. |
```

Note: H.0 kill threshold is "fails to achieve ≥2 weekly passes in any 4-week window" — weaker than the SC #22 "≥4 consecutive" gate. The gate blocks *declaration* of Phase 0 complete; the kill triggers *reconsideration* of whether the canary is the right scenario shape. Both have distinct purposes.

---

## §10. Sub-plan skeletons (specs — not authored by this shaping doc)

Packet 2b creates these files. The shaping doc only specifies their structure.

### §10.1 `plans/steward_platform/verification_contract/sub_plan.md` — skeleton spec

Headers required:

- `# Sub-Plan: Verification Contract Map` (title)
- Frontmatter: Status, Parent, Owner, Scope
- `## §1. Purpose` — one paragraph: map.md is the canonical reference Pattern 10 enforcement surfaces cite when auditing coverage
- `## §2. Work`
  - §2.1 Author `map.md` with columns: Deliverable | Class | Verification surface | Owner | Acceptance condition
  - §2.2 Author `verify_map_coverage.py` — computes coverage ratio; fails if <90%
  - §2.3 Integrate coverage check into `agent_readability_lint.py check verification-contract` sub-command
  - §2.4 Map review log at `plans/steward_platform/verification_contract/review_log.md` (append-only)
- `## §3. Phase 0 Readiness`
  - map.md exists at `plans/steward_platform/verification_contract/map.md`
  - Row coverage ≥90% versus enumerated deliverable set (currently ~60 rows across §5 sub-deliverables + §6.4 preflight items + ≥2 Readiness bullets per primitive; target ≥54 rows; exact count computed by verify_map_coverage.py)
  - Every row's "Verification surface" matches the deliverable-class default from §10.9 Pattern 10 OR carries an explicit justification in a `Notes` column
  - Orchestrator review logged at Phase 0 kickoff
- `## §4. Phase 1 Validation`
  - Map regenerated at Phase 1 close; coverage still ≥90%; drift since Phase 0 close documented in review_log.md
- `## §5. Verification Plan` (the template-mandated section — §2 of sub-plan gets verified against its own product)
- `## §6. Rollback`
  - map.md version history preserved in git; revert via PR
  - verify_map_coverage.py can be skipped via `--allow-under-coverage` flag for explicit one-off operator overrides, flag usage logged
- `## Outcome` (to be filled)
- `## Phase 2 Decision Inputs` (per §15.2 schema — 5 prompts + disposition)

### §10.2 `plans/steward_platform/canary_scenarios/dogfood.md` — skeleton spec

Headers required:

- `# Sub-Plan: Steward Dogfood Canary Implementation (dogfood-v1)`
- Frontmatter: Status, Parent (`§5-H.0` of governing plan), Owner (author for impl + ops for cron + orchestrator for monitoring)
- `## §1. Purpose` — one paragraph: dogfood-v1 is the Phase 0 mini-canary that proves the verification surfaces actually catch regressions; SC #22 gates Phase 0 closeout on its passing streak
- `## §2. Task spec` — the bounded task (§5.2 of this shaping doc, verbatim or near-verbatim)
- `## §3. Work`
  - §3.1 Implement `/run-canary` skill (`.claude/skills/run-canary/SKILL.md`)
  - §3.2 Implement canary packet generator (`tests/reliability/canaries/dogfood_v1_packet.py`)
  - §3.3 Implement pass-metric assertion script (`tests/reliability/canaries/dogfood_v1.py`)
  - §3.4 Extend `ops/dashboard.py` with canary fields + sparklines
  - §3.5 Extend event schema (Primitive A) with canary_run_* event types
  - §3.6 Wire conditional hook for material-platform-change trigger
  - §3.7 Install weekly cron in ops lane `/loop` config
  - §3.8 Wire failure-mode issue-filing (canary-slow / canary-fail / canary-silent / canary-schema-drift labels)
  - §3.9 Write quarterly `/canary-review` skill (`§5.4` mitigation) — stub lands Phase 0; full exercise Phase 3+
- `## §4. Phase 0 Readiness` — the H.0 Readiness list from §9.3 above
- `## §5. Phase 1 Validation` — rolls into H.1 full reliability suite; canary continues passing through Phase 1
- `## §6. Pass metrics` — the 9 metrics from §5.3 of this shaping doc
- `## §7. Failure behaviors` — §5.4 of this shaping doc
- `## §8. Cadence` — §5.5 of this shaping doc
- `## §9. Dashboard integration` — §5.6 of this shaping doc
- `## §10. Event schema additions` — §5.7 of this shaping doc
- `## §11. Audit` — quarterly `/canary-review` protocol; operator audits whether recent passes caught known failure modes; if not, add assertions
- `## §12. Verification Plan` — template-mandated section; every §3 Work bullet gets a row
- `## §13. Rollback` — feature flag ENABLE_CANARY_CRON; weekly cron removable; skill disable path
- `## Outcome`
- `## Phase 2 Decision Inputs` (§15.2 schema)

---

## §11. Packet 2b execution spec

Concrete enough that an author lane can execute without additional shaping.

### §11.1 Scope declared (Packet 2b)

**Files created:**
- `plans/steward_platform/verification_contract/sub_plan.md`
- `plans/steward_platform/verification_contract/map.md` (initial ≥90%-coverage skeleton)
- `plans/steward_platform/verification_contract/review_log.md` (empty append-only log)
- `plans/steward_platform/canary_scenarios/dogfood.md`
- `plans/_templates/execution_plan.md`
- `plans/_templates/primitive_closeout.md`
- `.claude/skills/create-plan/SKILL.md`
- `.claude/skills/run-canary/SKILL.md` (stub sufficient to register the skill; full canary impl lives under Primitive H.0 packets)
- `.claude/skills/canary-review/SKILL.md` (stub)
- `scripts/internal/verify_map_coverage.py` (plus `tests/unit/test_verify_map_coverage.py`)

**Files modified:**
- `plans/steward_platform/governing_plan.draft8.md` (or `governing_plan.md` if promotion has happened by Packet 2b dispatch):
  - Insert Pattern 10 into `§10.9` after Pattern 9
  - Split `§5-H` into `§5-H.0` (Phase 0) + `§5-H.1` (Phase 1)
  - Update `§10.7` phase-membership design-coupling note
  - Split `§11-H` kill row into H.0 + H.1 rows
  - Add row to `§12` Risks table (canary silent-green-check)
  - Add SC #21 and SC #22 to `§13`
  - Add `Verification Plan` cross-reference to `§6.4` preflight items table (Surface column or new column)
- `plans/_templates/sub_plan.md` (add `## Verification Plan` section with worked example)
- `scripts/internal/agent_readability_lint.py` (add `check verification-contract` sub-command; if the script doesn't yet exist, Packet 2b creates it — coordinate with Primitive C scaffolding work)
- `scripts/internal/review_driver.py` (add V1–V6 precheck IDs per §3.4; add commit-footer lint per §3.3)
- `.claude/rules/prompt_policy/orchestrator.md` (or whatever path Packet 1 lands) — add §4.1 clause
- `.claude/rules/prompt_policy/author.md` — add §4.2 clause
- `.claude/rules/prompt_policy/analyst.md` — add §4.3 clause
- `.github/pull_request_template.md` — add `## Verification Performed` section if absent

### §11.2 Order of operations (Packet 2b)

1. **Branch + scope lock.** `docs/verification-contract-execution` from `origin/main`.
2. **Governing plan edits first** — land Pattern 10 text, SC #21/#22, H.0/H.1 split, risk row, kill-row split. This gives downstream lint/script/skill work a plan to reference.
3. **Template edits second** — `sub_plan.md`, `execution_plan.md`, `primitive_closeout.md`. These establish the creation-time enforcement surface that subsequent sub-plan authoring uses.
4. **Sub-plan skeletons third** — `verification_contract/sub_plan.md` + `map.md` + `canary_scenarios/dogfood.md`. These use the templates from step 3.
5. **Scripts fourth** — `verify_map_coverage.py` + unit test; extend `agent_readability_lint.py`; extend `review_driver.py` with V1–V6 checks.
6. **Skills fifth** — `/create-plan`, `/run-canary` (stub), `/canary-review` (stub). Skills can be stub-only for Packet 2b; full implementations are H.0 packets.
7. **Prompt-policy clauses sixth** — orchestrator/author/analyst registry entries. Depends on Packet 1 (author-b) having landed the B.3 registry scaffolding; coordinate via orchestrator message if scoped timing collides.
8. **PR template eighth** — add `Verification Performed` section.
9. **Self-run lint ninth** — run `agent_readability_lint.py check verification-contract` against the newly-modified plan; expect clean.
10. **Open PR.** Title: `docs+feat(steward-platform): implement Pattern 10 verification-contract + H.0 dogfood canary scaffolding (Packet 2b)`. Body includes `Verification Performed` with the lint output + unit test output pasted.

### §11.3 Validation commands (Packet 2b Tier 2)

```bash
# Unit
uv run python -m pytest tests/unit/test_verify_map_coverage.py
uv run python -m pytest tests/unit/test_review_driver.py  # V1–V6 cases
uv run python -m pytest tests/unit/test_agent_readability_lint.py  # verification-contract sub-command cases

# Integration
uv run python scripts/internal/verify_map_coverage.py plans/steward_platform/verification_contract/map.md  # expect: coverage >= 90%
uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/  # expect: clean
uv run python scripts/internal/compile_decision_inputs.py  # expect: new sub-plans parse OK

# Negative-path
# Temporarily remove a Verification Plan row from a sub-plan; rerun lint; expect failure; revert
# Temporarily name a fake surface path in map.md; rerun verify_map_coverage; expect failure; revert

# Tier 2
make check-gated
```

### §11.4 Coordination notes (Packet 2b)

- **Dependency on Packet 1 (author-b):** B.3 prompt-policy registry home. If Packet 1 has not landed by Packet 2b dispatch, the author lane defers §11.1 prompt-policy file edits to a follow-up PR (Packet 2c). Signal the orchestrator; do not block on Packet 1.
- **Dependency on `agent_readability_lint.py` existence:** if the base script is not yet in place at Packet 2b dispatch (it is currently enumerated as planned in `rework_spec.md` §4), Packet 2b creates the base script AND the sub-command in one PR. This may push PR scope wider than ideal; the orchestrator may prefer to decompose Packet 2b into Packet 2b.1 (plan + templates + sub-plans) and Packet 2b.2 (scripts + skills + review-driver prechecks).
- **Non-overlap with Packet 1 scope:** Packet 1 (author-b) per orchestrator's current dispatch is plan text + templates + `§15` schema work. Packet 2b's governing-plan edits are §10.9, §13, §12, §5-H, §6.4, §11 — *different* sections from Packet 1. Template edits overlap on `plans/_templates/sub_plan.md`; Packet 2b's edit is *additive* (a new `## Verification Plan` section), which should merge cleanly if Packet 1's edit is also additive. Rebase vigilance required.

### §11.5 Packet 2b success criterion

> Packet 2b is complete when:
> (a) all files in §11.1 are created or modified per spec,
> (b) §11.3 validation commands pass,
> (c) `agent_readability_lint.py check verification-contract` runs clean against the full `plans/steward_platform/` tree,
> (d) the `dogfood-v1` canary stub is registered and runnable via `/run-canary` (does not need to pass yet — full impl is H.0 follow-on packets),
> (e) PR merged with `Verification Performed` evidence in the body.
>
> After Packet 2b merges, H.0 execution packets are dispatched to build out the canary implementation toward the SC #22 "≥4 consecutive weekly passes" gate.

---

## §12. Preflight interaction (§6.4)

The §6.4 preflight checklist has 11 items. Pattern 10 does not add a 12th item; it *sharpens* the existing items' pass criteria by requiring the verification surface to have been named in the originating plan artifact.

Proposed column addition to `§6.4` table (optional — Packet 2b's call):

| # | Surface | Pass criterion | Verification surface cited |
|---|---|---|---|
| (existing columns) | (existing) | (existing) | *(new)* Path to verification surface in plan / sub-plan / map.md; must resolve clean |

Alternative (lighter touch, preferred): add a preamble sentence to §6.4: "Every preflight pass-criterion column entry traces to a verification surface enumerated in `plans/steward_platform/verification_contract/map.md`; an item cannot pass if the underlying surface is un-enumerated."

Packet 2b should pick one; §11.1 lists "Add `Verification Plan` cross-reference to `§6.4`" abstractly — Packet 2b author picks the concrete form.

---

## §13. Self-review against "Step 1 — spawn reviewer agent"

**Constraint encountered.** The task packet (§Step 1) instructs the analyst lane to spawn a reviewer agent via the subagent-spawning `Agent` tool. The analyst-lane YAML frontmatter (in `.claude/agents/steward-analyst.md` system prompt, per this lane's loaded configuration) structurally disallows the `Agent` tool. I cannot spawn a subagent from this lane.

**Substitute applied:** I stress-tested the outline against explicit completeness criteria before writing, and document the self-review here for orchestrator audit:

### §13.1 Completeness criteria stress-test (outline-level)

| Criterion | Check | Outcome |
|---|---|---|
| Every enforcement surface has a failure mode it uniquely catches | §3.1 catalog + coverage analysis | ✓ (table in §3.1 footer) |
| Pattern-10-vs-11 framing decided with explicit rationale | §2.1 decision record | ✓ (Option A adopted; rationale named) |
| H.0 / H.1 bullet assignment complete (no orphan bullets) | §9.2 table | ✓ (7/7 bullets assigned) |
| Canary scenario has ≥6 grep-verifiable pass metrics | §5.3 | ✓ (9 metrics) |
| Canary has ≥3 failure behaviors | §5.4 | ✓ (4: soft / hard / silent / schema-drift) |
| §15.2 Phase 2 Decision Inputs subsection present at end | §14 below | ✓ |
| Packet 2b spec covers scope + order + validation + coordination | §11 | ✓ |
| Sub-plan skeletons spec headers + required sections | §10 | ✓ |
| Deliverable-class → verification-class map enumerated | §2 table + §3.4 V4 row | ✓ |
| Commit-footer trigger paths enumerated | §3.3 | ✓ (10 patterns) |
| Review-driver precheck severity per `60_review_gate.md` | §3.4 | ✓ (V1–V6; BLOCK / WARN / INFO assigned) |
| Risk row mitigations 3+ with concrete enforcement | §7 | ✓ (hash + sparkline + quarterly audit) |
| Prompt-policy clauses per lane with distinct scope | §4 | ✓ (orch / author / analyst distinguished) |
| ADR exemption framing preserves "strict-existence" | §2 ADR note | ✓ (rollback-as-surface framing) |

### §13.2 Risks I surfaced during self-review (orchestrator decision)

1. **Review-driver V3 "surface does not exist" check risks false-positive on surfaces named in-PR but landing in-PR.** Packet 2b should gate V3 to "surface not present in current head AND not added in PR diff."
2. **`agent_readability_lint.py` dependency chain:** Pattern 9 enforcement (load-bearing-ownership) and Pattern 10 enforcement (verification-contract) both live in this script. If either goes down, both degrade. Decomposing into two scripts trades duplication for independence. Recommendation: keep as sub-commands in one script; document the shared dependency as a Pattern 10 Phase 1 Validation concern.
3. **Commit-footer lint has a known false-positive class:** PRs with many small commits may have the verification footer only on the introducing commit; the lint must accept footer on *any* commit in the PR range, not only each commit. §3.3 text already handles this; call out for Packet 2b author.
4. **Canary self-reference:** the dogfood canary modifies `ops/dashboard.py` and the conditional-hook trigger list includes `ops/dashboard.py`. Running the canary could trigger itself recursively. §5.5 trigger list needs an exclusion: the canary's own revert-PR does not re-trigger a new run. Packet 2b implementation must handle.

### §13.3 Orchestrator option

If the orchestrator wants independent adversarial review of this shaping before Packet 2b dispatch, dispatch a separate packet to any flex lane (not the analyst lane, for recusal) with the prompt: "Review `plans/steward_platform/verification_contract/shaping.md` for Pattern 10 enforcement completeness, H.0/H.1 bullet assignment integrity, canary scenario pass-metric adequacy, and Packet 2b spec executability." Recommended but not blocking per the task's Step 1 framing.

---

## §14. Phase 2 Decision Inputs

**Portability readiness:** Pattern 10 is portable-by-design — the deliverable-class → verification-surface map is generic and does not encode Bid-Euchre-specific assumptions; same map works for a second cell. Source: §2 Pattern 10 table contains no Bid-Euchre literals. Evidence: `plans/steward_platform/verification_contract/shaping.md` §2.
**Meta-layer need:** no change. Pattern 10 is per-cell discipline; no meta-surface required. Future cells may share the map structure but each has its own map instance.
**Kill signal for primitive(s) named:** N/A at shaping stage. If Packet 2b lands and the dogfood canary fails to achieve ≥2 weekly passes in any 4-week window, §11-H.0 kill criterion triggers; shaping doc itself does not.
**Re-evaluation needed in Phase 3:** yes if Packet 2b discovers implementation blockers that force Pattern 10 down-scoping (e.g., review-driver precheck integration cost higher than estimated). Re-evaluation window: Phase 3 planning against proving-run evidence of whether Pattern 10 enforcement prevented any observed silent-running-feature incident.
**Surprise finding:** the ADR exemption ("rollback-path-as-surface") preserves strict-existence in a way that reviewers may find subtle. Suggest Packet 2b explicitly call this out in the Pattern 10 final text (§2) so future reviewers don't perceive inconsistency.
**Disposition:** open

---

## §15. References

- `plans/steward_platform/governing_plan.draft8.md` — primary target for Pattern 10 insertion
- `plans/steward_platform/draft8_final_review_handoff.md` — handoff enumerating 8 implementation-tightening findings and separate operator-identified silent-running-feature gap
- `plans/steward_platform/claude_code_changelog_implications.md` — Tier S feature inventory
- `plans/steward_platform/0_hardening/sub/rework_spec.md` — deliverable inventory (ops modules, hooks, scripts, skills)
- `.claude/rules/deferred/60_review_gate.md` — BLOCK / WARN / INFO severity definitions
- `.claude/rules/70_agent_reliability.md` — agent-spawning constraints relevant to §13.1
- `.claude/rules/25_task_lists.md` — task list conventions used for this session
- Task packet: `b3c2cf5c5f74` (Packet 2a)
