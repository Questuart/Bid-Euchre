<!-- review-tier: medium -->
# Token Economy Restart — Slice F Evaluation Protocol (DRAFT)

**Status:** DRAFT — shaping only. Evaluation has **not** been run. This
document locks the protocol *before* the data it will consume exists, so
decision criteria cannot be chosen post-hoc to match observed outcomes.
**Date:** 2026-04-21
**Author:** analyst-d (shaping under task `d3c78f23993a`)
**Governing plan:** `plans/sessions/2026-04-20_token_economy_restart_plan.md` §Slice F
**Governance home for D/E implementation:** SP-5-02 (Platform-11 partial reactivation)
at `plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md`
**Related:** #2169 (umbrella), #2159, SP-5-02

---

## 0. Executive Summary

When Slices C (routing metadata + outcome capture), D (fixed policy
controls: lane-default model/effort with low-risk task overrides), and E
(shadow-mode adaptive dispatch advisor) have landed **and** accumulated a
defined observation window, this protocol is dispatched to produce a
go/no-go recommendation.

Four decision questions, mapped to pre-committed operationalizations:

| # | Question | Metric | Threshold gate (pre-committed direction, numbers below) |
|---|----------|--------|---------------------------------------------------------|
| Q1 | Did tokens/merged-PR improve? | Median cached-input + output tokens per merged PR, by lane-pool | PROMOTE if ≥ target improvement on author-pool with no regression elsewhere |
| Q2 | Did review churn / rework get worse? | Review rounds per merged PR; revert/fix-up rate | ROLLBACK if rework rate increases materially vs Slice-A baseline |
| Q3 | Are model downgrades correctly applied per class? | % of low-risk task categories actually dispatched at cheaper model/effort; mis-classification audit | PROMOTE if ≥ target coverage AND mis-classification rate ≤ target |
| Q4 | Is the advisory scorer predictive? | Ranking agreement (Spearman ρ or top-1 accuracy) between advisor recommendation and realized clean-merge outcome, on tasks where N ≥ 5 per lane × task_type | Advisor promotion to higher-confidence modes only if meets threshold on a minimum task sample |

Exact threshold numbers are deferred to §4 and §5 and are intentionally
**unlocked** per SP-5-02's Adaptive Dispatch Policy Guardrails. Operator
must sign off on the number set at dispatch time of the evaluation, **not**
after reading the data.

> **Rigor caveat up-front:** fleet volume (~10–40 PRs/day, ~1–4 active
> lanes in a window) is **insufficient for rigorous A/B hypothesis
> testing**. Per `.claude/rules/deferred/05_rigor.md`, any claim resting on
> inferential statistics requires sample sizes this protocol will not have
> in its first run. Q1/Q2/Q4 are therefore structured as **effect-size +
> confidence-interval + operator judgment** comparisons, not
> p-value-driven tests. Q3 is a coverage-audit question and is quantitative
> in the counting sense, not the inferential sense. §4 is explicit about
> which claims are quantitative, which are qualitative, and where we do
> **not** claim statistical significance.

---

## 1. Observation Window Protocol

### 1.1 Rationale

Per `.claude/rules/deferred/05_rigor.md`:

- Bias detection: ≥ 2,000 deals
- Feature correlation: ≥ 1,000 samples per group
- Production reports: ≥ 50,000 samples

The steward fleet does not produce those volumes. An "observation window"
sized to reach 50,000 merged PRs would be multi-year. The protocol instead
uses a **minimum-credible-sample** heuristic and explicitly labels the
analysis as exploratory.

### 1.2 Window definition

The observation window is the interval `[T_start, T_end]` where:

- `T_start` = timestamp of the merge commit that landed the latest of
  { Slice C final PR, Slice D final PR, Slice E final PR }. Recorded
  verbatim from `git log` and embedded in the eval report.
- `T_end` = `T_start + window_duration` (see §1.3).

Tasks and PRs are **in-window** if their `task_completed` event (for the
advisor) or their GitHub `merged_at` timestamp (for tokens/PR) falls in
`[T_start, T_end]`.

