# Post-PR-5 Follow-On Roadmap

**Created:** 2026-03-19
**Context:** Potential follow-on work after the autonomous operator stack lands
through PR-5. This document tracks optional future directions so they can be
revisited later without reopening the governing plan.

These ideas are intentionally exploratory. None are committed, scheduled, or
prioritized by this document alone.

---

## Purpose

This roadmap captures two distinct but related follow-on tracks:

1. Improving the operator infrastructure after the current autonomous workflow
   plan lands.
2. Building the research control loop needed for autonomous improvement of
   bidding and play strategies.

The goal is to keep those ideas visible without mixing them into the current
PR-1 through PR-5 execution plan.

---

## Working Assumptions

- PR-1 through PR-5 establish the operational substrate:
  steward lanes, repo-owned state, `ops.py`, watchdogs, retry/reroute logic,
  audit index, and rollout validation.
- Future work should prefer building on stable repo-owned primitives rather
  than introducing a new framework at the base layer.
- Autonomous improvement should be conservative about promotion and aggressive
  about evidence.
- A system that can generate candidate ideas is not yet a system that can
  safely self-improve. The gatekeeping and evaluation layers matter more than
  the idea generator.

---

## Track A: Post-PR-5 Infrastructure Paths

### 1. Operational Maturity Layer

Turn the operator stack from "works" into "operates reliably."

Potential work:

- issue triage agent plus GitHub Project routing
- incident and SLO model for agent infrastructure
- recurring health reports
- soak gates before new automation becomes default
- automatic postmortems for retry-cap or watchdog incidents

Why it helps:

- makes failures visible and durable
- reduces silent degradation
- creates a real operating model instead of a pile of tools

Best if:

- confidence and auditability matter more than adding new capabilities

### 2. Full End-to-End Testbed

Build a true integration harness for the autonomous stack.

Potential work:

- one command that simulates:
  - lane startup
  - task assignment
  - heartbeat and progress updates
  - CI failure
  - retry and reroute
  - issue creation
  - recovery after interruption
- chaos tests for:
  - killed tmux session
  - corrupted runtime file
  - stale index
  - missing hook output
  - duplicated events

Why it helps:

- directly addresses the "looks good in review, flaky in use" failure mode
- catches seam failures that unit tests miss

Best if:

- reliability is the top priority

### 3. Operator Control Plane UI

Add a lightweight dashboard on top of `ops.py`, events, and the audit index.

Potential work:

- web UI or TUI for:
  - lane state
  - active tasks
  - watchdog findings
  - CI and review status
  - retry and escalation queue
  - recent events and issues
- drill-down into source-backed artifacts

Why it helps:

- lowers operator overhead
- makes the system easier to supervise than terminal output plus JSON files

Best if:

- the workflow is going to be used as a daily operating surface

### 4. Policy Engine / Machine-Readable Governance

Move more workflow rules out of prose and into enforceable config.

Potential work:

- machine-readable lane policies
- machine-readable escalation triggers
- command and ownership rules compiled from policy files
- policy linting in CI
- workflow contract checks for plans, handoffs, and PRs

Why it helps:

- reduces drift between docs and behavior
- makes future agents less dependent on interpreting prose correctly

Best if:

- the system needs to scale across many agents and many PRs

### 5. Smarter Orchestration / Capacity-Aware Scheduling

Evolve `ops` from a watchdog and scheduler into a workload manager.

Potential work:

- task dependency graph
- lane capacity and specialization
- priority queue with WIP limits
- blocked-task rerouting
- "do not start until dependency PR merges" rules
- issue-to-task queue integration

Why it helps:

- makes parallelism more intentional
- prevents too many active tasks and scattered work

Best if:

- higher multi-agent throughput is the main goal

### 6. Knowledge Layer on Top of the Audit Index

Use the audit index as a retrieval substrate for higher-level reasoning.

Potential work:

