# Token Economy Baseline Refresh — Steward-Era

**Date:** 2026-04-20
**Author:** author-b (Slice A of the token-economy restart plan)
**Predecessor:** `plans/sessions/2026-03-23_token-economy-baseline.md`
**Data range:** 2026-01-28 to 2026-04-20 (82 calendar days)
**Sessions analyzed:** 2,152 (308 session-meta skipped as malformed or
duplicate; 659 project-JSONL files skipped as partial/malformed)
**Related PRs:** #2169 (governance); PR introducing this report (Slice A).

---

## Purpose

This report refreshes the pre-steward baseline produced on 2026-03-23
(308 sessions, 2.67M tokens, all on the main checkout) with the first
fleet-era, multi-lane measurement. It is the measurement prerequisite for
Slices B-F of the restart plan — every downstream slice (caching strategy,
verbosity caps, dispatcher throttling, etc.) must be evaluated against this
baseline and against the staleness/parity gates that Slice A adds to the
CLI.

Unlike the 2026-03-23 report, which ran on unattributed data with a single
`main-checkout` pool, this refresh includes per-lane and per-pool breakdowns
made possible by the Phase 4 attribution pipeline and the staleness/parity
surfacing added in Slice A.

---

## Reproduction Command

```bash
uv run python scripts/internal/ops.py usage import
uv run python scripts/internal/ops.py usage attribute
uv run python scripts/internal/ops.py usage status
uv run python scripts/internal/ops.py usage summary
uv run python scripts/internal/ops.py usage lanes
uv run python scripts/internal/ops.py usage throughput
uv run python scripts/internal/ops.py usage anti-patterns
uv run python scripts/internal/ops.py usage reconcile
```

All commands read from and write to
`.claude/runtime/token_economy/{session_usage,session_attributions}.jsonl`
(gitignored). No seed is required — the telemetry pipeline is deterministic
given the set of source session-meta JSON and project-JSONL files present
at the time of import.

The `usage attribute` step is **mandatory** before `usage lanes` /
`usage reconcile` if you want non-drifted per-lane totals; see §5 Gap
Analysis.

---

## 1. Aggregate Token Economy

| Metric              | Value              | vs. 2026-03-23 baseline |
|---------------------|--------------------|-------------------------|
| Sessions            | 2,152              | +1,844 (+599%)          |
| Calendar span       | 82 days            | +42 days                |
| Total duration      | 317,102 min (5,285 h) | +4,763 h             |
| Total tokens        | 43,536,275         | +40,865,021 (+1,530%)   |
| Input tokens        | 2,014,592          | +1,457,797              |
| Output tokens       | 41,521,683         | +39,407,224             |
| Output/Input ratio  | 20.6x              | +16.8x                  |
| Tokens/hour         | 8,238              | +3,124                  |

The output/input ratio leap (3.8x → 20.6x) is the single largest
qualitative shift. It reflects the steward-era pattern of large
tool-result and file-read outputs returning from parallel agents, as well
as the introduction of the dashboard-first supervision surface that
expands context-window usage per session.

### Throughput

| Metric              | Value    |
|---------------------|----------|
| Lines added         | 72,672   |
| Lines removed       | 5,557    |
| Net lines           | 67,115   |
| Git commits         | 1,059    |
| Git pushes          | 783      |
| Files modified      | 664      |
| Tokens/commit       | 41,111   |
| Tokens/net line     | 649      |

Compared to the pre-steward baseline (10,948 tokens/commit, 40
tokens/net-line), the cost per committed unit of work has risen by
**~3.8x per commit** and **~16x per net line**. The primary driver is
session-level amplification (longer sessions, larger tool outputs), not
raw per-call inflation.

---

## 2. Per-Pool (Work-Class) Breakdown

Pools group lanes by their role in the fleet. Derived from
`lane_summary(...).pool` — see
`src/bid_euchre/ops/worktrees.derive_lane_class`.

| Pool          | Lanes | Sessions | Tokens      | Commits | % Tokens | Tok/Commit |
|---------------|-------|---------:|------------:|--------:|---------:|-----------:|
| (unattributed)*|    2 |    700   | 14,243,278  |    280  |  32.7%   |   50,868   |
| platform      |   5   |    591   | 12,408,130  |    278  |  28.5%   |   44,633   |
| browser-game  |   4   |    342   |  5,703,397  |    296  |  13.1%   |   19,268   |
| control       |   2   |    175   |  4,470,973  |      0  |  10.3%   |      —     |
| analyst       |   4   |    167   |  3,558,946  |    120  |   8.2%   |   29,657   |
| flex          |   4   |    177   |  3,151,551  |     85  |   7.2%   |   37,077   |
| **TOTAL**     |  21   |  2,152   | 43,536,275  |  1,059  | 100.0%   |   41,111   |

