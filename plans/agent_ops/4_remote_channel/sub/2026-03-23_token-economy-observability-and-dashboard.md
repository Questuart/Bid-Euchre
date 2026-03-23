# Token Economy Observability And Dashboard

**ID:** SP-4-03
**Date:** 2026-03-23
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Pre-Platform-8
**Status:** proposed
**Owner:** orchestrator

---

## Problem Statement

The orchestration platform is now capable of sustained multi-lane throughput, but
the repo does not yet have a repo-owned view of token economy. Claude usage data
exists locally under `~/.claude/usage-data/`, but it is not imported into repo
runtime state, joined to packets/PRs/lanes, or surfaced in the steward
dashboard. As a result:

- token-heavy anti-patterns are anecdotal instead of measurable
- throughput improvements cannot be compared against token burn
- Phase 4 remote work would begin without a local-vs-remote baseline
- operators cannot see whether a lane is productive or simply verbose

This sub-plan adds token-economy observability first. It does **not** optimize
token usage blindly before a baseline exists.

## Recommendation

Implement token-economy **measurement and dashboards now**, before
Platform-8 transport work, but defer policy/optimization changes until the
baseline report identifies the worst inefficiencies.

## Scope

This sub-plan covers:

- importing native Claude usage telemetry into repo-owned runtime state
- correlating usage with lanes, task packets, PRs, and merges
- defining throughput-normalized token metrics
- exposing token-economy views in CLI/dashboard surfaces
- producing one baseline report with anti-pattern findings

This sub-plan does **not** cover:

- changing model/provider selection policy
- prompt compression rewrites across all lanes
- transport-level token reduction features for Phase 4
- forcing lane behavior changes before the baseline is established

## Existing Inputs

Current local data sources already available:

- `~/.claude/usage-data/session-meta/*.json`
  - `input_tokens`
  - `output_tokens`
  - `duration_minutes`
  - `tool_counts`
  - `git_commits`
  - `git_pushes`
  - `lines_added`
  - `lines_removed`
  - `files_modified`
  - `project_path`
- `~/.claude/usage-data/facets/*.json`
  - qualitative session outcome and friction metadata
- repo runtime state:
  - `.claude/runtime/task_queue/`
  - `.claude/runtime/message_bus/`
  - `.claude/runtime/events/`
  - `.claude/runtime/worktree_registry/`

## Approach

Make token economy queryable before attempting optimization:

1. Import native local usage data into repo-owned runtime state
2. Normalize lane/worktree/session attribution
3. Join usage with throughput outcomes
4. Surface dashboard and CLI views
5. Produce a baseline anti-pattern report
6. Only then decide what optimization work is worth doing

## Implementation Contract

To reduce interpretation error, this sub-plan is locked to the following:

- Reuse native local usage files as the primary source.
- Do **not** scrape model output text to estimate tokens if native usage data is
  available.
- Create a repo-owned normalized runtime surface under:
  - `.claude/runtime/token_economy/`
- Keep the first version read-mostly:
  - importer
  - rollups
  - dashboard/CLI
  - baseline report
- Do **not** gate normal execution on token metrics in v1.
- Do **not** make token budgets a dispatch-time blocker in v1.
- Dashboard work in this sub-plan means:
  - steward/ops dashboard surfaces
  - PR/commit analytics enrichment where clearly compatible
  - not a separate competing dashboard stack

## Metrics To Define

The baseline must include at least:

- tokens per completed packet
- tokens per merged PR
- tokens per net line changed
- tokens per hour by lane
- output/input token ratio
- assistant messages per user message
- tool errors per 1k tokens
- retry or re-dispatch cost per completed task
- abandoned-work cost
  - tokens spent on duplicate/closed/abandoned work
- work-type efficiency
  - planning vs review vs implementation vs monitoring

## Anti-Patterns To Detect

The baseline report must explicitly evaluate:

- verbosity waste
  - high output tokens with low shipped change
- planning/doc overproduction
  - large token spend with little or no runtime/code throughput
- retry churn
  - repeated dispatches/reviews/recovery cycles for the same outcome
- context carryover tax
  - repeated work in stale sessions vs reset/clear lanes
- read amplification
  - repeated reads relative to files actually changed
- failure tax
  - high tool-error cost for low output
