# Shaping: Primitive B Phase 0 Execution Spec — Adaptive Dispatch + Prompt-Policy + Tool Risk + Launch + Effort + Recipes + Improvement-Eval

**Date:** 2026-04-24
**Lane:** analyst-a
**Packet:** `7e312ba73ae6` (Primitive B Phase 0 pre-shape — execution belongs to Packet B-exec, dispatchable when shape lands)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-B
**Sibling artifacts:**
- `plans/steward_platform/adrs/006-auto-mode.md` (dual-envelope model + model-tier interaction amendment, PR #2769 merged)
- `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` (keep `ops/task_queue.py` bespoke; lifecycle hooks adopted via Primitive A)
- `plans/steward_platform/adrs/010-mcp-memory-service.md` (rejected wholesale; relevant to B.11 archive design)
- `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` (19-lane → 8-archetype mapping, PR #2768 merged — upstream dependency for B.9a/b)
- `plans/steward_platform/1_primitive_A/shaping.md` (Primitive A event schema v1.0 + `ops/events.py` dispatcher — the emission surface B.1/B.3/B.6/B.10 all route through)
- `plans/steward_platform/verification_contract/shaping.md` (Pattern 10 verification-surface discipline + format exemplar)
- `plans/steward_platform/verification_contract/map.md` (Primitive B coverage rows will be added to this map when shape lands)
- `src/bid_euchre/ops/learning.py` (shadow-mode dispatch advisor, PR #2721 — B.1 extends, does not replace)
- `src/bid_euchre/ops/task_queue.py` (routing metadata contract, PR #2169 Slice C — B.1/B.10 consume)
- Issue #2767 (model-tier-aware permission-mode handling — forward dependency for B.1/B.6)

**Status:** DESIGN-SPEC — no code, policy, or registry files authored in this artifact. Produces a Packet B-exec execution-ready brief. Author-lane picks this up when the Phase 0 kickoff gate passes and dispatches directly from §10 without further analyst shaping.

**Purpose:** Pre-shape Primitive B's seven Phase 0 sub-deliverables (B.1, B.3, B.6, B.9b, B.10, B.11, B.12) so the orchestrator can dispatch B-exec to an author lane as soon as the Phase 0 kickoff gate passes — zero additional shaping required. Mirrors the Packet 2a → Packet 2b pattern (verification contract shaping → execution) that proved out on session 2026-04-23, and the Primitive A pre-shape pattern (PR #2771). Primitive B differs from A in breadth (seven distinct deliverables vs. one schema + dispatcher) — this shape is therefore more of an **orchestration contract** than a single module spec: it names the seven deliverables, their integration seams, their verification surfaces, and the order in which Packet B-exec (or a decomposed B.1-exec / B.2-exec family) executes them.

---

## §1. Scope of this document

This is a **shaping document**, not a sub-plan, ADR, or governing-plan
edit. Its single output is an execution-ready specification for the
seven Primitive B Phase 0 sub-deliverables enumerated in
`governing_plan.md` §5-B (Work + Phase 0 Readiness + Phase 1 Validation),
tightened by ADR 006 (dual-envelope safety model), ADR B8 (native task
system evaluation), the G13 archetype mapping, and Pattern 10 (every
deliverable carries a verification surface).

**What this document specifies:**

1. The integration contract for B.1 adaptive dispatch (how the existing
   shadow-mode advisor in `ops/learning.py` extends to consume model-tier
   + safety-envelope metadata; the `.claude/lane_models.json` forward
   dependency from #2767; the event-emission path through
   `ops/events.py` once Primitive A lands).
2. The B.3 prompt-policy registry spec (how the 4-file scaffold at
   `.claude/rules/prompt_policy/` becomes a versioned, assembleable,
   lint-checked registry; lifecycle; integration with
   `.claude/system_prompts/` from B.9a).
3. The B.6 tool risk registry spec (`.claude/rules/tool_risk_registry.md`
   — four approval classes; dual-envelope classification per ADR 006;
   emission via A's `permission_denied` event type).
4. The B.9b fleet launch adoption spec (tmux launch-script contract for
   `--system-prompt-file`; rollout order; rollback; dependency on B.9a).
5. The B.10 effort-level configuration spec (per-archetype + per-task-type
   defaults; resolution path at dispatch time; override protocol).
6. The B.11 orchestration recipe archive spec (`knowledge/orchestration_recipes/`
   layout; worked-example entry; archivist integration point).
7. The B.12 improvement-mechanism evaluation spec
   (`scripts/internal/measure_improvements.py` design; metric set; output
   path; cadence).
8. The Packet B-exec execution spec (files created, modified, order of
   operations, validation commands, coordination notes, success
   criterion).
9. Self-review against completeness criteria.
10. Phase 2 Decision Inputs (§15.2 schema).
11. Verification Plan (Pattern 10 mandate).

**What this document does NOT do:**

- Author any code, policy, or registry file. Packet B-exec implements;
  this shapes.
- Modify governing plan text. §5-B is the governing reference; this
  document consumes it.
- Shape B.2 (skill promotion loop), B.4 (prompt-policy change discipline),
  B.5 (routing rules encoding), B.7 (approval-class references), B.8
  (native task ADR, already filed), or B.9a (per-archetype system-prompt
  files — Packet 5 / analyst-d scope). These are explicitly out of scope
  for this packet per §5-B § "Sub-deliverables table" partition and the
  task packet's enumerated list.
- Re-litigate ADR 006 decisions (dual-envelope model; Opus-only auto
  mode; launch-flag selection per tier). Those are merged (PR #2769).
- Re-litigate ADR B8 decisions (keep `ops/task_queue.py` bespoke; adopt
  lifecycle hooks + SendMessage as supplemental). Those are merged.
- Author the G13 lane-model config (`.claude/lane_models.json`) — that
  is Primitive G Phase 0 scope, owned by Packet 2 (#2767 fix) on author-c.
  This document names it as a forward dependency and specs the B.1 read
  contract against it.
- Author the `.claude/system_prompts/<archetype>.md` files — that is
  B.9a scope, owned by Packet 5 on analyst-d. This document shapes
  B.9b (fleet launch adoption) with a placeholder for the B.9a file
  layout that fills in when B.9a lands.

### §1.1 Motivation (one paragraph)

Primitive B is the **policy-layer counterpart** to Primitive A's
observability layer: A provides the event stream; B defines the
*decisions* (dispatch routing, prompt composition, tool approval,
effort selection) that get emitted into that stream. Every Phase 0
decision made under B — every dispatch choice, every prompt-policy
version pinned, every tool invocation gated — must be *visible* in
the event record so the proving run can evaluate whether the decisions
were sound. The cascade-risk framing from §12 places A at the root
("A slip cascades to D, E, H"); B sits one layer out ("B slip cascades
to proving-run decision quality, observable only after decisions are
made and outcomes land"). Pre-shaping B means that when ADR 001 files,
ADR 006 is amended (already done via #2769), the G10 ADR for
`.claude/system_prompts/` vs. `.claude/agents/` files, and Primitive A's
Packet 3 lands, Packet B-exec can dispatch immediately with the seven
deliverable seams already specified. Without pre-shaping, B's
integration surface (six-way: A events, G13 archetypes, B.9a prompts,
lane_models.json, task_queue routing metadata, existing `ops/learning.py`
advisor) would force an analyst-lane turnaround at Phase 0 kickoff
time, compressing the Phase 0 timeline. This shape absorbs that
turnaround work now.

### §1.2 Relationship to upstream ADRs and merged work

Four merged artifacts bind this shape:

| Upstream artifact | Decision this shape inherits | Where it lands in this doc |
|---|---|---|
| ADR 006 (amended via PR #2769) | Opus-only auto mode; Sonnet/Haiku lanes use `--dangerously-skip-permissions`; tools evaluated against BOTH envelopes; routing-decisions that lower model tier simultaneously lower safety envelope and must be flagged | §3.2 (B.1 safety-envelope awareness); §5.2 (B.6 dual-envelope classification) |
| ADR B8 | Keep `ops/task_queue.py` bespoke; adopt lifecycle hooks as supplemental; native task schema not yet scope-locked or durable | §3.1 (B.1 extends existing advisor, not replaces; task_queue routing metadata contract stays bespoke) |
| G13 archetype mapping (PR #2768) | 19 lanes → 8 archetypes (orchestrator / ops / review / analyst / author / brws-author / flex / scratch); per-archetype model-tier + effort-tier hints | §6 (B.9b fleet launch reads archetype at launch time); §7 (B.10 effort defaults are per-archetype × per-task-type) |
| `ops/learning.py` shadow-mode advisor (PR #2721) | Shadow-mode advisor landed with `recommend_lanes()` pure-function guarantee; ADVISOR_MODE ∈ {"shadow", "disabled"}; POLICY_VERSION = "slice-e-v1"; SCORE_WEIGHTS on clean-rate / token-efficiency / cycle-time / rework-penalty | §3.1 (B.1 extends `recommend_lanes()` with model-tier + safety-envelope gate; advances POLICY_VERSION to `"b1-v1"` when the safety-envelope gate is enforced, not merely observed) |

Three forward dependencies exist (not yet merged as of this shaping):

| Forward dependency | State | Resolution path |
|---|---|---|
| `.claude/lane_models.json` — per-lane declared model tier | Not yet created; Packet 2 / #2767 fix on author-c | B.1 reads from this file at dispatch time; if file missing, B.1 falls back to conservative default "opus" for unknown lanes and emits a `dispatch_recommendation` warning |
| `.claude/system_prompts/<archetype>.md` — 8 archetype prompt files | Not yet created; Packet 5 / B.9a on analyst-d | B.9b launch adoption shapes the `--system-prompt-file` wiring against an 8-element archetype list; file paths fill in when B.9a lands; B.9b execution waits for B.9a merge before running |
| G10 ADR — relationship between `.claude/system_prompts/` and `.claude/agents/` | Not yet filed (default assumption: orthogonal) | B.9b's fleet launch spec assumes *orthogonal* (both persist, describing different things: system_prompts for per-launch system-prompt override, agents for Agent-tool-loaded subagent behavior). If G10 ADR picks replacement or supplement, B.9b reconciles at execution time by updating the launch-script wiring |

---

## §2. Deliverable → Pattern-10 verification-surface table

Per `governing_plan.md` §10.9 Pattern 10 and `verification_contract/shaping.md`
§2, every deliverable names a verification surface using the default
table's surface classes. Lenient-form where the deliverable class
deviates from runtime Python code.

| Deliverable | Deliverable class | Verification surface | Acceptance condition | §N.M in this doc |
|---|---|---|---|---|
| **B.1 Adaptive dispatch** | Module extension under `src/bid_euchre/ops/**` | **Unit test:** `tests/unit/test_ops_learning_model_aware.py` + **event-schema query:** grep in `data/events/events-*.jsonl` for `dispatch_recommendation` event type with `safety_envelope` field populated | `recommend_lanes()` accepts `required_safety_envelope` kwarg; filters out lanes whose declared tier cannot satisfy; emits `dispatch_recommendation` event carrying the envelope and the filtered-vs-kept lane list | §3 |
| **B.3 Prompt-policy registry** | `.claude/rules/**` structural extension | **Operator-readable review prompt** embedded in each policy file; **lint:** `scripts/internal/agent_readability_lint.py check prompt-policy` (new sub-command) passes clean over the 4-file scaffold + any per-archetype additions | Every `.md` file under `.claude/rules/prompt_policy/` contains: `## Version` header, `## Trigger`, `## Expected effect`, `## Rollback`; registry version cited in ≥90% of proving-run traces (Phase 1 target per §5-B) | §4 |
| **B.6 Tool risk registry** | New `.claude/rules/**` file | **Operator-readable review prompt** embedded + **structural test:** `tests/unit/test_tool_risk_registry.py` asserts every tool used by any lane has a registry row + every row has both envelopes classified | `.claude/rules/tool_risk_registry.md` exists; covers ≥all tools in the `permissions.allow` set; four approval classes {direct, approve, edit, reject} populated; dual-envelope columns populated | §5 |
| **B.9b Fleet launch adoption** | `.claude/tmux/steward-session.sh` config edit + runtime observable | **Rollback test:** `tests/unit/test_steward_session_launch.py::test_system_prompt_file_revertable` + **event-schema query:** every `session_start` event in the proving run carries `system_prompt_file` field populated with an archetype path | Launch script reads archetype from G13 mapping; passes `--system-prompt-file .claude/system_prompts/<archetype>.md`; revert-commit smoke confirms rollback path < 1 session restart | §6 |
| **B.10 Effort-level configuration** | New `.claude/rules/**` file + dispatch-path integration | **Unit test:** `tests/unit/test_effort_policy.py` + **commit-footer citation:** B.1 dispatch emissions include `effort_hint_source: <policy-version>` tracing to `.claude/rules/effort_policy.md` | Policy file exists; resolution at dispatch time is single-call; override protocol documented; `effort_hint_source` field appears in ≥80% of `dispatch_recommendation` emissions during the proving run | §7 |
| **B.11 Orchestration recipe archive** | New `knowledge/**` subdirectory | **KB `INDEX.md` inclusion** + **lint:** `agent_readability_lint.py check recipes` (new sub-command) enforces schema conformance (context → decision → outcome); **worked-example smoke:** at least one recipe entry committed at Phase 0 close | `knowledge/orchestration_recipes/` exists; `knowledge/INDEX.md` references it; ≥1 worked example committed (e.g., the shape-then-execute Pattern 11 recipe itself) | §8 |
| **B.12 Improvement-mechanism evaluation** | New Python script under `scripts/internal/**` | **Unit test:** `tests/unit/test_measure_improvements.py` + **named runnable command:** `uv run python scripts/internal/measure_improvements.py --since <date>` produces `knowledge/_candidates/<date>_improvement_metrics.md` with all five metrics | Script exists; scheduled weekly (cron or skill); output file has metric deltas for retry-rate / author-rework-rate / routing-correction-rate / prompt-policy-rollback-rate / skill-promotion-usefulness-rate; operator review step documented | §9 |

**Cross-coverage with `verification_contract/map.md`.** Primitive B's
coverage rows are NOT currently in the map (map was authored for
Primitives A + H.0 Pattern 10 validation; B was deferred). Packet
B-exec adds seven rows to `verification_contract/map.md` (one per
deliverable above) and runs `uv run python scripts/internal/verify_map_coverage.py`
to confirm 100% coverage. If map coverage exceeds the 90% threshold
cited in the packet Validation field but falls short of 100%,
orchestrator reviews the gap before declaring Phase 0 Readiness
(per the packet's Validation: "≥90% otherwise").

### §2.1 Lint cross-walk

The agent_readability_lint.py sub-commands referenced in §2 acceptance
conditions are three new extensions:

| Sub-command | Scope | Behavior |
|---|---|---|
| `check prompt-policy` | `.claude/rules/prompt_policy/**/*.md` | Every file has `## Version`, `## Trigger`, `## Expected effect`, `## Rollback` headers; version format is monotonic semver-ish (e.g., `b3-v1.0`); orphan references detected |
| `check tool-risk` | `.claude/rules/tool_risk_registry.md` | All rows have both envelope columns populated (no `TBD`); approval class is one of `{direct, approve, edit, reject}`; tools referenced elsewhere (e.g., in `permissions.allow`) have a row |
| `check recipes` | `knowledge/orchestration_recipes/**/*.md` | Each file has `## Context`, `## Decision`, `## Observed outcome` sections; INDEX.md references the file; no orphan recipes |

Primitive C owns `agent_readability_lint.py` (per `governing_plan.md`
§5-C work bullet). Packet B-exec *extends* that script with three
sub-commands; it does not author the base lint framework. If
`agent_readability_lint.py` does not yet exist when Packet B-exec
dispatches, the sub-commands ship as standalone checker scripts under
`scripts/internal/` with a TODO to fold into the unified lint once C's
base framework lands (same fallback Packet 3 / Packet 2b used).

---

## §3. B.1 Adaptive dispatch design

### §3.1 Integration seam — extend `ops/learning.py`, do not replace

Per ADR B8 (keep `ops/task_queue.py` bespoke) and the PR #2721 Slice E
charter (shadow-mode advisor), B.1 **extends** the existing
`recommend_lanes()` function in `src/bid_euchre/ops/learning.py` rather
than creating a parallel dispatcher. The existing advisor is pure
(no file writes, no event emission; file writes happen only via
`log_recommendation_for_dispatch()`), preserves ADVISOR_MODE ∈
{"shadow", "disabled"}, and is already wired through `ops/dispatcher.py`
as a side-effect-free recommendation source that the orchestrator may
or may not consult.

**B.1 extension scope:**

1. Add two new kwargs to `recommend_lanes()`:
   - `required_safety_envelope: Literal["auto-mode", "bypass", "any"] = "any"`
   - `required_model_tier: Literal["opus", "sonnet", "haiku", "any"] = "any"`
2. Add pre-filter step: before scoring, drop any candidate lane whose
   declared model tier (read from `.claude/lane_models.json`) fails to
   satisfy the `required_model_tier` or whose safety envelope fails to
   satisfy `required_safety_envelope` (per the ADR 006 §Model-tier
   interaction table). Filtered-out lanes are retained in the emission
   payload as `filtered_lanes: list[{lane, reason}]` for observability.
3. Add three new scoring inputs (WEIGHT adjustable via `SCORE_WEIGHTS`):
   - `model_tier_match` — +1.0 if lane tier matches caller's
     `required_model_tier` preference strictly; +0.5 if "any" and lane
     is opus; 0 otherwise.
   - `effort_match` — +1.0 if lane's per-archetype effort tier (from
     §7 B.10 policy) matches the packet's resolved effort hint.
   - `safety_envelope_penalty` — −2.0 if the caller requests
     "bypass"-tier lane for a task whose tool-risk-registry class
     (§5) is `reject` under `bypass`. Hard-filter equivalent but
     phrased as a large penalty for audit clarity.
4. Extend `log_recommendation_for_dispatch()` to emit the same
   `dispatch_recommendation` event type with three new top-level fields:
   `required_safety_envelope`, `required_model_tier`, `filtered_lanes`.

**Preserved invariants (do not break):**

- `recommend_lanes()` remains pure (no I/O, no event emission).
- `log_recommendation_for_dispatch()` emits exactly one
  `dispatch_recommendation` event per call (Pattern 8 emission
  discipline).
- ADVISOR_MODE stays `"shadow"` until Phase 0 advisor-quality review
  (per §5-B B.1 Phase 1 Validation: "≥80% operator approval if
  audited"). Promotion to ADVISOR_MODE = "enforce" is a Phase 1
  decision, not a Phase 0 scope expansion.
- POLICY_VERSION advances from `"slice-e-v1"` to `"b1-v1"` when B.1
  filter logic lands — the version change is the trace signature
  operators look for to confirm B.1 is live.

### §3.2 Safety-envelope awareness (per ADR 006 amendment)

Per ADR 006 §"Model tier interaction" (PR #2769 amendment):

- Opus lanes run `--permission-mode auto` → classifier-gated "auto-mode"
  envelope (soft-denies destructive actions without explicit User
  Intent).
- Sonnet/Haiku lanes run `--dangerously-skip-permissions` → "bypass"
  envelope (no classifier gate; git audit trail + post-merge review
  only).

**B.1 consequences:**

1. Every dispatch decision reads the candidate lane's declared model
   tier from `.claude/lane_models.json` (Packet 2 / #2767 forward
   dependency).
2. The caller (orchestrator) passes `required_safety_envelope` based
   on the task's tool-risk classification (B.6). Default:
   `required_safety_envelope = "any"` (B.1 honors whatever tier the
   lane declares; the caller accepts the resulting envelope).
3. If the caller explicitly requests `"auto-mode"`, B.1 filters out
   any lane whose declared tier is non-Opus. The filtered-lanes list
   surfaces this to the event stream (Pattern 8 emission).
4. If the caller requests `"bypass"` for a task whose tool-risk class
   is `reject-under-bypass` (§5.2), B.1 emits a warning and refuses to
   recommend any lane. The orchestrator must either upgrade the task
   to an Opus lane (auto-mode envelope) or explicitly override via
   operator-approved user intent recorded in the dispatch emission.
5. `dispatch_recommendation` event payload includes:
   ```json
   {
     "event_type": "dispatch_recommendation",
     "required_safety_envelope": "auto-mode | bypass | any",
     "required_model_tier": "opus | sonnet | haiku | any",
     "candidate_lanes": [...],
     "filtered_lanes": [{"lane": "<id>", "reason": "tier-mismatch | envelope-mismatch | risk-reject"}],
     "recommended_lane": "<id> | null",
     "policy_version": "b1-v1",
     ...
   }
   ```

### §3.3 `.claude/lane_models.json` read contract

The file is **not authored** by Packet B-exec. It is authored by
Packet 2 / #2767 fix on author-c. B.1 specs the read contract:

```json
{
  "orchestrator":   {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "orchestrator"},
  "ops":            {"model": "sonnet", "safety_envelope": "bypass",    "archetype": "ops"},
  "review":         {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "review"},
  "analyst-a":      {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "analyst"},
  "analyst-b":      {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "analyst"},
  "analyst-c":      {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "analyst"},
  "analyst-d":      {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "analyst"},
  "author-a":       {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "author"},
  "author-b":       {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "author"},
  "author-c":       {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "author"},
  "author-d":       {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "author"},
  "brws-author-a":  {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "brws-author"},
  "brws-author-b":  {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "brws-author"},
  "brws-author-c":  {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "brws-author"},
  "brws-author-d":  {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "brws-author"},
  "flex-a":         {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "flex"},
  "flex-b":         {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "flex"},
  "flex-c":         {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "flex"},
  "flex-d":         {"model": "opus",   "safety_envelope": "auto-mode", "archetype": "flex"}
}
```

**Read-contract invariants (B.1 must assert):**

- File exists at `.claude/lane_models.json`; if missing, B.1 falls
  back to conservative default (`{"model": "opus", "safety_envelope":
  "auto-mode"}` for any unknown lane) and emits a
  `dispatch_recommendation` warning with `warnings: ["lane_models.json
  missing; using conservative fallback"]`.
- Every lane in `get_known_lanes()` (from `ops/task_queue.py`) has a
  row in `lane_models.json`; coverage is asserted in the B.1 unit
  test.
- The four enum values are fixed: `model ∈ {opus, sonnet, haiku}`;
  `safety_envelope ∈ {auto-mode, bypass}`. Unknown values fail the
  B.1 unit test hard — the config is load-bearing enough that
  typos should not silently degrade dispatch.

### §3.4 Event emission path

Per Primitive A shaping §2.3 (§9.7 first-class IDs as top-level) and
§2.5 (event-type registry), `dispatch_recommendation` is a steward-
additive event type registered in A's v1.0 catalog. B.1 emits
through `from bid_euchre.ops.events import emit` once A's Packet 3
lands. Until Packet 3 lands, B.1's `log_recommendation_for_dispatch()`
retains its current fallback path (write to
`data/events/dispatch_recommendations.jsonl` directly). B.1 unit
test covers both code paths (a conditional import of `events.emit`
with a fallback to the pre-Primitive-A writer).

### §3.5 Escalation class: destructive tools on non-Opus lanes

Per ADR 006 §"Practical consequences for B.1 adaptive dispatch":

> Destructive tool classes should refuse non-Opus routing absent
> operator override.

B.1 consumes the §5 B.6 tool-risk registry to determine which tool
classes are destructive. The escalation logic:

1. Orchestrator builds a task packet with routing metadata
   `{"task_type": "refactor", "required_tools": ["Bash(rm *)",
   "Bash(git push --force *)"]}`.
2. B.1 queries the tool-risk registry for each required tool's
   `approval_class_under_bypass`.
3. Any tool with `approval_class_under_bypass = "reject"` forces
   `required_safety_envelope = "auto-mode"` (overriding whatever the
   caller passed).
4. B.1 emits `dispatch_recommendation` with `safety_envelope_override:
   true` and `override_reason: "tool-risk-rejected-under-bypass"`.
5. If no auto-mode lane is available, B.1 refuses to recommend. The
   orchestrator escalates to the operator rather than silently
   dispatching to a bypass-tier lane for a reject-under-bypass task.

**Rationale (preserves ADR 006 strictness):** B.1 cannot allow the
caller to downgrade the safety envelope for a task whose tool-risk
profile requires the stronger envelope. Routing decisions lowering
tier simultaneously lower envelope, which is a decision the
orchestrator-as-caller must explicitly request and record —
never a B.1 default.

### §3.6 Advisor-quality feedback loop (forward-dep to B.10 + B.12)

B.1's `clean_rate` / `rework_penalty` score inputs rely on downstream
lane-performance data. The existing advisor derives these from the
task-queue lifecycle (`task_completed` outcome). B.1 extends with
three new signals fed back by B.10 (effort hint override rate) and
B.12 (mechanism-change improvement metric):

- `effort_override_rate` — per-archetype rate at which operators
  override the B.1-recommended effort hint. High override = B.1
  effort-match score should weight lower.
- `routing_correction_rate` — per-archetype rate at which operators
  override B.1's lane recommendation (recorded as a
  `dispatch_override` event, a new steward-additive event type).
- `skill_promotion_usefulness` — whether skills promoted via B.2
  (out of scope for B.1 Phase 0 but feeds in Phase 1) reduce retry
  rate on subsequent dispatches.

**Scope lock:** Phase 0 B.1 implements the score-input plumbing
(adds the three kwargs, filters, emits); the *feedback-learning*
loop that updates `SCORE_WEIGHTS` based on these signals is a
Phase 1 deliverable (§5-B B.1 Phase 1 Validation). Phase 0 ships
the plumbing; Phase 1 proves it learns.

---

## §4. B.3 Prompt-policy registry

### §4.1 Current state — 4-file scaffold (landed)

PR #2762 landed the scaffold:

- `.claude/rules/prompt_policy/orchestrator.md` (Pattern 10 Verification-surface-at-packet-shape clause)
- `.claude/rules/prompt_policy/author.md` (Pattern 10 Verification-surface-at-slice-close clause + Pattern 11 Shape-is-authoritative clause)
- `.claude/rules/prompt_policy/analyst.md` (Pattern 10 Verification-surface-at-shaping clause + Pattern 11 reference)
- `.claude/rules/prompt_policy/common.md` (Pattern 10 supplementary for ops + review)

The scaffold currently contains only Pattern 10 + Pattern 11 clauses.
B.3 extends the scaffold into a versioned, assembleable, lint-checked
*registry* — that is, the files become the authoritative assembly
input for per-lane system prompts at session launch time (via B.9a/b)
and for Agent-tool-loaded subagents (via the G10 orthogonal pathway).

### §4.2 Per-file schema extension

Every file under `.claude/rules/prompt_policy/**/*.md` must add the
following required sections (B.3 Phase 0 Readiness per §5-B:
"versioned; rollback via version pin"):

```markdown
## Version

`<archetype>-v<MAJOR>.<MINOR>` (e.g., `author-v1.0`)

## Trigger

<When this policy version landed — commit SHA + ADR/incident reference.>

## Expected effect

<Observable behavior change this policy is meant to produce.>

## Rollback

<Single-command rollback: `git revert <SHA>` with documentation of
 the trace-signature that confirms rollback (e.g., "prompt_policy_version
 field in dispatch_recommendation events reverts to `<prior version>`").>

## Policy clauses

<Existing Pattern 10 / Pattern 11 content here; any additional clauses
 specific to this archetype.>
```

**Rationale:** §5-B B.4 (prompt-policy change discipline) mandates a
commit-message template with trigger / expected-effect / rollback
fields. Moving those fields into the policy file itself (rather than
only the commit message) makes them greppable as persistent records
and makes the lint (§2.1 `check prompt-policy`) a file-level rather
than commit-history assertion.

### §4.3 Registry assembly mechanism

The registry is a *virtual* assembly: at session launch time, the
tmux launch script (§6 B.9b scope) reads the relevant policy files
and passes them via `--system-prompt-file`. Assembly rules:

| Lane | Policy files loaded (in order) |
|---|---|
| orchestrator | `common.md` + `orchestrator.md` |
| ops | `common.md` |
| review | `common.md` |
| analyst-* | `common.md` + `analyst.md` |
| author-* | `common.md` + `author.md` |
| brws-author-* | `common.md` + `author.md` (initially; may diverge when B.9a files land for brws-author archetype) |
| flex-* | `common.md` + `author.md` + `analyst.md` (flex archetype crosses both; final choice bounded at B.9a shaping time) |

**Invariant-vs-variant split (per governing plan §16 agent-first discipline):**

- `common.md` carries invariant content — Pattern 10 + Pattern 11
  observer clauses, event-schema awareness, general escalation
  protocol.
- Per-archetype files carry variant content — lane-specific
  responsibilities, tool restrictions, handoff conventions.
- Drift between invariant and variant is a Pattern 9 (load-bearing
  ownership) violation: if a clause appears in both `common.md` and
  an archetype file and they disagree, lint flags it. Reconciliation
  is per-archetype: the archetype file wins (variant overrides
  invariant) but the conflict is explicit in the lint report.

### §4.4 Integration with `.claude/system_prompts/` (B.9a)

Per G10 ADR default assumption (orthogonal) and §5-B B.9a readiness:

- `.claude/system_prompts/<archetype>.md` files (authored by Packet 5
  / B.9a on analyst-d) are the **per-launch system-prompt override**
  payload. These are the files `--system-prompt-file` consumes.
- `.claude/rules/prompt_policy/<archetype>.md` files are the
  **policy clauses** that get *assembled into* the system-prompt
  files at author time (B.9a renders the policy clauses into the
  system-prompt bodies).
- The assembly is a compile-time (author-time) operation, not a
  runtime concatenation: B.9a's file content *includes* the policy
  clauses verbatim (or by reference with a marker that the lint
  verifies). This means the system-prompt file is self-contained
  at launch time.

**Relationship to `.claude/agents/<lane>.md`:** Per G10 default
(orthogonal), the agents-file is a distinct artifact describing the
Agent-tool-loaded subagent behavior. B.3 does not author, modify, or
reference `.claude/agents/**` — that is B.9a scope. If G10 ADR picks
replacement or supplement, B.3's lint extends to check agents-file
consistency; orthogonal makes this unnecessary.

### §4.5 Version pin + rollback

Every policy file declares a version in its `## Version` header. The
version is the rollback unit:

- Pin: dispatch emissions read the version at session start, cache
  for session duration, emit in every `dispatch_recommendation` event
  as `prompt_policy_version: "<lane>-<ver>"`.
- Rollback: `git revert <SHA of policy change commit>`; the next
  session-start event emits the prior version. The rollback path is
  single-commit — no migration, no data transform.
- Lint enforces monotonic version bumps (can't revert version
  number without the corresponding file rollback).

### §4.6 Lint scope (`agent_readability_lint.py check prompt-policy`)

**Assertions:**

1. Every file under `.claude/rules/prompt_policy/**/*.md` has all
   four required sections (`## Version`, `## Trigger`, `## Expected
   effect`, `## Rollback`).
2. Version format matches `^<archetype>-v\d+\.\d+$`.
3. Version is monotonically non-decreasing vs. prior commit (git-log
   cross-check).
4. No content overlap between `common.md` and per-archetype files
   (if a clause appears in both, they must be identical; otherwise
   lint flags drift).
5. Every clause references its §N.M source in `verification_contract/`
   or `governing_plan.md` (so clauses are traceable to their
   authoritative decision record).

**Scope exclusion:** the lint does NOT enforce content correctness
(operator owns). It enforces structural conformance.

---

## §5. B.6 Tool risk registry

### §5.1 Home + shape

Per §5-B B.6 Phase 0 Readiness: `.claude/rules/tool_risk_registry.md`
committed; mapped to four approval classes `{direct, approve, edit,
reject}` per task type.

**File shape:**

```markdown
# Tool Risk Registry

> Dual-envelope classification for every tool steward lanes may invoke.
> Per ADR 006, every tool is evaluated against BOTH the auto-mode
> classifier envelope AND the bypassPermissions envelope. Approval
> class may differ between envelopes; the registry captures both.

## Approval classes

- `direct` — tool executes without prompt; no operator involvement.
- `approve` — tool executes after classifier approval (auto-mode only)
   or human confirmation (bypass only); single-call gate.
- `edit` — tool output requires human/classifier review before
   downstream consumption (e.g., large-scope diff in a PR).
- `reject` — tool is not allowed under this envelope; dispatch
  refuses any lane whose envelope matches.

## Registry

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Read` | direct | direct | — |
| `Write(<repo paths>)` | direct | direct | — |
| `Write(~/.claude/**)` | approve (classifier gates; requires User Intent) | reject | Self-modification |
| `Edit(<repo paths>)` | direct | direct | — |
| `Bash(ls *)` | direct | direct | — |
| `Bash(git status|diff|log *)` | direct | direct | — |
| `Bash(git push)` | direct (to working branch only) | direct | — |
| `Bash(git push --force)` | approve | reject | Destructive |
| `Bash(git reset --hard)` | approve | reject | Destructive — local work loss |
| `Bash(rm *)` | approve | reject | Destructive — data loss |
| `Bash(curl * | bash)` | reject | reject | Exfil + arbitrary exec |
| `Bash(gh pr merge)` | approve | reject | State change — merge guard applies |
| `Bash(gh pr create)` | direct | direct | — |
| `WebFetch`, `WebSearch` | direct | direct | — |
| `mcp__github__*` (read-only) | direct | direct | — |
| `mcp__github__push_files`, `create_repository`, `delete_file` | approve | reject | State change |
| `Bash(uv run python scripts/internal/*)` | direct | direct | Blessed tooling |
| `Bash(make *)` | direct | direct | — |
| `Bash(render *)` | approve | reject | Production surface |
| `Bash(tmux send-keys -t <lane>)` | approve | approve | Orchestrator-only |
| ... | ... | ... | ... |
```

### §5.2 Dual-envelope classification discipline

The registry exists to *make the difference explicit*. Per ADR 006:

- An `approve` / `approve` row is a tool whose runtime gate is *the
  same substance* under both envelopes (classifier under auto-mode;
  operator under bypass); the difference is only the gate-operator
  identity (classifier vs. human).
- An `approve` / `reject` row is a tool whose runtime gate is
  *materially weaker* under bypass because no classifier exists;
  B.1 (§3.5) refuses to route the task to a bypass lane absent
  operator override.
- A `reject` / `reject` row is a tool never allowed in the fleet;
  used for exfiltrating, destructive, or arbitrary-execution patterns
  that have no sanctioned use.
- A `direct` / `direct` row is a tool whose impact is bounded and
  reversible under both envelopes (reads, blessed tooling, local
  file edits).

**Lint enforcement (`check tool-risk` per §2.1):**

1. Every row has both envelope columns populated (no `TBD`).
2. Every `approval_class_under_bypass = "reject"` row has an
   accompanying `Notes` column entry explaining why (destructive,
   exfil, etc.).
3. Every tool cited in `permissions.allow` (.claude/settings.json)
   has a row.
4. Every tool that appears in a `PermissionDenied` event in the last
   7 days of `data/events/events-*.jsonl` (once Primitive A is live)
   has a row. Missing rows are flagged as triage items.

### §5.3 Runtime consumption

Two runtime consumption paths:

| Consumer | Read-timing | Cache policy | Behavior |
|---|---|---|---|
| **B.1 adaptive dispatch** (§3.5 escalation class) | At dispatch-time, per task | No cache — read per dispatch | Filter out lanes whose envelope fails required tools |
| **Classifier / permission hook** | At tool-invocation time, per call | Cached per session | Reference for "is this tool in class X under envelope Y" — advisory only; auto-mode classifier has its own policy, this is complementary |

The registry is **documentation, not a runtime policy** (per §5-B
combined note: "The tool risk registry documents, does not replace,
the existing auto-mode classifier at `.claude/rules/80_permission_model.md`").
B.1 *consumes* it for dispatch filtering, but the classifier itself
retains authority over runtime tool-invocation gating.

### §5.4 Emission via Primitive A

When the classifier soft-denies a tool call, a `permission_denied`
event fires (per A §2.2 entry 5). B.6 enriches this event with three
new fields per ADR 006 integration:

| Field | Source | Purpose |
|---|---|---|
| `approval_class_auto_mode` | Registry lookup | What the registry says the auto-mode gate is |
| `approval_class_bypass` | Registry lookup | What the registry says the bypass gate is |
| `registry_row_id` | Registry lookup | Path to the row (file + line number) |

Enrichment happens in the `.claude/hooks/permission-denied-log.sh`
hook (existing script; extended by Packet B-exec). If the tool has
no registry row, the hook sets all three fields to `null` and emits
a `registry_coverage_gap` warning event — this drives the lint's
triage-item detection in §5.2 item 4.

### §5.5 Relationship to `.claude/rules/80_permission_model.md`

The existing permission-model rule is the *operational guide* to
auto mode; the tool-risk registry is the *cross-envelope
classification table*. They coexist:

- `80_permission_model.md` documents *why* auto mode is the chosen
  default, how the classifier behaves, what `PermissionDenied` means,
  operator guidelines.
- `tool_risk_registry.md` documents *what classification* each tool
  has under each envelope, and is load-bearing for B.1 dispatch
  decisions and B.6 lint.

Cross-reference: `80_permission_model.md` gains a § "Tool-risk registry"
subsection pointing to `tool_risk_registry.md`; the registry file
opens with a back-pointer to `80_permission_model.md`.

---

## §6. B.9b Fleet launch adoption of `--system-prompt-file`

### §6.1 Dependency on B.9a (forward)

Per §5-B B.9b: "**Upstream gate:** B.9a complete (files must exist
before launch can reference them)". B.9a is Packet 5 on analyst-d;
if Packet 5 has not produced `.claude/system_prompts/<archetype>.md`
files at Packet B-exec dispatch time, B.9b execution *waits* — the
orchestrator decomposes Packet B-exec into {B.9b-excluded} + {B.9b
standalone pending B.9a}.

**B.9b scope lock (dependency-respecting):** if B.9a files do not
exist, Packet B-exec *drafts* the tmux launch-script extension
against the 8-archetype list (from G13 mapping) but does not enable
it — the script edit stays behind a feature flag until B.9a files
land and lint passes. This prevents the "launch references non-
existent file" failure mode.

### §6.2 Launch-script contract

`.claude/tmux/steward-session.sh` is extended to read the archetype
for each lane and pass `--system-prompt-file .claude/system_prompts/
<archetype>.md` alongside the existing `--permission-mode auto` /
`--dangerously-skip-permissions` flag selection (per ADR 006 amendment
and #2767 fix on author-c).

**Integration pattern:**

```bash
# Existing (post-#2767 fix):
case "${lane_model}" in
  opus)   PERM_FLAG="--permission-mode auto" ;;
  sonnet|haiku) PERM_FLAG="--dangerously-skip-permissions" ;;
esac

# B.9b addition:
archetype="$(jq -r ".[\"${lane_id}\"].archetype" .claude/lane_models.json)"
SYSTEM_PROMPT_FLAG="--system-prompt-file .claude/system_prompts/${archetype}.md"

# Compose:
$CLAUDE_BIN $PERM_FLAG $SYSTEM_PROMPT_FLAG $ORCH_CHANNEL_FLAGS ...
```

### §6.3 Rollout order

1. **Pre-flight:** B.9a files exist + lint passes (assertion from
   `agent_readability_lint.py check system-prompts` — a sub-command
   to be added by B.9a, not B.9b).
2. **Review:** operator reviews the diff against a single test lane
   (e.g., `flex-d`) by adding the flag for that one lane and restart-
   only-that-lane.
3. **Canary:** one lane of each archetype runs with the flag for one
   session cycle; observe `session_start` events carry the
   `system_prompt_file` field populated (per Primitive A schema
   extension; B.9b adds this field to the `session_start` event type
   in A's v1.N additive evolution, not v1.0).
4. **Fleet:** add the flag to all 19 lanes. Restart fleet. Canary
   monitoring for first 24 hours.
5. **Observability gate:** once the flag is live fleet-wide, the
   §5-B B.9b Phase 1 Validation signal ("prompt-policy-cited-in-trace
   rate rises") is measurable via the B.3 `prompt_policy_version`
   field populated on `dispatch_recommendation` events.

### §6.4 Rollback

Single-commit rollback: `git revert <B.9b launch-script commit SHA>`;
next fleet-restart reverts to no `--system-prompt-file` flag. The
lanes then fall back to the Claude Code default system prompt — which
is the pre-B.9b state. Rollback is complete within one fleet restart
(< 5 minutes wall-clock for a full restart; per-lane restart < 30
seconds).

**Rollback test (per §2 acceptance):** `tests/unit/test_steward_session_launch.py::test_system_prompt_file_revertable` parses the launch script
pre- and post-revert, asserts the flag is present pre-revert and
absent post-revert; paired with a manual smoke of restarting one
lane and verifying `claude --print` consumes the default system
prompt.

### §6.5 Observable behavior change

The proving run tracks a single metric for B.9b effectiveness:
**`prompt_policy_cited_in_trace_rate`** (per §5-B B.9b Phase 1
Validation).

Definition: fraction of `dispatch_recommendation` events whose
`prompt_policy_version` field is populated with a non-null version
string. Pre-B.9b: ~0% (policy is a rule file, not loaded into lane
context). Post-B.9b: target ≥90% (per §5-B B.3 Phase 1 Validation —
every dispatch reads and emits the policy version).

Observability path: add a dashboard panel (in `ops/dashboard.py` post-
Primitive A) showing the metric rolling over 7 days. Rising to target
post-B.9b rollout is the proof-of-effectiveness signal.

### §6.6 Orthogonality to `.claude/agents/**` (per G10 default)

B.9b does not modify or read `.claude/agents/**`. If G10 ADR picks
*replacement* or *supplement* instead of *orthogonal*, B.9b
reconciles at execution time by:

- Replacement: B.9b's `--system-prompt-file` flag supersedes
  `.claude/agents/<lane>.md` for the session-level prompt; agents-
  file content is migrated into `.claude/system_prompts/<archetype>.md`
  by B.9a (upstream). No launch-script change.
- Supplement: B.9b launches with both flags — `--system-prompt-file
  .claude/system_prompts/<archetype>.md --agent <lane>`. Loading
  order documented in G10. Launch-script change: add the second flag.

**Scope-lock for this shape:** orthogonal default is assumed.
Reconciliation lives in the execution packet (Packet B-exec author)
if G10 picks non-orthogonal; it adds a 15-minute reconciliation step
at execution time. Not blocking.

---

## §7. B.10 Effort-level configuration

### §7.1 Home + shape

Per §5-B B.10 Phase 0 Readiness: effort recommendations recorded in
B.1 dispatch policy (lower / xhigh / max per Boris Cherny Opus 4.7
guidance); cross-referenced with B.6 approval classes.

**Config home:** `.claude/rules/effort_policy.md`

**File shape:**

```markdown
# Effort Policy

> Per-archetype × per-task-type effort tier defaults. Consumed by B.1
> adaptive dispatch at dispatch-time; overrides allowed per-packet via
> the `effort_hint` routing-metadata key.

## Version

`b10-v1.0`

## Tier vocabulary

| Tier | Semantics | Context size | Typical use |
|---|---|---|---|
| `lower` | Minimal reasoning; fast turnaround | <50KB | Simple edits, lint fixes, docs typos |
| `xhigh` | Extended reasoning; default for most work | 50–300KB | Feature implementation, refactoring, shaping |
| `max` | Maximum context + reasoning; slowest | 300KB–1MB | Governing plans, cross-module design, hardest shaping |

(Aligned with task_queue.py `VALID_EFFORT_HINTS = {"low", "medium", "high"}`
as `lower = low`, `xhigh = high`, `max` not yet in registered enum —
B.10 adds `max` to the effort enum as part of Packet B-exec.)

## Policy table

| Archetype | task_type=investigation | task_type=implementation | task_type=refactor | task_type=fix | task_type=docs |
|---|---|---|---|---|---|
| orchestrator | xhigh | n/a | n/a | n/a | n/a |
| ops | lower | n/a | n/a | lower | lower |
| review | xhigh | n/a | n/a | n/a | n/a |
| analyst | max | n/a | n/a | n/a | xhigh |
| author | n/a | xhigh | xhigh | xhigh | lower |
| brws-author | n/a | xhigh | xhigh | xhigh | lower |
| flex | xhigh | xhigh | xhigh | xhigh | lower |

## Override protocol

Per-packet override: set `effort_hint` in packet routing_metadata.
B.1 honors the override verbatim, records the override reason in the
emission payload (`effort_source: "override" | "policy"`).

## Rollback

Single-commit revert of this file; next dispatch reads the prior
version (caching is per-session so policy changes are session-boundary
effective).
```

### §7.2 Resolution path at dispatch time

B.1's `recommend_lanes()` gains an `effort_for(archetype, task_type)`
helper (pure function over the policy table). Resolution is:

1. Packet carries `routing_metadata = {"task_type": "implementation",
   "effort_hint": "high"}`.
2. B.1 resolves the candidate lane's archetype (from `.claude/lane_models.json`).
3. B.1 calls `effort_for(archetype, task_type)` — returns the policy
   default (e.g., `"xhigh"`).
4. B.1 compares the policy default to the packet's `effort_hint`:
   - Match: no override; `effort_source: "policy"`.
   - Mismatch: override; `effort_source: "override";
     override_reason: <caller-supplied-or-null>`.
5. B.1 emits `dispatch_recommendation` with both the policy value
   and the resolved value as separate fields.

**Feedback loop (to B.1):** if `effort_source: "override"` is
recurrent for a specific `(archetype, task_type)` pair (≥20% override
rate over 7 days), B.12 flags it as a probe candidate — the policy
default is likely miscalibrated and operator should review.

### §7.3 Integration with B.1 scoring

Per §3.1 item 3, B.1's `effort_match` score component uses the policy
output as its reference. Rationale: when B.1 scores candidate lanes,
lanes whose archetype policy matches the packet's resolved effort
hint score higher than lanes whose archetype policy does not match
— even if both lanes are "opus auto-mode". This produces the
per-archetype effort-affinity selection §5-B B.10 Phase 1 Validation
measures ("effort recommendations cited in ≥80% of dispatch
decisions").

### §7.4 Lint + unit test

**Lint (`check prompt-policy` extension):** enforce policy-file
structure (version header; table has all 8 archetypes × all 5
task_types; tier values are one of `{lower, xhigh, max, n/a}`).

**Unit test (`tests/unit/test_effort_policy.py`):**
- `effort_for("author", "implementation")` returns `"xhigh"`.
- `effort_for("ops", "investigation")` raises (archetype has no
  investigation task_type — `n/a`).
- Policy table matches the markdown table 1:1 (parser test).
- `effort_for` is pure (no I/O).

### §7.5 `max` effort enum addition

Packet B-exec adds `"max"` to `VALID_EFFORT_HINTS` in
`src/bid_euchre/ops/task_queue.py`. Migration: existing packets
default to their current enum values; `"max"` becomes available
for new dispatches. `validate_routing_metadata()` updated to accept
the new value.

**Cross-ref:** task packet schema extension is a schema change, which
per governing-plan `§5-A` versioning discipline is a v1.N additive
evolution of the routing-metadata contract. Documented in commit
footer.

---

## §8. B.11 Orchestration recipe archive

### §8.1 Home + shape

Per §5-B B.11 Phase 0 Readiness: versioned record at
`knowledge/orchestration_recipes/` (or `knowledge/PLAYBOOKS.md`
section); each entry: context → decision → observed outcome; updated
by archivist (Primitive D) from proving-run events.

**Choice:** `knowledge/orchestration_recipes/` as a directory (not a
PLAYBOOKS.md subsection). Rationale:
- Each recipe is ≥50 lines when worked out (context + decision
  rationale + outcome evidence + replay/reuse guidance); a single-
  file playbook would grow unmanageable.
- Directory structure lets archivist (Primitive D) emit individual
  files rather than diff-patching a monolithic playbook.
- `INDEX.md` aggregation is the agent-readable discovery surface.

**Directory layout:**

```
knowledge/orchestration_recipes/
├── INDEX.md                                   # Auto-generated; per-recipe 1-line summaries
├── shape_then_execute_pattern11.md            # First recipe: the Pattern 11 dispatch itself
├── packet2a_2b_split.md                       # Second recipe: the Packet 2a → 2b verification contract split
├── parallel_adr_dispatch.md                   # Third recipe: session 2026-04-23 six-packet parallel
├── _template.md                               # Blank schema for new recipes
└── _archive/                                  # Retired recipes (superseded or proven ineffective)
```

### §8.2 Recipe entry schema

Every recipe file has the three required sections:

```markdown
# Recipe: <name>

## Version

`b11-recipe-<slug>-v<MAJOR>.<MINOR>`

## Context

<When was this pattern observed? What task class / scope / pressure
 point was it a response to? Include trace-IDs or commit references.>

## Decision

<What pattern emerged? Enumerate the decisions (who does what, in
 what order, with what artifacts). Include anti-patterns ruled out.>

## Observed outcome

<What happened when this pattern was applied? Include outcome metrics
 (throughput, review-cycle time, issue-rate, rework-rate). Cite
 evidence — PR numbers, trace IDs, session-memory entries.>

## Reuse guidance

<When should this pattern be applied again? When should it NOT be?
 Name the invariants that make it effective and the failure-modes
 that make it inappropriate.>

## Downstream citations

<List of other packets / PRs / recipes that have cited this recipe.
 Auto-updated by archivist when citations are detected.>
```

### §8.3 Worked example (seeded at Phase 0 close)

Packet B-exec seeds the directory with at least one full recipe.
Candidate: **the shape-then-execute Pattern 11 dispatch itself**.

```markdown
# Recipe: Shape-then-execute Pattern 11 dispatch

## Version
`b11-recipe-shape-then-execute-v1.0`

## Context
Session 2026-04-23 demonstrated that novel, multi-file, multi-decision
work (steward platform Phase 0 primitives) routes poorly through
single-packet dispatch — authors re-litigate decisions that should
have been bounded at shaping time. Trace evidence: PRs #2759 / #2762
(verification contract 2a/2b), PR #2771 (Primitive A pre-shape).

## Decision
Decompose novel Phase 0 work into two packets:
1. Analyst produces a shaping doc (Pattern 11 minimum sections).
2. Author executes against the shape, scope-locked to it.

The shape is authoritative; author escalates on gaps rather than
re-designing in-line.

## Observed outcome
Session 2026-04-23: 25 files / 3804+ additions landed in Packet 2b
without author re-litigation. Observed ~4× throughput gain vs.
sequential design-in-author for novel infrastructure work.
Downstream: zero governing-plan clarifications during Packet 2b
execution (vs. historical rate of 2-4 clarifications per novel
packet).

## Reuse guidance
Apply when: scope crosses >3 files; touches multiple primitives;
requires design decisions not fully in governing plan; novel
pattern/infrastructure work.
Do NOT apply when: single-file obvious fix; straightforward
extension of existing pattern; design decisions fully specified
elsewhere (ADR / existing sub-plan).

## Downstream citations
- Pattern 11 §10.9 of governing_plan.md
- PR #2773 (Pattern 11 codification in ADR-adjacent commit)
- This shaping doc (Primitive B pre-shape)
```

**Rationale for self-seeding:** Pattern 11 *itself* is a recipe;
seeding it in the archive at the moment B.11 ships is both a
worked example and a proof that the archive is load-bearing —
the pattern the archive documents is the pattern the archive
came into existence through.

### §8.4 Archivist integration (Primitive D)

Per §5-B B.11 Phase 0 Readiness: "Updated by archivist (Primitive D)
from proving-run events". Archivist (not yet built — Primitive D
Phase 0 scope) will:

1. Detect recurring patterns in `dispatch_recommendation` events
   (e.g., "analyst-to-author handoff with shaping doc" appears ≥3
   times in a week).
2. Propose a recipe candidate as a file under `knowledge/_candidates/
   recipes/<slug>.md` (staging area).
3. Operator reviews (weekly), promotes to
   `knowledge/orchestration_recipes/<slug>.md` or rejects.

B.11 Phase 0 scope is the *archive home + schema + seeded worked
example + lint*; archivist inflow/outflow is Primitive D scope.

### §8.5 Lint + INDEX.md generation

**Lint (`check recipes` per §2.1):**
1. Every file in `knowledge/orchestration_recipes/**/*.md` (except
   `_archive/*` and `_template.md`) has the six required sections
   (Version, Context, Decision, Observed outcome, Reuse guidance,
   Downstream citations).
2. `INDEX.md` has a line referencing every non-archive, non-template
   file.
3. Version format `b11-recipe-<slug>-v\d+\.\d+`; monotonic per file.
4. Downstream-citations section has links that resolve (PRs, other
   recipes, rule files).

**INDEX.md generation:** auto-generated by a Primitive C script
(`scripts/internal/generate_kb_index.py`, per governing plan §5-C).
Packet B-exec adds the recipes directory to the index-generator
glob pattern; one-line entry per recipe.

---

## §9. B.12 Improvement-mechanism evaluation

### §9.1 Script home + shape

Per §5-B B.12 Phase 0 Readiness: `scripts/internal/measure_improvements.py`;
scheduled weekly; measures five metric deltas; output at
`knowledge/_candidates/<date>_improvement_metrics.md`.

**Script skeleton:**

```python
# scripts/internal/measure_improvements.py
"""
Weekly improvement-mechanism evaluation.

Reads event stream from `data/events/events-*.jsonl` (Primitive A) and
computes five rolling-window metrics, comparing the current week vs.
the prior week. Output: `knowledge/_candidates/<date>_improvement_metrics.md`.

Five metrics:
- retry_rate: fraction of task_started events whose task_completed has
  outcome != "completed" (per packet-id grouping).
- author_rework_rate: fraction of PRs with >1 push-to-branch after
  initial PR creation (per pr_number grouping against GitHub API).
- routing_correction_rate: rate of `dispatch_override` events per
  `dispatch_recommendation` event (B.1 feedback signal).
- prompt_policy_rollback_rate: rate of `git revert` commits
  touching `.claude/rules/prompt_policy/**` per week.
- skill_promotion_usefulness: rate at which skills promoted via B.2
  reduce retry_rate on subsequent dispatches (post-promotion window
  vs. pre-promotion window).

Outputs per-metric delta, sign, and flag for probe-candidate
recurring patterns (repeat-task probe).
"""

def main(since: str | None = None) -> int:
    ...
```

### §9.2 Repeat-task probe + threshold

Per §5-B B.12 (and per MEMORY.md session 2026-04-23 entry — the
probe requirement is a Primitive B sub-deliverable addition, not
yet in the governing plan table verbatim): when a task class
repeats ≥N times in a rolling window, flag for automation /
codification review.

**Threshold:** N=3 occurrences in a 14-day rolling window.

**Task-class signature:** per `dispatch_recommendation` event, the
signature is:
```
(packet_title_tokenized, archetype_resolved, task_type, effort_resolved)
```

Where `packet_title_tokenized` is the title with packet-specific
identifiers (task IDs, file paths, issue numbers) normalized away,
leaving the semantic phrase ("shape primitive X phase 0 spec"
normalizes to "shape primitive phase 0 spec").

**Probe output:** the metrics file includes a `## Repeat-task probes`
section:

```markdown
## Repeat-task probes (≥3 occurrences in last 14 days)

- **"shape primitive phase 0 spec"** — analyst × investigation ×
  max effort; 7 occurrences; suggested codification: make the
  Pattern 11 shape template a `/shape-primitive` skill.
- **"fix permission-mode launch for lane"** — author × fix × xhigh;
  3 occurrences; suggested codification: fold into the steward-
  session.sh launch-script lint.
- ...
```

Operator reviews probe candidates weekly; disposition:
- **Codify** (create skill, lint, or automation): file as a follow-up
  packet.
- **Defer** (not yet worth codifying; keep observing).
- **Dismiss** (noise; tokenization over-aggregated).

### §9.3 Metric delta discipline + net-positive / net-negative tracking

Per §5-B B.12 Phase 1 Validation: "≥1 mechanism change demonstrates
net-positive improvement-quality metric delta during the proving run;
≥1 mechanism change demonstrates net-negative and is rolled back".

The script computes deltas for each metric (this-week vs. prior-week).
A "mechanism change" is any commit that:
- Modifies `.claude/rules/prompt_policy/**` (B.3 change).
- Modifies `.claude/rules/tool_risk_registry.md` (B.6 change).
- Modifies `.claude/rules/effort_policy.md` (B.10 change).
- Modifies `src/bid_euchre/ops/learning.py` (B.1 change).
- Promotes or demotes a skill (B.2 change).

Each change is tagged with a change-ID (commit SHA). The script
correlates: metric values for the week after change-ID vs. the week
before. Net-positive = most metrics improved; net-negative = most
metrics regressed. Operator reviews; promotion / rollback is explicit
operator action.

**Rollback discipline (per §11 rev-reversibility goal):** any mechanism
change shipped to the active fleet carries a `## Rollback` note in
its commit message citing the single command needed (`git revert <SHA>`
plus fleet-restart if applicable).

### §9.4 Cadence + scheduling

**Initial:** manual invocation via `uv run python
scripts/internal/measure_improvements.py --since <date>` (operator-
run).

**Phase 1 target:** scheduled via a `/compile-improvement-metrics`
skill + nightly cron (wrapping the same script). Nightly means the
probe window is responsive; weekly cadence is only the operator-
review cadence.

**Observability:** script emission includes a
`improvement_metrics_computed` event (steward-additive event type,
registered in A's v1.N evolution). Dashboard panel reads the
latest candidate file; operator sees current-week metrics at a
glance.

### §9.5 Unit test (`test_measure_improvements.py`)

**Assertions:**
1. Seeded fixture: 100 synthetic `task_started` / `task_completed`
   events with known retry counts — assert `retry_rate` computes
   correctly.
2. Seeded fixture: 50 synthetic `dispatch_recommendation` /
   `dispatch_override` events — assert `routing_correction_rate`
   computes correctly.
3. Threshold-probe: seed 5 events with identical task-class
   signature over 14 days; assert probe flag appears.
4. Tokenization: seed 3 events with packet titles
   "Fix #1234 in foo.py" / "Fix #5678 in foo.py" / "Fix issue in
   foo.py"; assert they tokenize to the same signature ("fix in
   foo.py").
5. Net-positive detection: seed pre-change + post-change metrics;
   assert script classifies as "net-positive" correctly.

---

## §10. Packet B-exec execution spec

Concrete enough that an author lane can execute without additional
shaping.

### §10.1 Scope declared

**Files created:**

- `.claude/rules/tool_risk_registry.md` (new — B.6)
- `.claude/rules/effort_policy.md` (new — B.10)
- `knowledge/orchestration_recipes/INDEX.md` (new — B.11)
- `knowledge/orchestration_recipes/_template.md` (new — B.11)
- `knowledge/orchestration_recipes/shape_then_execute_pattern11.md` (new — B.11 seeded example)
- `scripts/internal/measure_improvements.py` (new — B.12)
- `tests/unit/test_ops_learning_model_aware.py` (new — B.1 extension)
- `tests/unit/test_tool_risk_registry.py` (new — B.6)
- `tests/unit/test_effort_policy.py` (new — B.10)
- `tests/unit/test_measure_improvements.py` (new — B.12)
- `tests/unit/test_steward_session_launch.py` (new — B.9b; may already exist from #2767 fix — coordinate at execution time)
- `tests/unit/test_prompt_policy_registry.py` (new — B.3 lint coverage)

**Files modified:**

- `src/bid_euchre/ops/learning.py` (B.1 — add `required_safety_envelope` + `required_model_tier` kwargs; add pre-filter; advance POLICY_VERSION to `"b1-v1"`)
- `src/bid_euchre/ops/task_queue.py` (B.10 — add `"max"` to `VALID_EFFORT_HINTS`; update `validate_routing_metadata`)
- `.claude/rules/prompt_policy/orchestrator.md` (B.3 — add `## Version`, `## Trigger`, `## Expected effect`, `## Rollback` sections)
- `.claude/rules/prompt_policy/author.md` (B.3 — same)
- `.claude/rules/prompt_policy/analyst.md` (B.3 — same)
- `.claude/rules/prompt_policy/common.md` (B.3 — same)
- `.claude/hooks/permission-denied-log.sh` (B.6 — enrich event with registry lookup)
- `.claude/tmux/steward-session.sh` (B.9b — add `--system-prompt-file` flag; guarded by feature flag if B.9a files not yet present)
- `.claude/rules/80_permission_model.md` (B.6 — add § "Tool-risk registry" subsection pointing to the registry file)
- `scripts/internal/agent_readability_lint.py` (B.3 + B.6 + B.11 — add three new sub-commands: `check prompt-policy`, `check tool-risk`, `check recipes`)
- `knowledge/INDEX.md` (B.11 — reference `orchestration_recipes/INDEX.md`)
- `plans/steward_platform/verification_contract/map.md` (add 7 Primitive B coverage rows)
- `MEMORY.md` (post-merge entry — Primitive B Phase 0 landing)

**Files NOT modified by Packet B-exec (deferred):**

- `.claude/lane_models.json` (created by Packet 2 / #2767 fix on author-c; B.1 reads this file but does not author)
- `.claude/system_prompts/<archetype>.md` (created by Packet 5 / B.9a on analyst-d; B.9b launch-flag wiring references these but does not author)
- `.claude/agents/<lane>.md` (G10 ADR default = orthogonal; no changes in Packet B-exec)
- `src/bid_euchre/ops/events.py` (Primitive A Packet 3; B.1 emits through it but does not author)
- Primitive D archivist (proposes recipes into `knowledge/_candidates/recipes/`; not yet built)
- Primitive F skill-promotion / token-economy evaluator (B.2 out of scope for this packet)

### §10.2 Order of operations

1. **Branch + scope lock.** `feat/primitive-b-phase0` from `origin/main`.
2. **Dependency check.** Confirm:
   - `.claude/lane_models.json` exists (if not: note forward-dep; B.1 unit test uses a fixture file).
   - `.claude/system_prompts/` directory exists with 8 archetype files (if not: B.9b flag-wiring stays behind a feature flag).
   - `src/bid_euchre/ops/events.py` from Primitive A exists (if not: B.1 uses the pre-A fallback emitter; note coordination).
3. **B.3 first (cheapest, no code).** Extend the 4 policy files with the four required sections. Write `test_prompt_policy_registry.py` covering the lint assertions (§4.6). Add `check prompt-policy` sub-command to `agent_readability_lint.py`. Run lint; expect clean.
4. **B.6 second.** Author `.claude/rules/tool_risk_registry.md` with initial coverage of all tools in `permissions.allow`. Author `test_tool_risk_registry.py`. Extend `agent_readability_lint.py` with `check tool-risk`. Extend `.claude/hooks/permission-denied-log.sh` to enrich events with registry lookup. Add back-pointer subsection in `80_permission_model.md`.
5. **B.10 third.** Author `.claude/rules/effort_policy.md` with the 8 × 5 policy table. Add `"max"` to `VALID_EFFORT_HINTS` in `task_queue.py`; update `validate_routing_metadata`. Author `test_effort_policy.py` covering the resolver + enum extension.
6. **B.1 fourth (main code block).** Extend `ops/learning.py` per §3: new kwargs; pre-filter; three new score inputs; effort_for integration with B.10 table; emission schema extension; POLICY_VERSION bump to `"b1-v1"`. Author `test_ops_learning_model_aware.py` covering: model-tier filter; safety-envelope filter; escalation class (destructive tool on non-Opus); fallback behavior when `.claude/lane_models.json` missing; POLICY_VERSION trace in emissions.
7. **B.11 fifth.** Create `knowledge/orchestration_recipes/` directory. Author `_template.md`, `INDEX.md`, `shape_then_execute_pattern11.md` (full worked example). Extend `agent_readability_lint.py` with `check recipes`. Update `knowledge/INDEX.md` to reference. Two more recipes (`packet2a_2b_split.md`, `parallel_adr_dispatch.md`) may ship in this packet or be deferred to a follow-up — execution-time orchestrator decision based on author-lane effort budget.
8. **B.12 sixth.** Author `scripts/internal/measure_improvements.py` with the five-metric computation + repeat-task probe. Author `test_measure_improvements.py` with seeded-fixture assertions. Run the script manually against current event stream (or synthetic fixture if event stream is empty); confirm output file renders cleanly.
9. **B.9b seventh.** Extend `.claude/tmux/steward-session.sh` with the `--system-prompt-file` flag per §6.2. If `.claude/system_prompts/` is empty, wrap the flag addition in a feature-flag env var (`STEWARD_SYSTEM_PROMPT_FILE=0` default) so the flag is not emitted until the files exist. Author `test_steward_session_launch.py::test_system_prompt_file_revertable`. Manual smoke: restart one lane with the flag enabled (if B.9a files present); confirm `session_start` event carries `system_prompt_file` field.
10. **verification_contract/map.md coverage.** Add 7 rows for the 7 B deliverables. Run `uv run python scripts/internal/verify_map_coverage.py`; expect 100%.
11. **Full lint + test sweep.** Run all three new lint sub-commands; expect clean. Run Tier 1 unit tests for each new file; expect pass. Run `make check-gated` (foreground); expect pass.
12. **Open PR.** Title: `feat(steward-platform): land Primitive B Phase 0 — adaptive dispatch + prompt-policy + tool-risk + launch + effort + recipes + improvement-eval (Packet B-exec)`. Body includes `Verification Performed` section with all lint + test output pasted.

### §10.3 Validation commands (Tier 1 + Tier 2)

```bash
# Tier 1 — unit (during development)
uv run python -m pytest tests/unit/test_ops_learning_model_aware.py
uv run python -m pytest tests/unit/test_tool_risk_registry.py
uv run python -m pytest tests/unit/test_effort_policy.py
uv run python -m pytest tests/unit/test_measure_improvements.py
uv run python -m pytest tests/unit/test_steward_session_launch.py
uv run python -m pytest tests/unit/test_prompt_policy_registry.py

# Tier 1 — targeted lint
uv run python scripts/internal/agent_readability_lint.py check prompt-policy
uv run python scripts/internal/agent_readability_lint.py check tool-risk
uv run python scripts/internal/agent_readability_lint.py check recipes

# Self-run: script smoke
uv run python scripts/internal/measure_improvements.py --since 2026-04-01

# Coverage-map verification
uv run python scripts/internal/verify_map_coverage.py

# Manual smoke (B.9b — only if B.9a files present)
# 1. Restart flex-d lane with STEWARD_SYSTEM_PROMPT_FILE=1
# 2. Grep data/events/events-<today>-001.jsonl for session_start events; confirm system_prompt_file field populated

# Negative-path
# 1. Delete .claude/lane_models.json temporarily; call B.1 recommend_lanes(); confirm fallback warning emitted
# 2. Call B.1 with a required_tool whose tool_risk row is reject-under-bypass against a bypass lane; confirm refusal
# 3. Author a policy-file edit without bumping version; confirm lint flags it

# Tier 2
make check-gated
```

### §10.4 Coordination notes

- **Dependency on Packet 2 / #2767 fix (author-c):** B.1 reads
  `.claude/lane_models.json`. If #2767 has not landed at Packet B-exec
  dispatch: Packet B-exec creates a fixture `.claude/lane_models.json`
  for unit test purposes *only* and files a blocker to orchestrator
  to coordinate dispatch order. Execution-lane preference: wait for
  #2767 fix before executing B.1 (otherwise B.1 ships against a
  fixture file that becomes authoritative by accident — Pattern 9
  load-bearing-ownership violation).
- **Dependency on Packet 5 / B.9a (analyst-d):** B.9b references
  `.claude/system_prompts/<archetype>.md` files. If B.9a has not
  landed: Packet B-exec ships B.9b flag-wiring behind a feature flag
  (see §10.2 step 9). The feature flag flips to enabled in a
  follow-up packet once B.9a merges.
- **Dependency on Primitive A / Packet 3:** B.1 emits through
  `ops/events.py`. If A has not landed: B.1 retains the existing
  `log_recommendation_for_dispatch()` fallback writer. Migration to
  A's emitter happens in a follow-up packet once A merges. This is
  a code path divergence the unit test covers (conditional import).
- **Dependency on Primitive C / agent_readability_lint.py base:**
  If the base script has not landed when Packet B-exec dispatches,
  the three sub-commands ship as standalone scripts under
  `scripts/internal/` with a TODO to fold into the unified lint
  once C's base lands. (Same fallback as Packet 3 / Packet 2b.)
- **Dependency on G10 ADR (system_prompts vs. agents relationship):**
  Default orthogonal is assumed. If G10 picks non-orthogonal,
  B.9b launch-script wiring reconciles at execution time (adds the
  second flag or migrates agents-file content). Not blocking at
  dispatch; reconciliation is execution-lane work.
- **Coordination with Primitive D archivist:** B.11 ships the
  archive home, schema, lint, seeded example. Archivist proposes
  additional recipes into `knowledge/_candidates/recipes/` when D
  ships. Packet B-exec does not need to coordinate timing — B.11
  ships first; archivist flows into the home when ready.
- **Coordination with Primitive F token-economy:** B.10's effort
  policy informs F's token-economy rollups (effort tier × tokens).
  No blocking dependency; both can ship in parallel. F's token
  measurements read `effort_source` field from `dispatch_recommendation`
  emissions (B.1 output).
- **Native-substrate-first preference (§10.9 Pattern 2):** if a
  native Claude Code feature surfaces during Packet B-exec
  implementation that subsumes a B deliverable (e.g., a native
  prompt-policy registry, a native tool-risk taxonomy), file an ADR
  and coordinate with the orchestrator. Do not silently rewrite to
  native without an ADR.

### §10.5 Packet B-exec success criterion

> Packet B-exec is complete when:
>
> (a) all files in §10.1 are created or modified per spec,
> (b) §10.3 validation commands pass (foreground; Tier 2 green),
> (c) all three new lint sub-commands (`check prompt-policy`,
>     `check tool-risk`, `check recipes`) run clean,
> (d) `verify_map_coverage.py` reports 100% Primitive B coverage
>     (or ≥90% with operator review note on the gap),
> (e) B.1's POLICY_VERSION trace appears as `"b1-v1"` in at least
>     one seeded `dispatch_recommendation` emission,
> (f) B.6's tool_risk_registry.md has rows for every tool in
>     `permissions.allow` (grep cross-check),
> (g) B.11's archive has ≥1 full worked example recipe committed
>     (minimum: the shape-then-execute Pattern 11 recipe),
> (h) B.12's script produces a non-empty output file when run
>     against the current event stream (or synthetic fixture if
>     the stream is empty),
> (i) B.9b flag-wiring is present in the launch script (enabled
>     or feature-flagged depending on B.9a state),
> (j) PR merged with `Verification Performed` evidence in the body
>     (lint output + pytest output + manual-smoke output pasted).
>
> After Packet B-exec merges, downstream Primitive Phase 0 work
> (D archivist feeding B.11 inflow; E active-triage consuming
> `dispatch_override` events; F token-economy consuming
> `effort_source` fields from B.1 emissions; G10 ADR resolution
> informing B.9b orthogonal reconciliation) can proceed.

### §10.6 Packet B-exec effort estimate

- LOC estimate: ~2500–3500 net additions (ops/learning.py extension
  ~200; scripts/internal/measure_improvements.py ~400; 6 new unit
  tests ~800; policy files + registry + recipes ~600; lint sub-
  commands ~300; launch-script extension ~50; permission-denied
  hook extension ~100; map coverage rows + docs ~200).
- Author-lane effort hint: **high** (per task_queue enum).
- Estimated turnaround: 3-4 author-lane sessions if no major
  blockers surface. The breadth (7 deliverables) is a natural
  split point — orchestrator may decompose into:
  - **Packet B-exec.α:** B.3 + B.6 + B.10 + B.11 (policy/config/
    archive — no Python code; operator-reviewable in one pass).
  - **Packet B-exec.β:** B.1 + B.12 + test sweep (Python code +
    event emission integration).
  - **Packet B-exec.γ:** B.9b (launch-script + feature flag +
    coordination with B.9a).
  - Decomposition is orchestrator's call at dispatch time based on
    author-lane availability.

---

## §11. Self-review against completeness criteria

Per the analyst prompt-policy clause (`§4.3` of
`verification_contract/shaping.md`): every shaping doc deliverable
names a verification surface, and the shape ends with a self-audit.

### §11.1 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| All seven deliverables (B.1/B.3/B.6/B.9b/B.10/B.11/B.12) have spec sections | §3 / §4 / §5 / §6 / §7 / §8 / §9 | ✓ (one section per deliverable) |
| Every deliverable has a named Pattern 10 verification surface | §2 table has 7 rows, each with surface column populated | ✓ |
| §2 surface-class choices match `verification_contract/shaping.md` §2 defaults | B.1 = unit test (Python module); B.3 = operator-readable review + lint (policy rule); B.6 = operator-readable review + structural test (rule file); B.9b = rollback test + event-schema query (config edit); B.10 = unit test + commit-footer citation (policy rule); B.11 = INDEX inclusion + lint (KB entry); B.12 = unit test + runnable command (new Python script) | ✓ |
| B.1 integration with existing `ops/learning.py` specified (extend, not replace) | §3.1 | ✓ |
| B.1 safety-envelope awareness per ADR 006 | §3.2 | ✓ |
| B.1 `.claude/lane_models.json` forward-dep handled (not authored here) | §3.3 | ✓ |
| B.1 event emission through Primitive A (with pre-A fallback) | §3.4 | ✓ |
| B.1 destructive-tool escalation (refuse non-Opus absent override) | §3.5 | ✓ |
| B.3 per-file schema extension specified | §4.2 | ✓ |
| B.3 registry assembly mechanism | §4.3 | ✓ |
| B.3 integration with `.claude/system_prompts/` (B.9a) | §4.4 | ✓ |
| B.3 version pin + rollback | §4.5 | ✓ |
| B.3 lint scope | §4.6 | ✓ |
| B.6 dual-envelope classification per ADR 006 | §5.2 | ✓ |
| B.6 home + shape | §5.1 | ✓ |
| B.6 runtime consumption path (B.1 + classifier) | §5.3 | ✓ |
| B.6 emission via Primitive A permission_denied enrichment | §5.4 | ✓ |
| B.6 relationship to `80_permission_model.md` | §5.5 | ✓ |
| B.9b B.9a forward-dependency handled (feature flag) | §6.1 | ✓ |
| B.9b launch-script contract | §6.2 | ✓ |
| B.9b rollout order + rollback | §6.3 / §6.4 | ✓ |
| B.9b observable behavior metric | §6.5 | ✓ |
| B.9b orthogonality to `.claude/agents/**` per G10 default | §6.6 | ✓ |
| B.10 home + shape | §7.1 | ✓ |
| B.10 resolution path at dispatch time | §7.2 | ✓ |
| B.10 integration with B.1 scoring | §7.3 | ✓ |
| B.10 `max` enum addition | §7.5 | ✓ |
| B.11 home + shape + schema | §8.1 / §8.2 | ✓ |
| B.11 worked example | §8.3 | ✓ |
| B.11 archivist integration (Primitive D coordination) | §8.4 | ✓ |
| B.11 lint + INDEX.md generation | §8.5 | ✓ |
| B.12 script home + shape | §9.1 | ✓ |
| B.12 repeat-task probe + threshold | §9.2 | ✓ |
| B.12 metric delta + net-positive / net-negative tracking | §9.3 | ✓ |
| B.12 cadence + scheduling | §9.4 | ✓ |
| Execution packet spec covers files + order + validation + coordination | §10 | ✓ |
| Execution packet success criterion explicit | §10.5 | ✓ |
| §15.2 Phase 2 Decision Inputs subsection at end | §12 | ✓ |
| Verification Plan section at end | §13 | ✓ |

### §11.2 Risks I surfaced during self-review (orchestrator decision)

1. **B.9b dispatch ordering with B.9a.** If the orchestrator dispatches
   Packet B-exec before Packet 5 (B.9a) completes, B.9b ships behind
   a feature flag — but the flag flip-on event is then a separate
   follow-up packet, which adds a coordination step. **Recommendation:**
   orchestrator prefers to wait for Packet 5 (B.9a) to merge before
   dispatching Packet B-exec, OR decomposes Packet B-exec per §10.6
   so B.9b lives in Packet B-exec.γ and the dispatch of γ waits on
   B.9a while α/β proceed. My preference: decompose into α/β/γ.
2. **B.1 dispatch-filter behavior when `.claude/lane_models.json` is
   missing.** §3.3 specifies a conservative default (opus / auto-
   mode for unknown lanes). Risk: the conservative default *hides*
   misconfiguration — a lane that declared itself sonnet in another
   file but absent in lane_models.json gets treated as opus.
   **Recommendation:** the B.1 unit test asserts a warning is emitted
   when any candidate lane is missing from lane_models.json. Operator
   should treat the warning as a must-triage signal, not noise.
   Lint extension candidate: cross-check lane_models.json keys
   against `get_known_lanes()` at commit time.
3. **Tool-risk registry initial coverage scope.** §5.1 seeds with
   rows for every tool in `permissions.allow`, but the registry
   should eventually cover every tool any lane may invoke — including
   MCP tools and custom Bash patterns. Initial coverage is lower-
   bound; lint (§5.2 item 4) catches gaps via the event stream. Risk:
   at Phase 0 Readiness time, the event stream may not have enough
   history to surface gaps. **Recommendation:** operator reviews the
   registry at Phase 0 close + again at Phase 1 mid-point; flag
   entries that have never been consulted (dead rows) and entries
   that have been consulted but have a `TBD` — but the lint doesn't
   allow `TBD`, so the latter shouldn't happen.
4. **B.10 `max` effort enum addition is a schema change.** §7.5
   extends `VALID_EFFORT_HINTS` from `{low, medium, high}` to add
   `max`. Existing packets in the queue continue to use the original
   values; new packets can opt in. Risk: the enum extension is a
   task_queue.py schema change that could interact with other
   tooling (operator dispatcher, existing tests). **Recommendation:**
   §7.5 includes a migration note — update `validate_routing_metadata`
   and all dispatching surfaces in a single commit; run a full test
   sweep to verify no existing caller fails.
5. **B.11 self-seeding recipe choice.** §8.3 seeds with the shape-
   then-execute Pattern 11 recipe (self-referential). Risk:
   self-seeding makes the archive's worked example recursive, which
   is conceptually elegant but may confuse future readers who expect
   a non-meta example first. **Recommendation:** also seed one
   non-meta recipe (e.g., the orchestration-recipe for the Packet
   2a → 2b verification-contract split) so the first two recipes
   span "meta" + "concrete" use cases. Packet B-exec author's call
   at execution time.
6. **B.12 tokenization signature stability.** §9.2 normalizes packet
   titles by removing task IDs, file paths, and issue numbers — but
   this tokenization has no existing implementation in the repo.
   Packet B-exec must implement the tokenizer; the unit test (§9.5
   item 4) locks the contract. Risk: the tokenizer could over- or
   under-aggregate; operator review loop in §9.2 mitigates but
   doesn't prevent the first-week noise. **Recommendation:** Phase
   0 ships with a simple tokenizer (regex-based; drop integers,
   drop hexadecimal task IDs, drop `#NNNN` issue refs, keep other
   tokens); revisit at Phase 1 mid-point with real data.
7. **Lint-sub-command ownership.** §2.1 says Primitive C owns
   `agent_readability_lint.py` base; Packet B-exec extends with three
   sub-commands. If C's base hasn't landed when B-exec dispatches,
   Packet B-exec creates the base (widens scope ~150 LOC). **Recommendation:**
   orchestrator confirms dispatch order — Primitive C base before
   Packet B-exec if possible; otherwise Packet B-exec creates the
   base with a clear TODO marker.

### §11.3 Orchestrator option: adversarial review

If the orchestrator wants independent adversarial review of this
shaping before Packet B-exec dispatch, dispatch a separate packet to
any other analyst lane (analyst-b/c/d, recusal applied) with the
prompt:

> "Review `plans/steward_platform/2_primitive_B/shaping.md` for:
> (a) seven-deliverable spec completeness against governing_plan.md
> §5-B + ADR 006 / ADR B8 / G13; (b) Pattern 10 surface coverage per
> §2 table (every deliverable has a named surface, surface class
> matches `verification_contract/shaping.md` §2 defaults);
> (c) execution-packet spec executability (§10 — author lane could
> open a PR without ambiguity); (d) forward-dependency handling
> (#2767 / Packet 5 / Primitive A / C) — does each dependency have
> a non-blocking fallback path?; (e) self-review §11.2 risk
> surfacing adequacy. Recommended but not blocking."

### §11.4 Constraint encountered

The task packet did not require spawning a reviewer agent (the
analyst-lane YAML frontmatter structurally disallows Agent-tool
invocation). Self-review per §11.1 + §11.2 substitutes; orchestrator
may upgrade to adversarial review per §11.3.

---

## §12. Phase 2 Decision Inputs

**Portability readiness:** Improved. B.1's `required_safety_envelope`
+ `required_model_tier` kwargs and `.claude/lane_models.json` read
contract are cell-boundary-respecting: a second cell would declare
its own lane-models mapping and its own tool-risk registry; B.1
would plug into the new mapping without code change. The §5-B B.3
prompt-policy registry is inherently portable (content is per-cell
policy). B.11 recipe archive is generic knowledge, not cell-specific.
Source: §3.2 / §3.3 / §4.3 of this shaping doc.

**Meta-layer need:** No change. The seven B deliverables integrate
through existing primitives (A for emission; C for lint base; G13
for archetypes) rather than introducing a new framework layer.

**Kill signal for primitive(s) named:** No. This shaping sharpens
Primitive B Phase 0 execution; it does not propose killing any
primitive. §11-B Kill criteria remain: B.1 row 1 ("dispatch
decisions ≥20% worse than operator baseline"); B.3 row 2 ("prompt
policy cited in <50% of traces"). If Packet B-exec lands and the
proving run shows either signal, §11-B kill criterion triggers —
but the shaping itself does not trigger.

**Re-evaluation needed in Phase 3:** Possibly. If the 8-archetype ×
5-task-type effort policy table (§7.1) turns out to miss dimensions
during the proving run (e.g., effort varies with file-change magnitude
rather than task_type alone), re-evaluate at Phase 3. Re-evaluation
window: end of proving run (end of Phase 1), informed by B.12
override-rate metric. **RE-EVAL: end-of-Phase-1**

**Surprise finding:** The fact that *six* primitives (A / C / D / E
/ F / G) all have forward dependencies into B's work — and B has
forward dependencies back into A (events) and G (lane_models.json,
archetypes) — makes B the **most-coupled** Phase 0 primitive by
edge count. §12 of the governing plan names A as the cascade-risk
primitive ("A slip cascades to D, E, H"); but B's coupling is
structural rather than cascading — a B slip doesn't stop downstream
primitives from landing, it just makes their decisions less
observable (events without policy versions; dispatches without
safety-envelope filtering). This suggests a follow-up shaping
consideration: is there a Phase 0 "coupling-audit" deliverable
that maps forward-dep graphs across primitives and flags
high-coupling primitives for more rigorous review?

**Disposition:** open

---

## §13. Verification Plan (Pattern 10 mandate)

Per the analyst prompt-policy clause (`§4.3` of
`verification_contract/shaping.md`): every shaping doc deliverable
names a verification surface. This shaping doc itself is the
deliverable; its "verification surface" is whether downstream Packet
B-exec can be authored from it without additional shaping. Per
Pattern 10 deliverable-class mapping, this is a **shaping artifact**
with operator-review surface form.

| Deliverable (§N.M of this shaping doc) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §3 B.1 adaptive dispatch spec | shaping spec for module extension under `src/bid_euchre/ops/**` | Packet B-exec author can extend `ops/learning.py` from §3 alone | author (Packet B-exec) | Packet B-exec PR's `ops/learning.py` matches §3.1–§3.6 design; `POLICY_VERSION = "b1-v1"` after change |
| §4 B.3 prompt-policy registry spec | shaping spec for `.claude/rules/**` structural extension | Packet B-exec author can extend all 4 policy files + author lint from §4 alone | author | `check prompt-policy` sub-command clean on extended files |
| §5 B.6 tool risk registry spec | shaping spec for new `.claude/rules/**` file + hook extension | Packet B-exec author can author `tool_risk_registry.md` + extend `permission-denied-log.sh` from §5 alone | author | `check tool-risk` clean; permission-denied events carry approval-class fields |
| §6 B.9b fleet launch adoption spec | shaping spec for `.claude/tmux/steward-session.sh` edit | Packet B-exec author can extend the launch script from §6 alone | author | Launch-script lint clean; `test_system_prompt_file_revertable` passes |
| §7 B.10 effort-level configuration spec | shaping spec for new policy file + enum extension | Packet B-exec author can author `effort_policy.md` + extend `VALID_EFFORT_HINTS` from §7 alone | author | `test_effort_policy.py` passes; `max` accepted by `validate_routing_metadata` |
| §8 B.11 orchestration recipe archive spec | shaping spec for new `knowledge/**` subdirectory | Packet B-exec author can create the archive + seed the worked example from §8 alone | author | `check recipes` clean; `knowledge/INDEX.md` references the archive |
| §9 B.12 improvement-mechanism evaluation spec | shaping spec for new Python script under `scripts/internal/**` | Packet B-exec author can author `measure_improvements.py` from §9 alone | author | `test_measure_improvements.py` passes; script produces non-empty output when run on seeded fixture |
| §10 Execution packet spec | dispatch-readiness | Orchestrator can dispatch Packet B-exec from §10 without re-shaping | orchestrator | Packet B-exec dispatched with §10 contents copied verbatim into Validation field |
| §11 Self-review | analyst-discipline check | All §11.1 criteria checked | analyst (this packet) | §11.1 table all ✓ |
| §12 Phase 2 Decision Inputs | required §15.2 schema subsection | 5 prompts + disposition all populated | analyst (this packet) | §12 has all 5 prompts + disposition |
| §13 Verification Plan | this section | Lint cross-walks every §N.M to a surface | analyst (this packet); lint (post-Packet-2b) | `agent_readability_lint.py check verification-contract` clean against this file |

**Worked example for reading this section (per Pattern 10 lenient-form):**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §3.2 safety-envelope awareness | architectural constraint | grep `dispatch_recommendation` events for `required_safety_envelope` field populated → expect 100% of emissions after B.1 lands | author (Packet B-exec) | grep returns 100% coverage in seeded smoke |
| §5.2 destructive-tool escalation | runtime-behavior constraint | grep `dispatch_recommendation` events for `safety_envelope_override: true` with `override_reason: "tool-risk-rejected-under-bypass"` → expect ≥1 match when a destructive-tool packet is seeded against a bypass lane | author | grep returns expected match in negative-path test |
| §6.5 prompt_policy_cited_in_trace_rate | metric target | dashboard panel shows metric ≥90% rolling over 7 days post-B.9b rollout | ops (during proving run) | dashboard reading ≥90% |
| §9.2 repeat-task probe threshold | threshold constraint | `measure_improvements.py` output flags a signature appearing ≥3 times in 14-day window → expect probe section populated when fixture is seeded with 5 identical-signature events | author | probe section non-empty in unit-test output |

---

## §14. References

- `plans/steward_platform/governing_plan.md` §5-B — primary source for Primitive B scope (12 sub-deliverables; this shape covers 7 Phase 0)
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 8 / Pattern 9 / Pattern 10 / Pattern 11 — pattern enforcement
- `plans/steward_platform/governing_plan.md` §11-B — B kill criteria rows
- `plans/steward_platform/governing_plan.md` §15.2 — Phase 2 Decision Inputs subsection schema
- `plans/steward_platform/adrs/006-auto-mode.md` — dual-envelope safety model; §"Model tier interaction" amendment (PR #2769 merged)
- `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` — keep ops/task_queue.py bespoke; adopt lifecycle hooks
- `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` — 19-lane → 8-archetype mapping (PR #2768 merged)
- `plans/steward_platform/1_primitive_A/shaping.md` — event schema v1.0 emission contract; `dispatch_recommendation` event type added by B.1
- `plans/steward_platform/verification_contract/shaping.md` — format exemplar; Pattern 10 enforcement catalog
- `plans/steward_platform/verification_contract/map.md` — Primitive B coverage rows will be added by Packet B-exec
- `src/bid_euchre/ops/learning.py` — shadow-mode advisor (PR #2721); extended by B.1
- `src/bid_euchre/ops/task_queue.py` — routing metadata contract (PR #2169 Slice C); `max` enum added by B.10
- `.claude/rules/prompt_policy/{orchestrator,author,analyst,common}.md` — 4-file scaffold (PR #2762); extended by B.3
- `.claude/rules/80_permission_model.md` — auto-mode operational guide; cross-reference added by B.6
- Issue #2767 — model-tier-aware permission-mode handling (forward dependency for B.1/B.6)
- `.claude/hooks/permission-denied-log.sh` — permission-denied event hook; enriched by B.6
- `.claude/tmux/steward-session.sh` — fleet launch script; extended by B.9b
- `.claude/rules/prompt_policy/analyst.md` — analyst lane shaping-doc obligation (this doc complies)
- `plans/steward_platform/adrs/010-mcp-memory-service.md` — KB governance reference (rejected; relevant to B.11 archive design discipline)
- Task packet: `7e312ba73ae6` (Primitive B pre-shape)