\* The `(unattributed)` row combines `main-checkout` (622 sessions, 12.3M
tokens, 247 commits — project work executed directly from the shared
checkout, typically pre-fleet or ad hoc) and `unattributed` (78 sessions,
1.9M tokens, 33 commits — sessions whose worktree could not be resolved
to a lane ID). Both are bundled here because neither represents a steward
lane pool.

### Key observations

1. **Platform pool carries ~29% of the fleet's tokens** across 5 author
   lanes (`author-a..d`, `author-scratch`) with ~44.6K tok/commit —
   2.3x the browser-game pool's efficiency.
2. **Browser-game pool is the most efficient** at ~19.3K tok/commit, which
   tracks the more bounded, template-heavy nature of browser feature work.
3. **Control pool (`ops`, `review`) has 0 commits across 175 sessions.**
   This is expected — these lanes run supervision and merge-gating, not
   authoring — but the 4.47M tokens consumed are a reminder that control
   plane cost is non-trivial and should be tracked against a separate
   tok/session (not tok/commit) metric in future slices.
4. **Analyst pool** shows ~29.7K tok/commit across 4 lanes with 167
   sessions; small sample per lane (see §4 Worst Offenders).
5. **Flex pool** is inflated by `flex-d`'s 114.3K tok/commit over only
   4 commits (below the §4 ranking threshold).

---

## 3. Per-Lane Detail

See `uv run python scripts/internal/ops.py usage lanes` for the authoritative
listing. Summary (all 21 lanes, post-attribute):

| Lane              | Pool          | Sessions | Commits | Tokens      | Tok/Commit |
|-------------------|---------------|---------:|--------:|------------:|-----------:|
| main-checkout     | —             |      622 |     247 | 12,320,016  |   49,879   |
| author-a          | platform      |      168 |      97 |  3,656,425  |   37,695   |
| author-b          | platform      |      140 |      66 |  3,215,253  |   48,716   |
| review            | control       |      137 |       0 |  2,624,058  |      —     |
| author-c          | platform      |      105 |      67 |  2,421,994  |   36,149   |
| author-d          | platform      |      114 |      48 |  2,224,050  |   46,334   |
| brws-author-a     | browser-game  |      115 |     102 |  2,105,812  |   20,645   |
| unattributed      | —             |       78 |      33 |  1,923,262  |   58,281   |
| ops               | control       |       38 |       0 |  1,846,915  |      —     |
| brws-author-b     | browser-game  |       99 |      89 |  1,562,092  |   17,552   |
| analyst-a         | analyst       |       69 |      56 |  1,379,220  |   24,629   |
| flex-a            | flex          |       74 |      46 |  1,356,763  |   29,495   |
| analyst-b         | analyst       |       37 |      30 |  1,118,029  |   37,268   |
| brws-author-c     | browser-game  |       66 |      48 |  1,053,100  |   21,940   |
| brws-author-d     | browser-game  |       62 |      57 |    982,393  |   17,235   |
| author-scratch    | platform      |       64 |       0 |    890,408  |      —     |
| flex-b            | flex          |       47 |      19 |    787,073  |   41,425   |
| analyst-c         | analyst       |       32 |      17 |    551,789  |   32,458   |
| flex-c            | flex          |       36 |      16 |    550,688  |   34,418   |
| analyst-d         | analyst       |       29 |      17 |    509,908  |   29,995   |
| flex-d            | flex          |       20 |       4 |    457,027  |  114,257\* |

\* `flex-d` excluded from the §4 ranking (only 4 commits — sub-threshold
sample size).

---

## 4. Worst Offenders (Ranked)

Only lanes with **≥10 commits** are ranked by tok/commit, matching the
`.claude/rules/deferred/05_rigor.md` principle of not drawing inference
from sub-threshold samples. The §3 table shows 4 lanes excluded from the
ranking (`review`, `ops`, `author-scratch`, `flex-d`).