- fragmentation
  - too many tiny sessions or handoffs for one work item

## Steps

### Step 1: Import native usage data into repo runtime

**Goal:** Create a durable repo-owned normalized usage store.

**Method:**
- Read from:
  - `~/.claude/usage-data/session-meta/*.json`
  - `~/.claude/usage-data/facets/*.json`
- Normalize into (created by this sub-plan):
  - `.claude/runtime/token_economy/session_usage.jsonl` (new)
  - `.claude/runtime/token_economy/session_rollups.json` (new)
- Preserve source identifiers so imports are idempotent
- Record import timestamp and source path/hash

**Validation:**
- Re-running the importer does not duplicate sessions
- Imported session count matches the number of distinct native source sessions

**Files likely touched:**
- `src/bid_euchre/ops/` (new token-economy module)
- `scripts/internal/ops.py`
- `tests/unit/` (new importer tests)

### Step 2: Attribute usage to lanes and work outcomes

**Goal:** Make usage data operationally meaningful.

**Method:**
- Infer lane/worktree class from `project_path`
- Join sessions to:
  - task packets
  - PRs
  - merges
  - lines changed
  - lane identity
- Handle imperfect attribution explicitly:
  - `attributed`
  - `partially_attributed`
  - `unattributed`

**Validation:**
- Known steward worktrees map to the expected lane IDs
- Sample merged packets can be traced to at least one usage session

### Step 3: Add CLI summaries

**Goal:** Make token economy inspectable without opening raw files.

**Add CLI views:**
- `ops.py usage summary`
- `ops.py usage lanes`
- `ops.py usage throughput`
- `ops.py usage anti-patterns`

**Validation:**
- CLI works against imported data with no dashboard dependency
- CLI output is stable enough for operator use and future monitor integration

### Step 4: Add dashboard surfaces

**Goal:** Surface token economy in the existing operator dashboards.

**Scope:**
- extend `ops.py dashboard` / dashboard JSON with token-economy sections
- add lane-level efficiency indicators
- add aggregate throughput-vs-token panels
- include a compatible enrichment path for existing PR/commit analytics

**Required dashboard views:**
- top expensive lanes
- cheapest productive lanes
- tokens per merged PR trend
- tokens per completed packet trend
- abandoned-work cost
- planning/review/implementation token mix

**Constraint:**
- Do not create a second primary supervision dashboard in v1.
- Extend the existing dashboard-first operator surface.

**Validation:**
- `ops.py dashboard --json` includes token-economy sections
- token fields are absent or null-safe when no usage data is imported

### Step 5: Produce baseline report and optimization shortlist

**Goal:** Turn observability into a concrete optimization agenda.

**Deliverable:**
- one baseline report under `plans/sessions/` or another agreed repo-owned path
- list the top 3 token-waste patterns with evidence
- recommend which optimizations should become later platform work

**The report must answer:**
- which lanes are most expensive per useful outcome?
- which work types have the worst token efficiency?
- what percentage of token spend is attached to shipped output vs churn?
- where are the highest-leverage fixes?

## Exit Criteria

Before using token-economy work to change behavior:

- [ ] Native Claude usage data is imported into repo-owned runtime state
- [ ] Session imports are idempotent
- [ ] Steward worktrees can be attributed to lane identities with acceptable accuracy
- [ ] `scripts/internal/ops.py` exposes token-economy summary/throughput/anti-pattern views
- [ ] Existing dashboard surfaces include token-economy information
- [ ] A baseline report identifies the top 3 token-waste patterns
- [ ] At least one correlation to shipped throughput exists:
      tokens per completed packet or tokens per merged PR

## Rollout Order

1. Importer and normalized store
2. Attribution and joins
3. CLI views
4. Dashboard views
5. Baseline report
6. Separate optimization planning after the baseline

## Estimated Effort

| Step | Effort | Lane Count |
|------|--------|------------|
| Step 1 | 1 PR | 1 lane |
| Step 2 | 1 PR | 1 lane |
| Step 3 | 1 PR | 1 lane |
| Step 4 | 1-2 PRs | 1 lane |
| Step 5 | 1 doc/report PR | 1 lane |
| **Total** | **4-6 PRs** | **Mostly sequential** |