- source-backed operational Q&A
- recurring summaries
- incident clustering
- "what usually fixes this failure class?"
- memory-promotion suggestions from repeated patterns
- optional LangChain or similar on top of stable primitives later

Why it helps:

- improves decision speed
- turns raw history into reusable knowledge

Best if:

- the team wants better reuse and less repeated diagnosis

### 7. Stronger Runtime Isolation

Push the execution model beyond worktrees and tmux.

Potential work:

- per-lane containers or sandbox profiles
- stricter secret and environment isolation
- per-lane resource limits
- reproducible lane environments
- safer experimentation and cleaner cleanup

Why it helps:

- reduces cross-lane contamination
- makes failures easier to contain and reproduce

Best if:

- the repo becomes more production-like or handles sensitive workflows

### 8. Experiment / Artifact Lineage Unification

Unify research outputs and agent-ops outputs into one lineage model.

Potential work:

- connect rung runs, reports, CI, PRs, issues, and agent sessions
- explicit provenance graph
- answer questions like:
  - which code change produced this report?
  - which incident led to this fix?
  - when was a skill or memory entry promoted?

Why it helps:

- strengthens reproducibility and historical reasoning
- fits this repo especially well because research and agent infrastructure are
  tightly related

Best if:

- provenance and historical traceability matter heavily

### Suggested Order for Track A

If PR-1 through PR-5 land cleanly, the most defensible order is:

1. full end-to-end testbed
2. operational maturity layer
3. policy engine / machine-readable governance
4. smarter orchestration / capacity-aware scheduling
5. operator control plane UI
6. knowledge layer
7. stronger runtime isolation
8. experiment / artifact lineage unification

This order prioritizes:

- reliability first
- governance second
- throughput third
- convenience and higher-level reasoning later

---

## Track B: Autonomous Strategy Self-Improvement

### Goal

Set the repo up so research can autonomously improve bidding and play
strategies without relaxing determinism, evaluation discipline, or promotion
safety.

This is primarily a research control-loop problem. The important question is
not "can an agent generate candidate changes?" but "can the repo safely detect
weaknesses, generate bounded candidates, evaluate them rigorously, and promote
only the right ones?"

### Core Self-Improvement Loop

The desired loop is:

1. detect where current bidding or play is weak
2. generate bounded candidate improvements
3. evaluate candidates against trusted benchmark ladders
4. compare them against the current champion with strong gates
5. promote only if they improve without unacceptable regressions
6. archive evidence so the next cycle starts from better context

### Design Principles

1. The generator can be creative; the promotion gate must be conservative.
2. Aggregate metrics are never enough by themselves.
3. Every autonomous promotion path must be reproducible from committed code,
   committed configs, and fixed seeds.
4. Bidding and play should be improved as modular components, not as one
   opaque monolith.
5. Early self-improvement should prefer parameter tuning and bounded strategy
   variation over unrestricted code invention.

### Infrastructure Needed for Safe Self-Improvement

#### 1. Frozen Benchmark Ladder

Maintain distinct benchmark layers such as:

- smoke suite
- fast-rank suite
- promotion suite

Every evaluation should facet by at least:

- contract type
- seat
- role
- opponent pool
- partner pool

The promotion path should never rely on a single aggregate score.

#### 2. Structured Weakness Mining

Automatically extract repeated failure patterns such as:

- bad bid decisions by hand shape or auction context
- bad trick-play decisions by trick context or card pattern
- contract-specific regressions
- seat-specific weaknesses

Repeated weakness clusters should become research tasks or issues rather than
being rediscovered manually.

#### 3. Decision-Trace Capture

For both bidding and play, store source-backed decision traces that record:

- relevant state features
- candidate actions
- chosen action
- estimated value or rank
- downstream outcome

Decision traces are the raw material for autonomous diagnosis, weakness
mining, and future learned helpers.

#### 4. Parameterized Strategy Surface