Tasks whose packet was dispatched before `T_start` but whose completion
event lands after `T_start` are **out-of-window** for Q1/Q2/Q3/Q4 because
they were not routed under the new policy. They are reported separately as
a "mid-window carryover" row in the eval report.

### 1.3 Minimum window duration

The window closes when **all** of the following are met (whichever comes
last):

1. **Calendar floor:** 7 calendar days of fleet activity. (Aligned with
   baseline refresh cadence and matches the "at least one controlled
   period of production-like use" wording in the restart plan.)
2. **Merge floor:** ≥ 30 merged PRs routed under the new policy across the
   fleet. (Sufficient for bootstrap CIs on a median-tokens-per-PR metric
   with visible lane-pool contrast; still exploratory — explicitly not
   a p-value threshold.)
3. **Lane coverage floor:** ≥ 2 author lanes and ≥ 1 ops-or-review lane
   have each merged at least one PR whose routing was governed by the new
   policy. (Without multi-lane coverage, lane-pool contrasts are
   confounded with the specific lane that happened to run.)
4. **Advisor observation floor:** ≥ 5 observations per lane × task_type
   for at least two task_types. (Matches the SP-5-02 PR2 minimum
   `N ≥ 5 per task_type per lane` threshold before affinity scoring
   activates. Without this, Q4 is uncomputable and the protocol should
   return NO-GO on insufficient data rather than a recommendation.)

**Ceiling:** 14 calendar days. If floors are not met in 14 days, the
protocol emits a **NO-GO on insufficient data** verdict and files a
follow-up to either extend the window or revisit scope. Running longer
than 14 days confounds the evaluation with whatever else has changed in
the fleet and blurs the "this is the result of Slices D+E" attribution.

### 1.4 Handling sessions mid-window

- **Cleanly in:** Packet dispatched after `T_start`, completed before
  `T_end`, under the new routing policy → included in Q1/Q2/Q4.
- **Cleanly out:** Packet dispatched before `T_start` → excluded from all
  metrics except the "mid-window carryover" reporting row. Do not
  retroactively reclassify its outcome.
- **Advisor mid-window:** Q3 (downgrade coverage) and Q4 (advisor
  predictiveness) only count packets whose `<metadata.task_type>` was
  populated at dispatch time and whose routing decision was logged by
  Slice E's recommendation logger. Packets missing either field are
  reported in an "unaudited" row and excluded from Q3/Q4 numerators and
  denominators.

### 1.5 Observation-window handshake

Before starting the window, the operator must:

1. Confirm Slice C/D/E PRs are merged and their SHAs are captured in the
   eval report's "Data provenance" section (see §6).
2. Snapshot the token_economy store (`uv run python scripts/internal/ops.py
   usage status`) as the pre-window reference point. Record the SHA-256 of
   `<.claude/runtime/token_economy/session_usage.jsonl>` and
   `<.claude/runtime/token_economy/session_attributions.jsonl>`.
3. Pre-register the threshold numbers in §4 and §5 **before** `T_start`.
   These numbers must appear in a committed update to this file (or a
   companion thresholds file) before the window opens. Any change after
   `T_start` is a protocol violation and resets the window.

---

## 2. Data Sources

The evaluation consumes only these artifacts. All are local to the repo
or to `~/.claude/`; no network calls. Exact paths are pinned so the
evaluation is reproducible from a clean machine.

The paths below use angle-bracket notation (e.g. `<path/to/file>`) for
artifacts that are **planned but not yet on disk** — they will be created
by Slices A/B/C/D/E PRs before this evaluation runs. Plain-backtick paths
are existing files in the repo.

| Input | Path | Produced by | Query |
|-------|------|-------------|-------|
| Token telemetry (raw) | `~/.claude/projects/*steward*/*.jsonl` | Claude Code runtime | Ingested via `usage import` |
| Token telemetry (normalized) | `<.claude/runtime/token_economy/session_usage.jsonl>` | Will add `usage import` (Slice A) | Read via `token_economy.usage_summary` / `lane_summary` |
| Session attributions | `<.claude/runtime/token_economy/session_attributions.jsonl>` | Will add `usage attribute` (Slice A) | Joined on `session_id` for lane attribution |
| Event log | `.claude/runtime/events/events.jsonl` | `src/bid_euchre/ops/events.py` | Grep/jq for `task_completed` and `task_outcome_recorded` in window |
| Task outcome log (Slice C/D/E) | `<.claude/runtime/learning/outcomes.jsonl>` | New file created by SP-5-02 PR2 `OutcomeLogger` | Filter by completion timestamp in window; group by lane × task_type × model_hint × effort_hint |
| Advisor affinity snapshot | `<.claude/runtime/learning/lane_affinity.json>` | New file created by SP-5-02 PR2 `AffinityModel` | Read post-window for final state; snapshot pre-window for drift |
| Advisor recommendation log | `<.claude/runtime/learning/recommendations.jsonl>` | New file created by SP-5-02 PR3/PR4 (Slice E shadow log) | Match `recommendation_id` → actual `selected_lane` → outcome record |
| GitHub PR merge data | `gh pr list --state merged --search "merged:>=<T_start>"` | GitHub | Join on branch or PR number to find owning task packet |
| Review round count | `<.claude/runtime/review_loops/pr_<N>/state.json>` + `<.claude/runtime/review_loops/pr_<N>/verdict.json>` | `scripts/internal/review_driver.py` | Count rounds; cross-check with PR comment history |
| Task packet archive | `.claude/runtime/task_queue/*` | `src/bid_euchre/ops/task_queue.py` | Resolve packet metadata (task_type, complexity_estimate, model_hint, effort_hint) per outcome |

### 2.1 Known gaps (verify on-dispatch, before running)

These are asserted below but must be **verified** when the evaluation is
actually dispatched (because Slices C/D/E have not landed as of this
draft):

- ⬛ **Slice C:** the new `<.claude/runtime/learning/outcomes.jsonl>` file
  actually carries `model_hint`, `effort_hint`, `task_type`,
  `complexity_estimate`, and joins to token spend.
- ⬛ **Slice D:** A `dispatch_policy_applied` audit record per packet exists
  so we can measure coverage without re-inferring from heuristics.
- ⬛ **Slice E:** the new `<recommendations.jsonl>` file exists, includes a
  ranked lane list per decision, and emits an `advisor_override` flag when
  the orchestrator picked a lane other than rank-1.
- ⬛ Outcome records include enough fields to reconstruct tokens/PR, review
  rounds, and outcome class (shipped / set-aside / reverted).

If any of these is missing at evaluation time, the evaluation **halts** and
returns a NO-GO on data contract, with follow-up to patch Slice C/D/E
rather than retro-fit the eval.

### 2.2 Query fragments per decision question

The eval runner is not in scope here, but query skeletons are pinned so
the evaluator can execute them verbatim:

- **Q1 tokens/merged-PR:**
  - Pull `<session_usage.jsonl>` + `<session_attributions.jsonl>` in window.
  - Sum `cache_read + output` tokens per `lane_id`, normalize by count of
    `merged_at in window` PRs attributable to that lane.
  - Bootstrap median (n=10000, seed=42) and report 95% CI.
- **Q2 review churn:**
  - For each merged PR in window, count review rounds from
    `<.claude/runtime/review_loops/pr_<N>/state.json>`.
  - Compute rework rate as `reverts_within_7d + followup_fix_prs /
    merged_in_window`.
- **Q3 downgrade coverage:**
  - Group outcome records by `task_type`; for each low-risk class, compute
    `% where effective_model != "opus-4-6"` and
    `% where effort_hint in {"medium", "low"}`.
  - Mis-classification audit: operator reviews a random sample of 10
    packets per low-risk class and flags any that should NOT have been
    downgraded. Flag rate is the mis-classification rate.
- **Q4 advisor predictiveness:**
  - For each decision in `<recommendations.jsonl>`, find the outcome of the
    realized lane. Compute Spearman ρ between advisor rank and a
    post-hoc "clean merge yes/no + token-efficiency tier" outcome score.
  - Also compute top-1 accuracy: was the advisor's rank-1 lane the lane
    that would have produced the best observed outcome? (Requires
    counterfactual reasoning, so only report for task_types where ≥ 2
    lanes have observations; otherwise not applicable.)

---

## 3. Decision Question Framework — Operationalized

Each decision question becomes a **metric**, a **comparison**, a
**confidence expression**, and a **pre-committed directional threshold**.
Exact threshold numbers live in §4.

### Q1 — Did tokens per merged PR improve?

- **Metric:** Median of (`cached_input_tokens + output_tokens`) per merged
  PR, computed per lane-pool (author, analyst, browser, flex, control).
- **Comparison:** In-window median vs Slice-A baseline median
  (`plans/sessions/2026-04-20_token_economy_baseline_refresh.md`), by
  lane-pool.
- **Confidence:** 95% bootstrap CI (n=10000 resamples, seed=42) on the
  delta. CI, not p-value — see rigor caveat.
- **Direction:** Improvement = reduction. A negative delta with
  95% CI fully below zero is the strong case; a negative point estimate
  with CI crossing zero is the qualitative-only case.
- **Non-regression constraint:** No lane-pool may have its CI fully above
  zero (regression). If any pool regresses clearly, overall Q1 = "FAIL".

### Q2 — Did review churn / rework get worse?

- **Metric A:** Review rounds per merged PR (from review coordinator
  state). Mean and median, per lane-pool.
- **Metric B:** 7-day rework rate: count of revert or follow-up "fix"
  PRs referencing an in-window merge, divided by in-window merge count.
- **Comparison:** vs pre-window baseline (last 30 days before `T_start`,
  same metric definitions).
- **Confidence:** Bootstrap CI on the deltas (same recipe as Q1).
- **Direction:** No change or reduction = pass. Increase = concerning.
- **Rollback trigger:** See §5.

### Q3 — Are model downgrades correctly applied per class?

- **Metric A (coverage):** For each low-risk task_type, % of in-window
  packets where lane-default or task-override actually picked a cheaper
  model/effort. Low-risk classes (per restart plan §Slice D): ops
  monitoring, review coordination, docs-only tasks, test-only tasks,
  convention fixes.
- **Metric B (mis-classification):** Operator-reviewed sample of 10
  packets per low-risk class; flag rate of "should have used higher
  effort/model."
- **Comparison:** Coverage is a raw percentage; no baseline required (the
  baseline is zero, because Slice D is the first time any downgrading
  occurs). Mis-classification is judged against an absolute threshold.
- **Confidence:** Coverage is reported with Wilson 95% CI. Mis-classification
  is a raw proportion with exact binomial CI; sample too small for
  bootstrap.
- **Direction:** Higher coverage + lower mis-classification = better.

### Q4 — Is the advisory scorer predictive enough?

- **Metric A (rank correlation):** Spearman ρ between advisor rank order
  of lanes and realized outcome ordering (clean-merge + token-efficiency
  composite) for decisions where ≥ 2 candidate lanes had observations.
- **Metric B (top-1 hit rate):** % of decisions where the advisor's
  rank-1 lane matched the lane that produced the best realized outcome
  (among candidates that had data).
- **Comparison:** Against a **random-baseline** ρ (expected 0) and a
  **round-robin top-1** hit rate (1 / #candidates per decision).
- **Confidence:** Permutation test at n=10000 for the rank correlation;
  95% Clopper–Pearson CI on top-1 hit rate. Both reported alongside the
  sample size; we explicitly do **not** claim significance below N=20.
- **Direction:** Advisor predictive only if both ρ and top-1 hit rate
  exceed random/round-robin baselines by the pre-committed margin.

---

## 4. Pre-Committed Decision Thresholds

These numbers are the protocol's **decision rule**. They are
intentionally separable from the interfaces locked in SP-5-02 so that
operator + analyst can tune them based on data volume, fleet state, and
risk tolerance at dispatch time.

**Status:** not yet locked. Must be finalized in a committed update to
this file **before** `T_start`. Current recommendations (to be reviewed
by operator):

| # | Threshold variable | Recommended | Rationale |
|---|--------------------|-------------|-----------|
| Q1-T1 | Author-pool tokens/merged-PR delta | ≤ −10% point estimate AND 95% CI upper bound ≤ 0 | 10% is the minimum detectable effect at N ≈ 30; looser than the 25-35% claim in #2159 by design |
| Q1-T2 | Any pool regresses? | If any pool's 95% CI is fully > 0 → FAIL | Non-regression constraint |
| Q2-T1 | Review rounds/PR delta | ≤ +0.2 rounds point estimate; 95% CI upper ≤ +0.5 | Allows normal noise; blocks large regression |
| Q2-T2 | 7-day rework rate delta | ≤ +3 percentage points | Above this, Slice D is plausibly making things worse |
| Q3-T1 | Coverage on low-risk classes | ≥ 70% per class | Below this, Slice D isn't actually changing behavior enough to matter |
| Q3-T2 | Mis-classification flag rate | ≤ 10% | Operator-judged; 1 out of 10 sampled packets is the ceiling |
| Q4-T1 | Advisor Spearman ρ | ≥ 0.3 with N ≥ 20 decisions | Rank correlation at steward scale; not a confidence claim |
| Q4-T2 | Advisor top-1 hit rate delta vs round-robin | ≥ +15 percentage points | Minimum visible advantage over random |

**If any threshold number above is changed after `T_start`:** protocol
violation; observation window resets.

---

## 5. Rollback Criteria — Operationalized

The restart plan specifies three rollback triggers. Each is made
checkable below. **Any one** triggers an immediate ROLLBACK
recommendation, regardless of Q1–Q4 outcomes.

### R1 — CRITICAL post-merge review finding attributed to D/E behavior

- **Checkable condition:** During the window, any post-merge review
  (`.claude/hooks/post-merge-review.sh` output) surfaces a CRITICAL severity finding
  **and** the finding's root cause is attributable to a Slice D/E
  behavior change (e.g., a downgrade to Sonnet produced a logic bug that
  was not caught in review). Attribution is **operator-judged**, with
  named transcript evidence cited in the eval report.
- **Action:** ROLLBACK. File an immediate issue with label `rollback` +
  `fix:bug`; revert Slice D/E policy PRs; preserve outcome log for
  forensic analysis.

### R2 — PR merge rate drops > 30%

- **Checkable condition:** Window PR merge rate vs previous-30-day rate,
  per lane-pool. If author-pool merge rate drops > 30% OR fleet-wide
  merge rate drops > 30%, trigger.
- **Metric:** `merged_in_window / active_calendar_days` vs
  `merged_in_prior_30d / 30`.
- **Confidence:** Report the delta with Poisson 95% CI on merge count.
  If the point estimate is > 30% and the CI lower bound is > 0
  (i.e., a real reduction, not noise), trigger.
- **Action:** ROLLBACK. File an issue with label `rollback` +
  `fix:process`; disable Slice D lane defaults and Slice E advisor call
  site; re-run measurement to confirm recovery.

### R3 — Operator judgment with named transcript evidence

- **Checkable condition:** Operator reviews tmux transcripts and cites
  at least one specific incident where Slice D or E behavior caused
  visible harm (wrong lane dispatched, repeated rework, confusing
  recommendation). The evidence must be reproducible — link to a
  specific pane capture, log line, or PR.
- **Action:** ROLLBACK if operator elects. This is intentionally
  subjective; the protocol does not pretend this is a quantitative
  trigger.

### Rollback precedence

If a rollback trigger fires, the per-question verdicts are still
computed and reported — they are not suppressed — but the overall
recommendation is ROLLBACK regardless of Q1–Q4.

---

## 6. Artifact Shape — Eval Report

When the evaluation runs, the output report lives at:

**Path:** `plans/sessions/2026-04-20_token_economy_restart_eval.md`
(this file, amended in place — the final "executed" version of the
protocol and its results).

Alternative: if the evaluator prefers to keep this file as the protocol
and publish the verdict separately, create a new dated report file
`<plans/sessions/YYYY-MM-DD_token_economy_restart_eval_report.md>`
(dated to the execution date), and cross-link both ways.

### Required sections (in order)

1. **Data provenance** — window bounds, Slice C/D/E merge SHAs,
   token_economy store SHA-256s pre-window and post-window, outcomes.jsonl
   row count delta, fleet activity summary.
2. **Thresholds applied** — copy of the §4 table with the numbers
   actually in effect, plus the commit SHA in which they were locked
   before `T_start`.
3. **Per-question verdict** — one subsection per Q1–Q4 with:
   - Metric value(s) and 95% CI / exact-binomial CI
   - Threshold check result
   - Qualitative vs quantitative label (see §7)
4. **Rollback trigger check** — explicit pass/fail for R1–R3 with
   supporting evidence or explicit "no trigger fired."
5. **Overall recommendation** — one of:
   - **PROMOTE** — all pass-gates hit, no rollback trigger, consider
     expanding lane defaults to include complex implementation classes.
   - **HOLD (retain as-is)** — mixed or insufficient signal; keep
     Slice D/E as shipped; re-evaluate in 7–14 days.
   - **ROLLBACK** — any rollback trigger fires, or multiple Q1–Q4
     thresholds fail.
   - **NO-GO on data** — window floors not met at ceiling; no
     recommendation, file follow-up.
6. **Operator notes** — transcript evidence, qualitative observations,
   callouts of "we are NOT claiming statistical significance here."
7. **Follow-up issues** — GitHub issues filed as a result (rollback,
   threshold-tuning, data-contract gaps).

### Reproducibility requirements

- **Seeds:** bootstrap and permutation tests must use `seed=42` unless a
  deviation is recorded in "Data provenance."
- **Queries:** every number in the report must be reproducible by re-running
  the query skeletons in §2.2 against the artifact hashes recorded in
  "Data provenance." If the artifact hash shifts (new sessions, new
  outcomes), the report is re-runnable but the numbers may drift; the
  original committed report retains the original hash and numbers.
- **Artifact capture:** at the end of the evaluation, copy
  `<outcomes.jsonl>`, `<session_usage.jsonl>`, `<session_attributions.jsonl>`,
  `<recommendations.jsonl>`, and the review-loop state files for in-window
  PRs into a new committed artifact tarball under `data/fixtures/eval_slice_f/`
  (tiny — only the in-window slice, gitignore otherwise). Per
  `.claude/rules/deferred/30_data_contract.md`, only `data/fixtures/` is
  committable.

---

## 7. Statistical Honesty

Per `.claude/rules/deferred/05_rigor.md` and
`.claude/rules/deferred/45_notebook_boundary.md`, this protocol
explicitly labels each claim:

| Claim | Type | Why |
|-------|------|-----|
| "Tokens/PR decreased by X% with 95% CI [a, b]" | **Quantitative, exploratory** | Bootstrap CIs at N ≈ 30 are wide; we report them as effect-size + uncertainty, **not** p-values |
| "Author-pool improvement is not confounded with ..." | **Qualitative** | At this sample size we cannot rule out confounders; we can only name them and note they were stable in window |
| "Mis-classification rate is 2/10 on docs-only" | **Quantitative** | Operator count with binomial CI |
| "Advisor is predictive (ρ = 0.35, N = 22)" | **Quantitative, exploratory** | Permutation test gives a p-value, but we explicitly avoid claiming "statistically significant" unless N ≥ 50 in that task_type; we report the number and call it exploratory |
| "Operator saw a specific harmful dispatch (transcript X)" | **Qualitative** | Single-case evidence; sufficient for R3 rollback, not for a population claim |
| "Review rounds increased by 0.1" | **Quantitative, likely-noise-band** | At this N, 0.1 rounds/PR is within expected noise; we name the point estimate but do not claim a real effect |

**Explicit statement in the eval report:** "This evaluation is
exploratory. We make **no claim of statistical significance** on Q1, Q2,
or Q4 at the fleet's current volume. Decisions rest on effect sizes,
confidence intervals, and named operator judgment. A decision to PROMOTE
is a decision under uncertainty, not a claim of proof."

---

## 8. Dispatch-Ready Package (for the evaluation run)

This is the packet the orchestrator will dispatch when the window closes.

| Field | Value |
|-------|-------|
| **Trigger condition** | All of: (a) Slice C/D/E PRs merged; (b) ≥ 7 calendar days since the last of those merges; (c) merge floor and lane coverage floor met per §1.3; (d) thresholds from §4 locked in a committed update |
| **Owner recommendation** | **analyst lane** (analyst-c or analyst-d). Ops lane has the monitor data but does not own statistical analysis; analyst lane is the right fit for bootstrap + operator-judgment write-up. If the analyst pool is saturated, a flex lane with a narrow `scope_declared` is acceptable. |
| **Delivery mode** | **PR mode** — amends this file in place (or adds companion report file per §6) |
| **scope_declared** | `plans/sessions/2026-04-20_token_economy_restart_eval.md` (amendments), optional new `<plans/sessions/YYYY-MM-DD_token_economy_restart_eval_report.md>`, and a new `data/fixtures/eval_slice_f/**` tarball directory with in-window slice data. **No `src/` changes** unless a query helper is needed, in which case it must be scoped to `src/bid_euchre/ops/token_economy.py` or the new SP-5-02 module `<src/bid_euchre/ops/learning.py>` with tests. |
| **Validation commands** | ```bash
uv run python -m pytest tests/unit/test_token_economy.py tests/unit/test_ops_learning.py -v
uv run python scripts/internal/ops.py usage status
uv run python scripts/internal/ops.py usage reconcile
make check-gated
``` |
| **Suggested PR title** | `docs(ops): token economy Slice F — evaluation results and promote/hold/rollback recommendation` |
| **Suggested branch name** | `analyst/slice-f-eval-results` |
| **PR body must include** | (a) the §6 required sections; (b) a link to the §4 threshold-lock commit; (c) the window bounds and merge SHAs; (d) the overall recommendation with one-sentence justification; (e) `Refs #2169` (not `Fixes`) — umbrella stays open until follow-on waves are done, per `.claude/rules/deferred/55_issue_closure.md` |
| **Known risks / scope traps** | (i) Tempting to re-tune thresholds after seeing the data — forbidden per §4. (ii) Tempting to claim significance — forbidden per §7. (iii) Mixing Slice D coverage and Slice E advisor quality in a single verdict — each question gets its own verdict. (iv) Running the evaluation before floors are met — should return NO-GO on data, not a speculative PROMOTE. (v) Forgetting to snapshot artifact hashes — evaluation is then unreproducible and must be rerun. |

---

## 9. Out of Scope

Per the shaping task packet, this document explicitly does **not**:

- Run the evaluation (data does not yet exist; Slices C/D/E must land
  first, and the observation window must elapse).
- Lock the exact threshold numbers in §4 without operator sign-off — the
  recommendations are proposed, not final, per SP-5-02's deliberately
  unlocked scoring weights.
- Re-scope Slice D or Slice E — those are governed by SP-5-02.
- Change the measurement path from Slice A or the telemetry extension
  from Slice B.
- Commit to running a post-promotion monitoring loop — that is a
  follow-up plan if and only if the recommendation is PROMOTE.

---

## 10. Handoff

When this draft is approved and merged:

1. The document lives as the **pre-registered protocol** until evaluation
   time. `T_start` must not precede (a) Slice C/D/E merges, (b) the
   §4 threshold-lock commit.
2. The orchestrator tracks Slice C/D/E completion and, when §1.3 floors
   look reachable, dispatches the evaluation packet described in §8.
3. Until then, a comment on #2169 linking this file documents that Slice
   F shaping is complete and is waiting on D/E data.

## Outcome

_To be filled when the evaluation runs. Suggested template:_

- **Window:** `T_start=<ISO8601>`, `T_end=<ISO8601>`
- **Slice merge SHAs:** C=`<sha>`, D=`<sha>`, E=`<sha>`
- **Threshold-lock commit:** `<sha>`
- **Fleet activity:** `<N>` merged PRs, `<M>` active lanes, `<K>` outcome records
- **Verdicts:** Q1 `<PASS|FAIL|INCONCLUSIVE>`, Q2 `<...>`, Q3 `<...>`, Q4 `<...>`
- **Rollback triggers:** R1 `<no|yes — evidence>`, R2 `<...>`, R3 `<...>`
- **Overall recommendation:** `<PROMOTE|HOLD|ROLLBACK|NO-GO>`
- **Follow-up issues:** `#<n>, #<n>`
