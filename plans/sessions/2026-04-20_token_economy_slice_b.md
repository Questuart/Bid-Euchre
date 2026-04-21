<!-- review-tier: medium -->
# Token Economy — Slice B Session Plan (model × effort telemetry)

**Date:** 2026-04-20 (authored 2026-04-21)
**Author:** analyst-b (shaping only — no implementation)
**Governing plan:** `plans/sessions/2026-04-20_token_economy_restart_plan.md` § Slice B
**Related:** #2169 (token economy umbrella), #2687 (Slice A baseline refresh), #2694 (Slice C routing metadata)
**Predecessor baseline:** `plans/sessions/2026-04-20_token_economy_baseline_refresh.md`
**Status:** READY FOR DISPATCH — awaiting author lane assignment

---

## 1. Purpose

Extend the token-economy store so rollups can be broken down by the
**model** actually used during a session and by a **declared effort**
dimension that downstream slices (D/E) will populate. The telemetry
extension must:

1. Capture the real per-session model signal that already lives in JSONL
   (the `<JSONL>.message.model` field on assistant records) with no new
   upstream emission.
2. Accept an `effort` dimension that is almost entirely `null/unknown` at
   baseline and degrade gracefully until Slices D/E start populating it.
3. Expose additive CLI + dashboard surfaces — do not remove or rewire the
   existing lane-level summaries (rollback-plan requirement in the
   restart plan).
4. Update the measurement story enough to answer the operator's core
   question: *is premium-model spend concentrated in productive or
   unproductive work?*

Slice B is the last measurement-only slice before routing changes land in
Slice D. No dispatch behaviour, task-queue schema, or worker-pool logic
changes here.

---

## 2. Data availability audit

Verified 2026-04-21 against live runtime telemetry under
`~/.claude/projects/...` and
`~/.claude/usage-data/session-meta/` (see §8 Reproduction).

### 2.1 Per-project JSONL (`project-jsonl` record type)

Each assistant message carries a fully-populated `message` object:

```
message.keys() = ['content', 'id', 'model', 'role', 'stop_details',
                  'stop_reason', 'stop_sequence', 'type', 'usage']
```

Observed:

| Field | Path | Availability | Notes |
|-------|------|--------------|-------|
| model | `<JSONL>.message.model` (JSONL field) | **100%** of assistant messages | Values seen: `claude-opus-4-7`, `claude-sonnet-4-6`, `<synthetic>` |
| service_tier | `<JSONL>.message.usage.service_tier` (JSONL field) | 100% | Uniform `"standard"` in live data — not a useful effort proxy yet |
| speed | `<JSONL>.message.usage.speed` (JSONL field) | ~99.9% | Uniform `"standard"` — also not a useful effort proxy |
| thinking block | `message.content[].type == "thinking"` | Present but empty-redacted in JSONL | Proves extended-thinking *was* invoked without revealing contents — usable as a weak "effort:extended" binary proxy |
| input/output tokens | `<JSONL>.message.usage.*_tokens` (input, output, cache_creation_input, cache_read_input) | 100% | Already aggregated in `_scan_jsonl_file` |

**Model mixing within a session.** In a 25-session sample, 24 were
single-model and 1 contained two distinct models (opus + synthetic).
The `<synthetic>` entries come from Claude Code's internal
summarization/compaction pass and should not be counted as "production"
token spend.

### 2.2 Legacy session-meta (`session-meta` record type)

```
keys = ['session_id', 'duration_minutes', 'input_tokens', 'output_tokens',
        'user_message_count', 'assistant_message_count', 'tool_counts',
        'lines_added', 'git_commits', ...]
```

**Model is NOT present.** Session-meta predates per-message model capture.
These records (308 session-meta files in the 2026-04-20 import, all
pre-steward) must flow through rollups as `model=unknown`.

### 2.3 Effort

Claude Code does not emit a dedicated `effort` field to JSONL today.
Available proxies:

- `thinking` content-block presence — binary proxy for
  `effort ∈ {extended, unknown}`.
- `service_tier` / `speed` — both uniform `"standard"` today, reserved
  for future differentiation.
- `CLAUDE_CODE_EFFORT` env var (if set at launch by
  `.claude/tmux/steward-session.sh`) — **not currently emitted to
  JSONL**. Adding emission is out of scope per the shaping packet.