| Rank | Lane           | Pool          | Commits | Tokens     | Tok/Commit |
|-----:|----------------|---------------|--------:|-----------:|-----------:|
|   1  | unattributed   | —             |     33  |  1,923,262 |   58,281   |
|   2  | main-checkout  | —             |    247  | 12,320,016 |   49,879   |
|   3  | author-b       | platform      |     66  |  3,215,253 |   48,716   |
|   4  | author-d       | platform      |     48  |  2,224,050 |   46,334   |
|   5  | flex-b         | flex          |     19  |    787,073 |   41,425   |
|   6  | author-a       | platform      |     97  |  3,656,425 |   37,695   |
|   7  | analyst-b      | analyst       |     30  |  1,118,029 |   37,268   |
|   8  | author-c       | platform      |     67  |  2,421,994 |   36,149   |
|   9  | flex-c         | flex          |     16  |    550,688 |   34,418   |
|  10  | analyst-c      | analyst       |     17  |    551,789 |   32,458   |

### Interpretation

- **Ranks 1-2 (unattributed + main-checkout)** are not fleet lanes — they
  represent work that ran outside the per-lane steward model. They
  nonetheless dominate the fleet's total token spend (45.5% of all
  tokens). Slice E (documented in `plans/sessions/2026-04-20_token_economy_restart_plan.md`
  when author-d's parallel PR lands) should treat this as the primary
  wedge: reducing main-checkout spend by directing ad hoc work to flex
  lanes would shift a large fraction of total tokens into more efficient
  pools.
- **Platform lanes (ranks 3-8, except ranks 5, 7, 10)** cluster around
  36-49K tok/commit. The spread is ~35% — suggesting lane-level variance
  is non-trivial but not pathological. No single platform lane is an
  outlier.
- **Browser-game lanes do not appear in the top 10.** They sit at ranks
  11+ with tok/commit in the 17-22K range.

---

## 5. Gap Analysis — What This Report Relies On From Slice A

The pre-Slice-A CLI (as of `main` at 2026-04-20) had three observability
gaps that would have made this report unreliable:

1. **Staleness opacity.** `usage summary` read whatever JSONL happened to
   exist, with no indication of whether the store had been refreshed
   recently. On a fleet where lanes import asynchronously, reports could
   silently reference weeks-old data.
2. **Empty-store silent success.** `usage summary` on a fresh checkout
   would print an all-zeros table with no warning, indistinguishable from
   a genuine "no work this period" state.
3. **Cross-surface drift invisibility.** `usage summary`, `usage lanes`,
   and `usage throughput` each compute totals independently. There was no
   cross-check surfacing attribution gaps or per-lane vs. aggregate drift.

### How Slice A closes these gaps

- **New `usage status` subcommand** prints an explicit status banner:
  `[fresh]` (age < 1h), `[stale: Xh old]`, `[missing]`, or
  `[empty]`. Also available as `store_status` on the public Python API
  (`StoreStatus` dataclass) and as a header suffix on the dashboard
  `Token Economy` section when stale (`Token Economy [STALE: 2h old]`
  or `...[STALE: 2h old; attributions missing]`).
- **New `usage reconcile` subcommand** cross-checks totals across
  `usage summary`, `usage lanes`, and `usage throughput` and prints
  `[OK]` / `[DRIFT]` with a parity footer. `[DRIFT]` is emitted for:
    - attribution-gap > 0 (→ hint: run `usage attribute`)
    - token delta > tolerance (tolerance = max(1% of summary tokens, 1000))
    - commit delta ≠ 0 (always)
- **Existing `usage summary` prepends the store-status banner and
  appends the parity footer** so that every routine check sees both gates
  without invoking new commands.

### Concrete demonstration in this data set

**Before `usage attribute` was run for this report**, `usage reconcile`
reported:

```
Totals parity: [DRIFT] cross-surface totals disagree:
  - Attribution gap: 844 imported session(s) lack attribution records
    (run `usage attribute`).
  - Token parity delta +21,881,316 tokens between `usage summary`
    (43,536,275) and sum-of-`usage lanes` (21,654,959);
    tolerance ±435,362.
  - Commit parity delta +815 commits between `usage summary` (1059) and
    sum-of-`usage lanes` (244).
```

Had this gap gone unseen, §2 and §3 of this report would have understated
fleet-level per-lane totals by **~50%** (21.6M of 43.5M tokens missing).
After running `usage attribute`, parity returned to `[OK]` with all
deltas at zero — the drift was a legitimate attribution-pipeline lag, not
double-counting. This is exactly the failure mode Slice A was designed
to catch.

---

## 6. Anti-Patterns (Post-Attribute)

From `uv run python scripts/internal/ops.py usage anti-patterns`:

1. **🔴 HIGH — Retry/churn sessions.** 77% of sessions (1,647/2,152)
   produced zero commits, consuming 30.0M tokens (69% of total spend).
   This is consistent with — but slightly higher than — the pre-steward
   baseline's 47.6% zero-commit rate on 1.15M tokens. The absolute
   zero-commit-tokens figure grew by **~26x** between the two periods.
2. **🟡 MEDIUM — Verbosity waste.** 649 tokens/net-line exceeds the 500
   tokens/net-line target by ~30%. Compared to the pre-steward baseline
   (40 tokens/net-line), verbosity has grown **~16x per committed line**.
   This is the largest single efficiency regression in the data set and
   is the primary motivation for Slice B of the restart plan.

---

## 7. Sample-Size Disclosures

Per `.claude/rules/deferred/05_rigor.md`:

- **Lane-level tok/commit ranking (§4)**: 10-commit minimum threshold.
  Lanes with fewer commits are noted in §3 but not ranked. This threshold
  is well below the 1,000-sample "feature correlation" floor from the
  rigor rule, so the rankings are **directional, not inferential**. They
  identify where to investigate, not where to draw conclusions.
- **Per-pool aggregates (§2)**: Pool-level totals are sums over 2-5
  lanes each; 167-700 sessions per pool. Sufficient for descriptive
  comparison, but not for a hypothesis test of "pool A is more efficient
  than pool B" — variance structure across lanes within a pool is not
  modeled in this report.
- **No statistical test is attached to this report.** This is
  intentional: §5 calls out that Slice A is a **measurement** prerequisite
  (surface the numbers and their gates). Slices B-F will include
  pre-specified effect-size thresholds and hypothesis tests when they
  propose specific interventions against these baselines.
- **Session duration noise**: Session durations are self-reported by the
  Claude Code client and are rounded to whole minutes. For sessions
  <5 min (62 sessions, 2.9% of total), tokens/hour is unreliable.
  Aggregate tokens/hour in §1 is computed over total duration, which
  dampens but does not eliminate this noise.
- **Source-file skips**: 308 session-meta JSON files and 659
  project-JSONL files were skipped during import (malformed, partial, or
  duplicate). At 2,152 clean sessions vs. ~967 unusable files, the clean
  rate is ~69%. This means per-pool totals may be biased downward for
  lanes whose telemetry is more prone to interruption (no evidence this
  effect is correlated with pool — assumed uniform).

---

## 8. Observations for Follow-On Slices

These are observations, not recommendations. Each is a candidate wedge
for a future slice but requires a dedicated plan before action.

1. **main-checkout dominance (12.3M tokens, 28.3% of fleet).** Investigate
   whether steering more ad hoc work into flex lanes would reduce total
   spend without loss of throughput.
2. **Control-pool token spend without commits.** `review` and `ops`
   together consume 4.47M tokens. Consider a separate metric
   (tok/session, tok/PR-reviewed, tok/event-projected) for control-plane
   lanes — tok/commit is structurally undefined for them.
3. **Verbosity regression vs. pre-steward.** Tokens/net-line has grown
   ~16x. Plausible contributors: larger tool outputs from parallel
   agents, dashboard context expansion, longer session transcripts.
   Slice B should target this with a controlled verbosity-cap
   experiment.
4. **Retry/churn growth in absolute terms.** 30M tokens on zero-commit
   sessions. Slice C (stall detection + auto-recovery) could reduce
   this significantly; baseline for the evaluation is captured here.

---

## Outcome

*Filled after implementation lands — this PR introduces this baseline
alongside the Slice A measurement-hardening code. See PR body for the
commit pair.*

---

## References

- `plans/sessions/2026-03-23_token-economy-baseline.md` — pre-steward
  baseline this report refreshes.
- `plans/sessions/2026-04-03_token_economy_optimization.md` — earlier
  optimization plan superseded by the restart plan.
- `.claude/rules/deferred/05_rigor.md` — sample-size and statistical-test
  requirements governing this report.
- Slice A code surface:
  - `src/bid_euchre/ops/token_economy.py` — `StoreStatus`,
    `store_status()`, `TotalsReconciliation`, `reconcile_totals()`.
  - `scripts/internal/ops.py` — `usage status`, `usage reconcile`,
    status banner + parity footer on `usage summary`.
  - `src/bid_euchre/ops/dashboard.py` — `Token Economy [STALE: ...]`
    header rendering when staleness is detected.