Move more bidding and play behavior into explicit, tunable surfaces:

- thresholds
- feature weights
- routing rules
- module toggles
- candidate policy specs

Autonomous improvement is much safer when it can mutate structured knobs or
candidate modules instead of rewriting arbitrary code.

#### 5. Champion / Challenger Workflow

Maintain:

- one current champion
- bounded challengers
- a regression pool of prior strong strategies and opponent types

Candidates should only promote if they beat the champion on the promotion
suite and avoid major slice regressions.

#### 6. Search Infrastructure

Support bounded search over candidate improvements such as:

- grid search
- random search
- Bayesian search
- evolutionary search

This search infrastructure should be seed-controlled, budgeted, and able to
run in parallel safely.

#### 7. Conservative Promotion Gate

The promotion gate should be harder than the candidate-generation loop.

Promotion should require:

- uplift on primary performance metrics
- no catastrophic regression by contract type
- acceptable compute and latency cost
- deterministic reproducibility
- stability across seeds and evaluation pools

#### 8. Auto-Generated Research Reports

Every candidate cycle should be able to produce a report that answers:

- what changed
- why it was tried
- what improved
- what regressed
- whether promotion is justified

### Practical Paths for Autonomous Improvement

#### Path 1: Heuristic Autotuning

Expose bidding and play knobs, run automated sweeps, and promote only safe
parameter improvements.

Why start here:

- lowest operational risk
- easiest to audit
- naturally compatible with the repo's deterministic structure

#### Path 2: Hybrid Research Loop

Keep rule-based policy structure, but add learned helpers such as:

- bid prior model
- trick value estimator
- opponent inference model

These helpers should rank or advise decisions before they are allowed to
fully replace policy logic.

Why it is attractive:

- more upside than pure tuning
- still easier to govern than fully learned end-to-end play

#### Path 3: League-Based Self-Play Improvement

Maintain a pool of historical champions and specialist opponents. Candidates
train or tune against that pool and only promote when they beat both the
current champion and the regression pool.

Why it is attractive:

- strongest long-run upside
- helps avoid overfitting to one static baseline

Why it is risky:

- self-play can drift into unrealistic local optima
- failures are harder to interpret

### Biggest Risks to Guard Against

- reward hacking against narrow benchmarks
- overfitting to a fixed opponent pool
- regressions hidden by aggregate metrics
- self-play collapse into unrealistic strategies
- autonomous code changes outside intended scope
- experiment churn without promotion discipline
- compute budget blowups from unbounded search

### Suggested Order for Track B

The safest order is:

1. frozen benchmark ladder
2. parameterize current bidding and play policies
3. decision traces and weakness mining
4. heuristic autotuning and bounded candidate generation
5. conservative promotion gate
6. champion / challenger league
7. hybrid learned helpers
8. broader self-play and more aggressive autonomous search

This order aims to:

- make evaluation trustworthy before search becomes powerful
- keep early autonomous improvement auditable
- avoid learning loops that are difficult to diagnose too early

---

## Questions to Revisit After PR-5

These are good decision points once the current operator plan is complete:

1. Should the first follow-on investment prioritize reliability or strategy
   self-improvement?
2. Should autonomous promotion remain human-gated indefinitely, or only until
   the benchmark and promotion stack proves itself?
3. Should early self-improvement be limited to parameterized strategies before
   allowing structural code changes?
4. Should browser or human-play data become part of the autonomous loop, or
   stay out until the offline research loop is mature?
5. Should issue-triage and research-queue automation share one backlog system,
   or stay separate?

---

## Summary

After PR-5, the repo likely has two major opportunity spaces:

1. harden the operator stack so it is boring, reliable, and scalable
2. build a research control loop that can safely improve bidding and play
   strategies over time

The most important principle across both is the same: autonomous generation is
easy to add, but autonomous improvement only becomes trustworthy once the
evaluation, promotion, and provenance layers are stronger than the generator.