**Conclusion:** the `effort` dimension at Slice B baseline will be
dominated by `unknown`. The rollup contract and CLI/dashboard must treat
`unknown` as a first-class bucket, not a placeholder or error. When
Slices D/E start populating `effort_hint` on TaskPackets, and/or when
upstream emission adds a real effort field, the same rollup code picks
up the dimension without schema migration.

### 2.4 Task-completed event joins (from Slice C)

Slice C already shipped (PR #2694) and writes enriched
`task_completed` events to `.claude/runtime/events/events.jsonl` with:

```
{task_type, complexity_estimate, model_hint, effort_hint,
 actual_lane, recommended_lane, token_spend, elapsed_seconds,
 review_rounds, shipped_outcome, pr_number, packet_id, ...}
```

**Key distinction for Slice B rollups:**

- `model_hint` / `effort_hint` on the event = the **declared** routing
  intent set at packet creation. Present on every packet that used the
  metadata helpers, `None` on legacy packets.
- The **observed** per-session model comes from JSONL (the
  `<JSONL>.message.model` field). This is the independent signal Slice B
  introduces.

These two signals are deliberately kept separate. Divergence between
declared `model_hint` and observed model is a future routing-fidelity
metric, not an error.

### 2.5 Session ↔ packet join

Sessions in JSONL carry `sessionId` but **no packet_id**. Task-completed
events carry `packet_id` + `completed_by` lane. There is no direct key
to join a session to the specific packet it worked on.

**Slice B join policy (directional, not inferential):** bucket by
`(lane_id, day)`. For each lane-day:

- Sum observed tokens per model from JSONL (via `lane_id` attribution
  already in `SessionRecord`).
- Sum `token_spend` and count `shipped_outcome` values from the day's
  `task_completed` events for that lane.

**Duplication rule (normative).** When a lane-day contains sessions from
more than one observed model, naïvely attaching the full day's
`task_completed` count to every model seen in the bucket double-counts
outcomes and inflates the headline productivity ratio. Slice B resolves
this with **output-token-share weighting** at the lane-day granularity:

- Let `T_m` be observed output tokens for model `m` in the lane-day and
  `T = sum(T_m)` for all observed models. Share `w_m = T_m / T`.
- For each `task_completed` event in the lane-day, its outcome count
  (1 completed, 1 shipped or 1 churned per §3.5 enum mapping) is
  allocated to each model `m` as `w_m * count`. Fractional allocations
  accumulate in `float` and are rounded to `int` **only at CLI/JSON
  render** (dataclass stores `float`).
- When a lane-day has sessions from exactly one observed model, `w_m = 1`
  and allocation is trivially integer-preserving — this is the common
  case and produces no behavior change relative to the simpler spec.
- Lane-days whose only observed model is `unknown` (all-legacy
  session-meta rows) fall entirely into the `unknown` model bucket;
  their outcomes are not redistributed.

This yields the requested `model × work-outcome` rollup at lane-day
granularity. It is explicitly labelled "directional" in §7 (matching
§5 of the Slice A baseline) because we cannot prove per-session
causation for lanes that complete multiple packets in a day. A future
slice can tighten this join if session↔packet linkage is added
upstream. The token-share weighting is normative for Slice B — any
alternative (majority-model assignment, per-event lane-day-first-model
tiebreak) must be called out explicitly in the implementation PR so
reviewers can compare.

### 2.6 Degradation matrix

| Record class | model | effort | Rollup behaviour |
|--------------|-------|--------|------------------|
| Fresh project-jsonl, single model | captured | `unknown` until D/E | Counted in `by_model` with real model; `by_effort` → `unknown` bucket |
| project-jsonl, mixed model in one session | see §3.1 | `unknown` | Tokens split per-model by iteration; session counted once |
| Legacy session-meta | `unknown` bucket | `unknown` bucket | Totals preserved; cannot break down by model |
| project-jsonl with `<synthetic>` model only | `synthetic` bucket | `unknown` | Counted separately — surfaced but not rolled into production totals |

No record class produces an error; no record class is silently dropped.

---

## 3. Rollup schema

### 3.1 SessionRecord extension

Add optional fields to `SessionRecord` in
`src/bid_euchre/ops/token_economy.py` (schema_version bump to `3`):

```python
@dataclass
class SessionRecord:
    ...
    # Slice B: per-session observed model + effort (null-safe).
    model: str | None = None             # e.g. "claude-opus-4-7",
                                          # "claude-sonnet-4-6",
                                          # "synthetic", or None
    model_mix: dict[str, int] = field(default_factory=dict)
                                          # Only populated when >1 model
                                          # seen; maps model → output_tokens
                                          # attributed to that model via
                                          # the usage.iterations array
    effort: str | None = None             # Slice B emits None at baseline;
                                          # D/E populate via hint → effort
                                          # promotion pathway
```

`_scan_jsonl_file` changes:

1. Track a `models: collections.Counter[str]` per session, accumulating
   output tokens per model from each assistant message.
2. On build, if exactly one model is seen: `model = that_model`,
   `model_mix = {}`.
3. If >1 model seen: `model = <majority-by-output-tokens>`,
   `model_mix = dict(counter)` so analysts can still split correctly.
4. `session-meta` records: `model = None`, `model_mix = {}`.

Back-compat: all new fields default to `None` / `{}`. Existing
consumers that don't know about them continue to work. `schema_version`
bumps; existing stored records are left in place (reader tolerates
v2 rows via `.get(...)` semantics).

### 3.2 Rollup dataclasses

Add to `token_economy.py`:

```python
@dataclass
class ModelBucket:
    model: str                       # or the literal "unknown"
    session_count: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    git_commits: int | None = None    # None when all contributing sessions
                                      # were control-plane (no commits)

@dataclass
class EffortBucket:
    effort: str                      # "low" | "standard" | "extended" |
                                      # "unknown"
    session_count: int
    total_tokens: int
    git_commits: int | None = None

@dataclass
class LaneModelRow:
    lane_id: str
    model: str
    session_count: int
    total_tokens: int
    git_commits: int | None

@dataclass
class LaneEffortRow:
    lane_id: str
    effort: str
    session_count: int
    total_tokens: int
    git_commits: int | None

@dataclass
class ModelOutcomeRow:
    """Directional join at (lane, day) granularity — see §2.5."""
    model: str
    lane_days: int                   # number of (lane, day) buckets
                                      # contributing to this row
    session_count: int               # JSONL sessions in those buckets
    total_tokens: int                # observed tokens in those buckets
    # Counts are stored as floats to carry fractional allocations from
    # the lane-day token-share weighting (§2.5). CLI/JSON rounds to int
    # at render time.
    task_completed_count: float
    shipped_count: float             # mapped from shipped_outcome="merged"
    churned_count: float             # mapped from shipped_outcome
                                      # in {"abandoned", "rolled_back"}
    blocked_count: float             # mapped from shipped_outcome="blocked"
    other_count: float               # mapped from shipped_outcome="other"
                                      # and from None (no shipped_outcome
                                      # recorded at task_completed time)
    # Derived metric is computed by CLI/dashboard, not stored:
    # productive_fraction = shipped_count / max(task_completed_count, 1)
```

**shipped_outcome enum mapping (normative).** `scripts/internal/ops.py`
registers the `--shipped-outcome` CLI choice as
`{"merged", "abandoned", "rolled_back", "blocked", "other"}`, and the
`task_completed` event payload records `None` when the completer did
not pass `--shipped-outcome`. Slice B maps these five values plus
`None` deterministically:

| `shipped_outcome` value | Slice B bucket        |
|-------------------------|-----------------------|
| `"merged"`              | `shipped_count`       |
| `"abandoned"`           | `churned_count`       |
| `"rolled_back"`         | `churned_count`       |
| `"blocked"`             | `blocked_count`       |
| `"other"`               | `other_count`         |
| `None` (unset)          | `other_count`         |

The mapping table is expressed as a module-level constant
(`_OUTCOME_BUCKET: dict[str | None, str]`) in `token_economy.py` so the
`task complete` enum and the Slice B reducer can be kept in sync by a
single grep-friendly test (see §7.2). Adding a new outcome value to the
CLI enum without updating this table raises in the Slice B reducer and
fails the dedicated contract test — new values must not be silently
lumped into `other_count`.

### 3.3 Public API additions

```python
def model_summary(output_dir: Path | None = None) -> list[ModelBucket]: ...
def effort_summary(output_dir: Path | None = None) -> list[EffortBucket]: ...
def lane_model_summary(output_dir: Path | None = None) -> list[LaneModelRow]: ...
def lane_effort_summary(output_dir: Path | None = None) -> list[LaneEffortRow]: ...
def model_outcome_summary(
    output_dir: Path | None = None,
    events_dir: Path | None = None,
) -> list[ModelOutcomeRow]: ...
```

### 3.4 Storage location and retention

No new files. All rollups are **computed on demand** from the two
existing runtime-store files (`<runtime>/session_usage.jsonl` and
`<runtime>/session_attributions.jsonl`, where `<runtime>` resolves to
the gitignored directory `.claude/runtime/token_economy/`; neither
file is tracked in the repo — they are written by `usage import` and
`usage attribute`). This mirrors `lane_summary()` today
and means:

- No retention policy change.
- No new gitignore entry needed.
- `model_outcome_summary` reads `task_completed` events from **both**
  the active and archived event logs: `events.jsonl` *and*
  `events.archive.jsonl` (both under `.claude/runtime/events/`,
  gitignored). `src/bid_euchre/ops/events.py` drains completed records
  from the active log into the archive — reading only the active log
  would make the Slice B rollup depend on retention state rather than
  task history. Records are de-duplicated by `event_id` on read so a
  mid-drain race does not double-count. Callers may pass `events_dir`
  to override the location; both files are optional on disk (a fresh
  lane may have only `events.jsonl`, a long-lived lane may have both).

Caching, if profiling later reveals a hot path, is out of scope for
Slice B.

### 3.5 Null-safety contract

Normative behaviour for the `"unknown"` bucket (applies uniformly to
model and effort):

1. **Render as a distinct bucket**, not dropped, not merged into a
   default. CLI tables show a row labelled `unknown`. Dashboard panels
   show `unknown` with its share-of-total so the operator sees how much
   of the fleet cannot yet be attributed.
2. **Never zero-coerce.** A `None` model on a legacy session-meta row
   produces `model="unknown"`, not `model="claude-opus-4-7"` via any
   default fallback.
3. **Rollup math.** `unknown` rows contribute to `total_tokens` and
   `session_count` the same as any other bucket. They do NOT contribute
   to derived per-model ratios (e.g., "fraction of premium-model
   tokens") — the denominator for such ratios explicitly excludes
   `unknown` and the CLI prints a disclosure footer when the
   excluded-unknown fraction exceeds 10%.
4. **Schema consistency.** Every rollup row ships with the same
   dataclass shape regardless of bucket value — there is no
   `Optional[ModelBucket]`, only `ModelBucket(model="unknown", ...)`.
5. **Tests (§7.2):** dedicated null-safety test covering a mixed store
   (v2 session-meta rows + v3 JSONL rows, with and without model_mix).

---

## 4. CLI surface changes

All changes are additive — existing subcommands keep their current
output shape. New subcommands live alongside, gated behind no new
flags so existing shell snippets continue to work.

### 4.1 New subcommands

```
uv run python scripts/internal/ops.py usage by-model
uv run python scripts/internal/ops.py usage by-effort
uv run python scripts/internal/ops.py usage by-model-outcome
```

Shared flags: `--output-dir`, `--json`, and for `by-model-outcome` also
`--events-dir` (defaults to `.claude/runtime/events`).

### 4.2 Text output (non-JSON)

```
$ uv run python scripts/internal/ops.py usage by-model

Model                  Sessions      Tokens   % of total   Git commits
claude-opus-4-7           1,504  33,104,210       76.0%         702
claude-sonnet-4-6           340   8,421,005       19.3%         291
synthetic                     8      43,062        0.1%           —
unknown                     308   1,968,000        4.5%          66
— total —                 2,160  43,536,277      100.0%       1,059

[unknown bucket is 4.5% of tokens. Fractions excluding `unknown`: opus
79.6%, sonnet 20.2%, synthetic 0.2%.]
```

```
$ uv run python scripts/internal/ops.py usage by-effort

Effort       Sessions      Tokens   Git commits
standard            0           0             —
extended            0           0             —
low                 0           0             —
unknown         2,160  43,536,277         1,059
— total —       2,160  43,536,277         1,059

[effort dimension not yet populated — see Slice D/E.]
```

```
$ uv run python scripts/internal/ops.py usage by-model-outcome

Model                  Lane-days  Sessions  Tokens  Completed  Shipped  Churned
claude-opus-4-7              212      1,402   32.1M        147      131       12
claude-sonnet-4-6             88        312    8.0M         54       49        3
unknown                      127        448    3.4M          8        6        1
```

### 4.3 JSON output

Stable, documented schema. Consumers can pin to this shape.

```jsonc
// usage by-model --json
{
  "buckets": [
    {"model": "claude-opus-4-7",
     "session_count": 1504,
     "total_tokens": 33104210,
     "input_tokens": 1588000,
     "output_tokens": 31516210,
     "cache_read_tokens": 4121000,
     "cache_creation_tokens": 8901000,
     "git_commits": 702},
    ...
    {"model": "unknown", ...}
  ],
  "total_tokens": 43536277,
  "unknown_fraction": 0.045
}
```

```jsonc
// usage by-model-outcome --json
{
  "rows": [
    {"model": "claude-opus-4-7",
     "lane_days": 212,
     "session_count": 1402,
     "total_tokens": 32100000,
     "task_completed_count": 147,
     "shipped_count": 131,
     "churned_count": 12,
     "productive_fraction": 0.891},
    ...
  ],
  "join": {"granularity": "lane_day", "directional": true}
}
```

`productive_fraction` is computed by the CLI, not stored in the rollup
dataclass, because the `shipped_outcome` label set is owned by the
caller's reporting conventions.

### 4.4 Existing subcommand additions (opt-in only)

- `usage summary` gains a one-line trailer: `By model: opus 76.0%,
  sonnet 19.3%, synthetic 0.1%, unknown 4.5%.` Emitted only when the
  store contains at least one v3 record (otherwise trailer suppressed).
- `usage lanes` gains optional `--by model` / `--by effort` flags to
  group each existing row by the chosen dimension. With no flag,
  existing shape is untouched (important for dashboard parser stability
  and the reconcile gate added in Slice A).
- **No change** to `usage summary`, `usage lanes`, `usage throughput`,
  `usage anti-patterns`, `usage status`, or `usage reconcile` default
  shapes — parity checks from Slice A continue to pass byte-for-byte on
  pre-existing rollups.

### 4.5 Reconcile integration

`usage reconcile` is extended with one additional cross-check:

- Sum of `by-model` tokens must equal sum of `lanes` tokens within the
  existing tolerance. Drift hint: "run `usage import --force` to
  rescan JSONL with the model-aware scanner."

---

## 5. Dashboard wiring

Additive panel only — existing `Token Economy` section stays intact.

**Module boundary.** `dashboard_token_economy` is defined in
`src/bid_euchre/ops/token_economy.py` (line 2177 as of this writing).
`src/bid_euchre/ops/dashboard.py` imports it and renders the return
value — it does not own the payload shape. The Slice B payload change
therefore lives in `token_economy.py::dashboard_token_economy`; the
only edit to `dashboard.py` is in its `format_dashboard_text` helper
(referenced below), which reads the new `by_model` key and emits the
additive sub-section.

`src/bid_euchre/ops/token_economy.py::dashboard_token_economy` gains a
new `by_model` key on its return dict:

```jsonc
"by_model": {
    "buckets": [/* same shape as CLI by-model */],
    "unknown_fraction": 0.045
}
```

`format_dashboard_text` renders a new sub-section under the existing
`Token Economy` header:

```
Token Economy
  Tokens: 43,536,275 (2,160 sessions, 1,059 commits)
  Efficiency: 8,238 tok/hr, 20.6x out/in, +67,115 net lines
  Top lanes:
    main-checkout      12,320,016 tok  49,879 tok/commit
    author-a            3,656,425 tok  37,695 tok/commit
    author-b            3,215,253 tok  48,716 tok/commit
  By model:                     ← NEW, additive
    opus-4-7           33.1M tok (76.0%)  702 commits
    sonnet-4-6          8.4M tok (19.3%)  291 commits
    unknown             2.0M tok ( 4.5%)   66 commits
  Anti-patterns: 2 detected
    [HIGH] retry_churn
    [MEDIUM] verbosity_waste
```

Rules:

1. Section appears only when the `by_model → buckets` list is non-empty **and** at
   least one non-`unknown` bucket exists. On a fresh checkout with
   only legacy session-meta data, the section is suppressed rather
   than printed as "unknown 100%".
2. At most 4 rows rendered; remaining models folded into an `other`
   row if >4 non-unknown models are present (future-proof for the
   arrival of haiku, synthetic-classifier-N, etc.).
3. `effort` breakdown is **not** rendered in the dashboard at Slice B
   — it would be 100% `unknown` today and operator-confusing. Added
   once D/E produce real effort data (tracked as a deferred follow-up,
   not blocking Slice B).
4. JSON dashboard (`format_dashboard_json`) includes the full
   `by_model` and `by_effort` dicts unconditionally — scripting
   consumers get the raw data even when the TUI hides the panel.

Stale/empty handling reuses the existing
`_format_token_economy_header` path; no changes to the STALE banner
logic.

---

## 6. Baseline-report impact — recommendation

**Recommendation: Produce a new standalone Slice B report as part of
the Slice B implementation PR** (target filename
`plans/sessions/2026-04-20_token_economy_slice_b_report.md`, created
by the implementation PR — not this shaping PR). Do **not** re-issue
or mutate the Slice A baseline.

Rationale:

1. Slice A's baseline is referenced from #2687 and from
   `plans/sessions/2026-04-20_token_economy_restart_plan.md`. Mutating
   it would destabilize those links and break the rigor-rule contract
   that reports are reproducible from a committed command set at a
   point in time.
2. Decoupling the reports lets the operator compare the two baselines
   side by side — Slice A shows "where tokens go by lane", Slice B
   adds "where do they go by model, and is premium-model spend
   productive". Merging them collapses that comparison.
3. Slice B's report is numerically additive (new tables, no contradict
   of Slice A's numbers). Scope is bounded: one new report file,
   ≤6 numbered sections mirroring the Slice A structure, same
   reproduction-command convention.

**Required sections for the Slice B report:**

1. Purpose + reproduction command (`usage import`, `usage attribute`,
   `usage by-model`, `usage by-effort`, `usage by-model-outcome`).
2. Aggregate by model (opus/sonnet/synthetic/unknown).
3. Per-lane × model breakdown — only for lanes meeting the 10-commit
   sample threshold from Slice A §4 (rigor-rule compliance).
4. Model × work-outcome at lane-day granularity, with an explicit
   "directional, not inferential" disclosure reusing Slice A §5's
   wording.
5. Gap analysis — effort dimension is `unknown`-dominated; restate
   what Slice D/E must emit to make the `by-effort` view meaningful.
6. Observations for follow-on slices (candidate wedges only — no
   recommendations).

The report is produced as part of the Slice B PR (same repo change)
and is **not** split into a separate PR, matching the Slice A model.

---

## 7. Testing strategy

### 7.1 Targeted test files

| File | What it proves |
|------|----------------|
| `tests/unit/test_token_economy.py` | `_scan_jsonl_file` captures `model` and `model_mix`; `_build_record_from_jsonl` propagates them; schema_version=3 records read back correctly; v2 records remain readable |
| `tests/unit/test_ops_token_economy.py` | `model_summary`, `effort_summary`, `lane_model_summary`, `lane_effort_summary`, `model_outcome_summary` produce the documented dataclass shapes on fixture data; ratios and aggregates match hand-computed values |
| `tests/unit/test_ops_dashboard.py` | `dashboard_token_economy` emits `by_model` key; `format_dashboard_text` renders the additive sub-section when conditions are met and suppresses it when only `unknown` bucket exists |

No new test files needed; all three already exist from Slice A.

### 7.2 Required test cases (names are normative)

**Cases in tests/unit/test_token_economy.py:**

- `test_scan_jsonl_single_model_session` — assistant messages all
  `claude-opus-4-7` → `model="claude-opus-4-7"`, `model_mix={}`.
- `test_scan_jsonl_mixed_model_session` — opus + synthetic → majority
  wins for `model`; both populate `model_mix`.
- `test_scan_jsonl_synthetic_only_session` — `model="synthetic"`,
  recorded but not coerced.
- `test_build_record_from_jsonl_preserves_model_fields`.
- `test_session_meta_record_has_no_model` — `model=None` on legacy
  rows; reader treats as `"unknown"` bucket.
- `test_schema_version_bump_read_compat` — store with mixed v2/v3
  rows loads without error.
- `test_null_safe_unknown_bucket` — `unknown` row counted in totals
  but excluded from per-model ratio denominators.

**Cases in tests/unit/test_ops_token_economy.py:**

- `test_model_summary_shape` — returns `list[ModelBucket]`; totals
  match `usage_summary`.
- `test_effort_summary_all_unknown_at_baseline` — single `unknown`
  bucket with full token total.
- `test_lane_model_summary_respects_attribution` — lane IDs match
  existing `lane_summary()` output.
- `test_model_outcome_summary_lane_day_join` — fixture with known
  JSONL sessions + `task_completed` events produces expected
  `shipped_count` / `churned_count`.
- `test_model_outcome_summary_enum_contract` — fixture covers all five
  `shipped_outcome` values (`merged`, `abandoned`, `rolled_back`,
  `blocked`, `other`) plus `None`, and asserts the exact mapping from
  §3.2's `_OUTCOME_BUCKET` table; adding a new enum value in
  `scripts/internal/ops.py` without updating the mapping fails this
  test with a clear "unhandled outcome" error.
- `test_model_outcome_summary_token_share_weighting` — lane-day with
  two models (70/30 token split) and 10 `task_completed` events
  produces 7.0 + 3.0 allocations; single-model lane-days produce
  integer-preserving allocations.
- `test_model_outcome_summary_reads_archive` — events split between
  `events.jsonl` and `events.archive.jsonl` with one event_id present
  in both (mid-drain race) is counted exactly once.
- `test_model_outcome_summary_missing_events_dir` — returns rows with
  zero outcome counts, never raises.
- `test_reconcile_includes_by_model_parity` — mismatch surfaces
  `[DRIFT]` with the new hint text.

**Cases in tests/unit/test_ops_dashboard.py:**

- `test_dashboard_by_model_rendered_when_non_unknown_present`.
- `test_dashboard_by_model_suppressed_when_only_unknown` — legacy-only
  store does not show the panel.
- `test_dashboard_by_model_folds_tail_into_other` — >4 non-unknown
  models collapse correctly.
- `test_dashboard_json_always_includes_by_model_key` — scripting
  contract.

### 7.3 Schema-consistency gate

Add a single regression test
`tests/unit/test_ops_cli.py::test_by_model_cli_matches_library` that
runs `usage by-model --json` under subprocess and asserts the output
matches `model_summary()` called on the same store. Proves the CLI,
rollup, and dashboard cannot silently diverge.

### 7.4 Validation sequence (matches Slice A convention)

```
uv run python -m pytest tests/unit/test_token_economy.py \
    tests/unit/test_ops_token_economy.py \
    tests/unit/test_ops_dashboard.py -v
uv run python -m pytest tests/unit/test_ops_cli.py \
    -k "by_model or by_effort" -v
make check-gated
```

---

## 8. Dispatch-ready package

### 8.1 Scope lock

**File:** `plans/sessions/2026-04-20_token_economy_slice_b.md` (this
file — governs; copy intent into the PR body).

**Implementation scope (`scope_declared`):**

```
src/bid_euchre/ops/token_economy.py
scripts/internal/ops.py
src/bid_euchre/ops/dashboard.py
tests/unit/test_token_economy.py
tests/unit/test_ops_token_economy.py
tests/unit/test_ops_dashboard.py
tests/unit/test_ops_cli.py
plans/sessions/2026-04-20_token_economy_slice_b_report.md   (new)
```

**Out of scope (explicit):**

- Any change to `src/bid_euchre/ops/task_queue.py` (that's Slice C —
  already shipped #2694) or `src/bid_euchre/ops/worker_pool.py`
  (Slice D/E).
- Any change to `scripts/internal/ops.py task complete` event shape
  (Slice C).
- Any new telemetry emission point — Slice B consumes existing JSONL
  only.
- Any scorer / learning logic (Slice E).
- Any evaluation harness (Slice F).
- Any schema for caching rollups to disk (deferred; only needed if
  profiling shows on-demand rollup is slow).

### 8.2 Suggested PR title

`feat(ops): add lane × model × effort rollups to token economy (Slice B)`

### 8.3 Branch

`ops/token-economy-slice-b`

### 8.4 Validation commands

```bash
# Tier 1 during development
uv run python -m pytest tests/unit/test_token_economy.py \
    tests/unit/test_ops_token_economy.py \
    tests/unit/test_ops_dashboard.py \
    tests/unit/test_ops_cli.py -v

# Smoke the new CLI surfaces on the current store
uv run python scripts/internal/ops.py usage by-model
uv run python scripts/internal/ops.py usage by-model --json | python -m json.tool
uv run python scripts/internal/ops.py usage by-effort
uv run python scripts/internal/ops.py usage by-model-outcome

# Slice-A parity gate must still pass
uv run python scripts/internal/ops.py usage reconcile

# Tier 2 before PR
make check-gated
```

### 8.5 Acceptance criteria

The implementation PR is ready for review when:

1. `usage by-model`, `usage by-effort`, `usage by-model-outcome` all
   print a result on the live store and return non-zero only on
   genuine error conditions (not empty-store).
2. `usage reconcile` exits `[OK]` after `usage import --force`
   completes on a repo that already had a populated store — i.e., the
   schema_version bump does not invalidate existing rows.
3. All named test cases in §7.2 exist and pass.
4. Dashboard output on a real store shows the `By model` sub-section;
   dashboard output on a store with only session-meta suppresses it.
5. A new Slice B report file — the implementation PR will add a new file at `plans/sessions/2026-04-20_token_economy_slice_b_report.md` — with §§1-6 filled, reusing the Slice A report reproduction discipline.
6. PR body cites §8.4 commands and links this shaping plan.

### 8.6 Known risks and mitigations

| Risk | Mitigation |
|------|------------|
| JSONL scanner now reads every assistant message for model — increases CPU for `usage import --force` | Model capture is cheap (`dict.get` per message); existing scan already walks every message for token aggregation, so incremental cost is negligible. Add a micro-benchmark test in `tests/unit/test_token_economy.py` that asserts scan-time for a 1000-message fixture stays within 2× current baseline. |
| `effort` dimension is almost entirely `unknown` at Slice B ship — operator may read this as a bug | Dashboard suppresses `by-effort` until D/E populate it; CLI prints an explicit "effort dimension not yet populated" note. |
| Mixed-model sessions (opus + synthetic) could be misattributed | `model_mix` preserves the raw split. Slice B report excludes `synthetic`-only sessions from premium-spend ratios to avoid double-counting compaction overhead. |
| Schema bump to v3 could break external consumers | Only the repo-owned CLI + dashboard consume this store. Reader tolerates v2 rows indefinitely via `.get(...)` semantics. |
| Lane-day join for `by-model-outcome` is coarse | Documented as directional, not inferential. Future slice can tighten if session↔packet linkage lands upstream. |

### 8.7 Suggested author lane

Any platform author (author-a/b/c/d). Warm context advantage sits with
**author-b** (token-economy store staleness + totals parity landed as
#2687) or **author-d** (Slice D in flight, knows the packet-metadata
side). No hard dependency either way.

### 8.8 Estimated size

~450–600 net lines across source + tests (comparable to Slice A scope).
Single PR; does not require decomposition.

---

## 9. Outcome

_To be filled once the implementation PR lands._

---

## 10. References

- `plans/sessions/2026-04-20_token_economy_restart_plan.md` — governing plan
- `plans/sessions/2026-04-20_token_economy_baseline_refresh.md` — Slice A baseline
- PR #2687 — Slice A implementation
- PR #2694 — Slice C routing metadata (already shipped)
- `.claude/rules/deferred/05_rigor.md` — rigor / sample-size rule
- `src/bid_euchre/ops/token_economy.py` — scanner and store
- `scripts/internal/ops.py` § `usage` subcommands — CLI surface
- `src/bid_euchre/ops/dashboard.py` § token economy — dashboard wiring
