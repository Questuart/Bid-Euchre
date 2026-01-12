# Repo Review + Cleanup + Docs + Roadmap Prompt (ZIP-based)

Last Updated: January 11, 2026 (post PR #81)

## ROLE

You are an engineering lead reviewing a Python card-game simulator repo (Bid Euchre / double-deck euchre). The repo is entirely created by AI agents. Your job is to:

1. Review the entire repo and the development to date (use PRs + commits as ground truth)
2. Propose and stage a repo cleanup plan (reduce clutter, consolidate structure, quarantine/deprecate safely)
3. Create and/or complete missing docs (some docs may be thin/empty/outdated)
4. Chart a roadmap from here (sequenced PRs, low risk, agent-friendly)

You MUST bias toward agent execution correctness and low-leak processes:
- Hard gates
- Determinism by default
- Reproducible experiments
- Clear "gold path" commands
- Strict boundaries (no imports across forbidden layers)
- No committed generated artifacts

---

## INPUTS

- You will be given a ZIP of the repo (treat ZIP contents as authoritative).
- Use PR history + commit history below as "archaeology hints," but do not invent details not present in the ZIP.
- If anything is unclear, explicitly say what you could not confirm and how to verify it.

---

## GROUND TRUTH: PR HISTORY (MERGED)

81 PRs total (January 5–11, 2026)

### Latest PRs (#76–81): Drift Pipeline Polish + Cleanup

| PR | Title | Theme |
|----|-------|-------|
| #81 | ci: polish drift workflow with actionable issue output | CI |
| #79 | feat: improve comparator output ergonomics | Feature |
| #78 | docs: fix DRIFT.md fixture schema example | Docs |
| #77 | docs: fix experiments/README.md config and suite lists | Docs |
| #76 | docs: delete empty placeholder docs | Cleanup |

### PRs #64–75: Drift Infrastructure + Fixture Stabilization

| PR | Title | Theme |
|----|-------|-------|
| #75 | ci: baseline_full drift workflow runs comparator (tricks-only) and ignores auction_smoke | CI |
| #74 | docs: align METRICS.md with emitted keys and drift v1 (tricks-only) | Docs |
| #73 | chore: populate baseline_full fixture and stabilize rollup JSON determinism (tricks-only drift) | Quality |
| #72 | docs: make worktrees default for parallel PR agents | Docs |
| #71 | ci: add scheduled baseline_full drift signal | CI |
| #70 | docs: tidy CODEBASE_CONSISTENCY tracking | Docs |
| #69 | docs: clarify experiments _deprecated guidance | Docs |
| #68 | docs: tighten archive guardrails | Docs |
| #67 | docs: make PR templates parallel-safe via git worktrees | Docs |
| #66 | ci: add scheduled baseline_full drift-signal workflow | CI |
| #65 | feat: emit win-rate metrics in results JSON and suite rollups | Feature |
| #64 | feat: add rollup drift comparator script + baseline_full fixture v0 | Feature |

### PRs #56–63: Baseline Full Suite + Metrics Contract

| PR | Title | Theme |
|----|-------|-------|
| #63 | docs: bulletproof PR prompt templates for gh auth + TLS + SSH remote | Docs |
| #62 | docs: bulletproof PR templates for gh TLS + SSH | Docs |
| #61 | feat: surface rollup metric parse failures in summary table | Feature |
| #60 | docs: define metrics contract v1 (win/points/tricks) | Docs |
| #59 | feat: add per-config metrics table to suite rollup | Feature |
| #58 | docs: add ARCHIVED banner to docs/archive/ | Docs |
| #57 | docs: fix training README false --config claim | Docs |
| #56 | feat: add baseline_full suite (matchup matrix) | Feature |

### PRs #46–55: Docs Cleanup + Hardening

| PR | Title | Theme |
|----|-------|-------|
| #55 | docs: resolve PR #49 revert impact and restore correct experiments docs | Docs |
| #54 | docs: consolidate and harden PR prompt templates (parallel-safe + auth gate) | Docs |
| #53 | docs: remove stale blockers from CODEBASE_CONSISTENCY | Docs |
| #52 | chore: quarantine non-runnable experiment configs | Cleanup |
| #51 | docs: remove 0-byte agent-doc footguns | Cleanup |
| #50 | docs: harden PR prompt templates for parallel agents | Docs |
| #49 | Revert "docs: fix experiments README stale refs" | Revert |
| #48 | docs: fix experiments README stale refs | Docs |
| #47 | docs: fix docs README legacy script ref | Docs |
| #46 | chore: quarantine stale experiments registry | Cleanup |

### PRs #39–45: Fixes, Linting, Docs Cleanup

| PR | Title | Theme |
|----|-------|-------|
| #45 | ci: fix ruff exclude to lint canonical runner and scripts | CI |
| #44 | docs: remove dead reporting commands from active docs | Docs |
| #43 | docs: align docs with current workflows (remove dead paths) | Docs |
| #42 | chore: lint runner and scripts (ruff coverage) | Quality |
| #41 | chore: remove .DS_Store from git tracking | Hygiene |
| #40 | fix: auction determinism under deal_seed + repeatability test | Bugfix |
| #39 | docs: clarify config precedence and effective-config snapshot | Docs |

### PRs #30–38: Scoring, Guards, and Hardening

| PR | Title | Theme |
|----|-------|-------|
| #38 | feat: runner validation hardening (fail fast) | Quality |
| #37 | test: add results JSON shape guard (baseline_tiny) | Testing |
| #36 | test: add scoring invariants guard (baseline_tiny) | Testing |
| #35 | docs: fix SCORING.md and DATA_CONTRACT.md ambiguity | Docs |
| #34 | docs: add scoring contract documentation | Docs |
| #33 | fix: auction smoke test verifies auction mode without requiring bids | Bugfix |
| #32 | feat: support auction scenarios (contract_type: null) in run_experiment | Feature |
| #31 | chore: remove .DS_Store and block via repo-lint | Hygiene |
| #30 | chore: fix report command footgun | Bugfix |

### Infrastructure Blitz (#19–29): CI, Determinism, Baseline

| PR | Title | Theme |
|----|-------|-------|
| #29 | feat: add points scoring aggregates to simulation results | Feature |
| #28 | chore: fix report generator command in run_experiment output | Bugfix |
| #27 | test: add baseline_tiny invariants fixture and CI guard | Testing |
| #26 | feat: add suite runner for baseline_tiny + rollup index | Feature |
| #25 | docs: define baseline + add baseline_tiny suite | Docs |
| #24 | test: add deterministic repeatability check | Testing |
| #23 | ci: block new scripts in experiments comparisons and training folders | CI |
| #22 | chore: delete quarantined experiment scripts | Cleanup |
| #21 | chore: quarantine legacy experiment scripts | Cleanup |
| #19 | chore: pre-commit hygiene sweep (whitespace/EOF/YAML) | Hygiene |

### Foundation (#1–18): Core Infrastructure

| PR | Title | Theme |
|----|-------|-------|
| #18 | feat: add per-run report generator entrypoint | Feature |
| #17 | feat: standardize run output layout and snapshot config | Feature |
| #16 | feat: require seed by default for deterministic runs | Determinism |
| #15 | ci: enforce data fixtures allowlist and size limits | CI |
| #14 | chore: remove tracked data artifacts | Cleanup |
| #13 | docs: define data layout and commit policy | Docs |
| #12 | docs: add meta.json schema v2 documentation | Docs |
| #11 | chore: add Makefile gold path and use in CI | Build |
| #10 | ci: add repo linter (artifacts, boundaries, deprecated) | CI |
| #9 | test: fix model test and xfail flaky perf test | Testing |
| #8 | ci: re-enable ruff linting with import sorting (I) | CI |
| #7 | feat: strengthen run meta.json contract (schema v2) | Feature |
| #4 | test: add engine invariants integration test | Testing |
| #3 | test: add golden seed smoke test | Testing |
| #2 | chore: add PR template (repro-first) | Process |
| #1 | ci: add Tier 1 pytest workflow | CI |

Closed (not merged): #6, #5 (conflicts; functionality in other PRs)

---

## RECENTLY FIXED (January 8–11, 2026)

The following issues were identified in earlier reviews and have been resolved:

| Issue | Fixed In | Verification |
|-------|----------|--------------|
| Auction determinism bug | PR #40 | Code now uses `random.Random(deal_seed + deal_id)` for deterministic dealer selection |
| .DS_Store tracked in git | PR #41 | `git ls-files \| rg -i ds_store` returns nothing |
| Ruff excludes runner/scripts | PR #42, #45 | `extend-exclude` now only excludes `["data/", "experiments/_deprecated/"]` |
| docs/README.md deprecated script refs | PR #43, #44, #47 | Removed `generate_all_reports.py`, `generate_dashboard.py`, `run_baseline_greedy.py` refs |
| experiments/README.md stale folder refs | PR #48, #55 | No longer references `analysis/`, `dashboards/`, `data_generation/`, `plotting/` |
| experiments/REGISTRY.yaml outdated | PR #46 | Moved to `_deprecated/`; replaced with `REGISTRY.md` pointing to configs/ |
| Empty docs (AI_PLAYBOOK.md, WORKPLAN.md) | PR #51 | Deleted 0-byte files |
| CODEBASE_CONSISTENCY.md stale blockers | PR #53, #70 | Removed stale "scoring system" blockers |
| Win-rate metrics missing | PR #65 | Added `win_rate_team0`, `win_rate_team1`, `tie_rate` to results JSON |
| Rollup drift comparator | PR #64, #73 | `scripts/compare_rollup.py` + `data/fixtures/baseline_full_expected.json` |
| CI drift detection workflow | PR #66, #71, #75 | `.github/workflows/baseline_full_drift.yml` runs daily |
| Empty placeholder docs (01_core/) | PR #76 | Deleted ROADMAP.md, SCHEMA_VERSIONING.md, STYLEGUIDE.md, TESTING_STRATEGY.md |
| Empty placeholder docs (root) | PR #76 | Deleted CHANGELOG.md, CONTRIBUTING.md |
| experiments/README.md outdated config list | PR #77 | Now lists all 10 active configs accurately |
| DRIFT.md schema vs fixture mismatch | PR #78 | Schema example now matches `data/fixtures/baseline_full_expected.json` |
| Comparator output not actionable | PR #79 | Improved formatting, shows expected/actual/delta, deterministic ordering |
| Drift workflow issue not readable | PR #81 | GitHub issues now include run metadata table, artifact links, comparison output |

---

## KNOWN ISSUES (still present as of January 11, 2026)

### ALL HIGH/MEDIUM PRIORITY ISSUES RESOLVED

As of PR #81, all previously tracked high and medium priority issues have been resolved:

- ✅ Empty placeholder docs deleted (PR #76)
- ✅ experiments/README.md config list accurate (PR #77)
- ✅ DRIFT.md schema matches fixture (PR #78)
- ✅ Comparator output actionable (PR #79)
- ✅ Drift workflow creates readable GitHub issues (PR #81)

### LOW PRIORITY (informational)

**Issue:** Fixture only covers baseline_matchups.yaml
- **Description:** `data/fixtures/baseline_full_expected.json` only has metrics for `baseline_matchups.yaml`; `auction_smoke.yaml` is explicitly skipped for drift comparison (by design)
- **Verification:** `cat data/fixtures/baseline_full_expected.json`
- **Status:** By design (auction_smoke is smoke-only, no metrics to compare)

---

## IMPLICATIONS OF CURRENT STATE

### CI & Quality Gates

- CI runs fast pytest on PRs (Tier 1)
- Ruff lint/import sorting enforced (E/F/I) in CI + pre-commit
- Ruff now covers `experiments/run_experiment.py` and `scripts/*.py`
- Repo-linter enforced: prevents sprawl, boundary violations, artifact commits
- **Drift detection**: Scheduled daily workflow runs `baseline_full` suite and compares against fixture
- "Honest green CI": flaky perf test xfailed (not silently ignored)

### Gold Path Commands (via Makefile)

```bash
make repo-lint    # Repo linter (diff vs origin/main)
make lint         # Ruff check
make test         # Pytest fast suite
make check        # All of the above
```

### Data Policy & Enforcement

- Only `data/fixtures/**` is commit-allowed (size-capped)
- Generated outputs must not be committed
- All outputs go to `data/runs/<run_id>/`
- .DS_Store blocked by repo-lint and not tracked

### Determinism

- Runner requires seed by default; nondeterminism is opt-in (`--allow-nondeterministic`)
- Common deals: strategies see same hands when seeded
- Auction mode dealer selection is deterministic when `deal_seed` provided

### Run Output Contract

Runs live under `data/runs/<run_id>/` with stable skeleton:
- `meta.json` (schema v2)
- `config_effective.yaml`
- `results/`, `logs/`, `reports/`, `splits/`, `artifacts/`

### Scoring & Points

- Results JSON includes: `avg_points_team0/team1`, `distribution_points_*`, bidding_points
- Scoring contract documented in `docs/01_core/SCORING.md`
- CI guards freeze scoring invariants in `baseline_tiny`

### Baseline Infrastructure

- `baseline_tiny` suite defined (~760 hands, seconds to run)
- `baseline_full` suite defined (16 matchups x 6 scenarios = 96 configs, n_per=500, ~5 min)
- Suite runner: `scripts/run_suite.py`
- Invariants fixture + CI guard for regression detection
- Results JSON shape guard for structural stability
- Auction repeatability test added

### Drift Detection (Stable as of PR #81)

- **Comparator script:** `scripts/compare_rollup.py`
- **Fixture:** `data/fixtures/baseline_full_expected.json` (tricks-only, v0 schema)
- **CI workflow:** `.github/workflows/baseline_full_drift.yml` (daily at 17:00 UTC, creates GitHub Issue on drift)
- **Metric gated:** `avg_tricks` only (auction_smoke skipped for drift)
- **Tolerance:** 0 (exact match required for deterministic suite)
- **Issue output:** Run metadata table, artifact links, comparator output in collapsible details, next steps guidance

### Auction Support

- `contract_type: null` enables auction mode in experiments
- Smoke test validates auction path
- Determinism verified via `test_auction_repeatability.py`
- **Note:** auction_smoke excluded from drift detection (smoke-only, no metrics)

---

## COMMIT HISTORY HIGHLIGHTS

### Milestones (chronological)

| Date | Milestone |
|------|-----------|
| Dec 10, 2025 | Initial simulation + strategies + greedy |
| Dec 15, 2025 | Refactor to `src/bid_euchre` package layout |
| Dec 15–16, 2025 | Unified experiment runner + standardized outputs + reporting |
| Dec 16, 2025 | Head-to-head evaluation system + deprecations |
| Jan 3, 2026 | Regression modeling + bidding engine + training data pipeline (200k records) |
| Jan 4, 2026 | Major reorganization (67+ files) + docs overhaul |
| Jan 5–6, 2026 | Infrastructure blitz: CI + lints + determinism + output contracts (PRs #1–29) |
| Jan 7–8, 2026 | Scoring contracts + guards + auction support + hardening (PRs #30–38) |
| Jan 8–10, 2026 | Auction determinism fix + .DS_Store removal + Ruff coverage + docs cleanup (PRs #39–55) |
| Jan 10–11, 2026 | baseline_full suite + drift comparator + CI drift workflow (PRs #56–75) |
| Jan 11, 2026 | Drift pipeline polish + cleanup + actionable issue output (PRs #76–81) |

---

## KEY THEMES SUMMARY (what to validate)

### Infrastructure & Quality

- CI workflow correctness and speed
- Ruff + pre-commit consistency (now covers runner/scripts)
- Makefile gold path parity with CI
- Repo-linter rule coverage
- **Drift workflow correctness**

### Reproducibility & Determinism

- Seed requirement and propagation to all RNG sources
- Auction determinism (fixed)
- meta.json v2 integrity
- config_effective.yaml usefulness for reproduction
- Stable run outputs (no writes outside run dirs)
- **Rollup JSON determinism**

### Scoring & Points

- Scoring contract completeness (`docs/01_core/SCORING.md`)
- Points aggregates in results JSON
- bidding_points conditional fields logic
- Scoring invariants guard stability

### Baseline & Regression Detection

- `baseline_tiny` suite coverage (3 configs, ~760 hands)
- `baseline_full` suite coverage (16 matchups + auction_smoke)
- Invariants fixture accuracy
- Results JSON shape guard effectiveness
- Suite runner + rollup correctness
- Auction repeatability test
- **Drift comparator accuracy**

### Testing

- 12 unit test files, 17+ integration test files (including auction repeatability), 1 performance test file
- Golden seed smoke tests
- Engine invariants
- Scoring + shape guards
- Runner validation tests

### Documentation Health

- ✅ Empty docs deleted (PR #76)
- ✅ experiments/README.md config list accurate (PR #77)
- ✅ DRIFT.md schema matches actual fixture (PR #78)

---

## CURRENT STRUCTURE

```
bid-euchre/
├── src/bid_euchre/          # Core library (the only importable package)
│   ├── core/                # Cards, deck, rules, trick logic
│   ├── sim/                 # Simulation engine (auction determinism fixed)
│   ├── strategy/            # AI strategies (greedy, random, etc.)
│   ├── features/            # Hand evaluation (40+ features)
│   ├── scoring.py           # Points calculation
│   ├── analysis/            # Statistical analysis
│   ├── reporting/           # Metrics, visualization
│   ├── logging/             # Structured game logging
│   └── experiments/         # Config system
├── experiments/             # Experiment configs + runner
│   ├── run_experiment.py    # THE canonical runner (linted)
│   ├── configs/             # YAML experiment definitions (10 active)
│   ├── suites/              # Suite definitions (baseline_tiny, baseline_full)
│   ├── _deprecated/         # Quarantined legacy scripts + configs
│   ├── comparisons/         # (blocked by repo-lint)
│   ├── training/            # (blocked by repo-lint)
│   ├── README.md            # Directory guide
│   └── REGISTRY.md          # Points to configs/ as authoritative
├── scripts/                 # Tooling (linted)
│   ├── lint_repo.py
│   ├── run_suite.py
│   ├── generate_report.py
│   ├── compare_rollup.py    # NEW: Drift comparator
│   ├── run_tests.py
│   └── validate_tests.py
├── tests/                   # Unit, integration, performance tests
├── docs/                    # Documentation
│   ├── 01_core/             # Architecture, contracts, specs
│   │   ├── ARCHITECTURE.md  # System design, boundaries
│   │   ├── BASELINE.md      # Baseline suite documentation
│   │   ├── DRIFT.md         # Drift detection contract
│   │   ├── METRICS.md       # Metrics contract v1
│   │   ├── SCORING.md       # Points calculation
│   │   └── (others...)      # All accurate
│   ├── 02_agent/            # AI agent guidelines
│   │   ├── AGENTS.md        # Agent operating rules
│   │   └── PR_PROMPT_TEMPLATES.md  # Parallel-safe + auth gate
│   ├── 03_TODO/             # Task tracking
│   ├── archive/             # Deprecated docs (has ARCHIVED banner)
│   ├── DEVELOPMENT.md       # Build/test commands
│   └── README.md            # Docs overview
├── data/
│   ├── fixtures/            # Committed test fixtures (size-capped)
│   │   └── baseline_full_expected.json  # NEW: Drift fixture
│   └── runs/                # Generated outputs (gitignored)
├── Makefile                 # Gold path commands
├── pyproject.toml           # Ruff config (now lints runner/scripts)
└── .github/
    ├── workflows/
    │   ├── ci.yml           # Fast CI on PRs
    │   ├── baseline_full_drift.yml  # NEW: Daily drift detection
    │   └── nightly_baseline_full.yml
    └── PULL_REQUEST_TEMPLATE.md
```

---

## PRIORITIES (ranked)

### 1. Agent Execution Correctness / Low Leak

- Agents must use gold-path commands
- Prevent new one-off runners/entrypoints
- Deterministic experiments by default ✅
- Reproducibility is non-negotiable ✅
- Strict layer boundaries and import hygiene
- No committed generated outputs, ever ✅
- **Drift detection for regression protection** ✅

### 2. Repo Cleanup

- Reduce ambiguity of "where code goes"
- Delete or populate empty docs (6+ files at 0 bytes)
- Quarantine/deprecate safely; delete later
- Consolidate structure; remove duplicate entrypoints
- Minimize "choose your own adventure" paths

### 3. Docs Completion

- Operational docs (copy/paste commands)
- Minimal narrative; clear contracts
- Keep docs aligned with gates
- Delete or populate empty docs

### 4. Roadmap

- Small PRs; clear acceptance criteria
- Staged improvements; low risk; agent-friendly
- Stabilize baseline before expanding

---

## CONSTRAINTS

- Prefer "quarantine + deprecate + delete later" over risky sweeping changes.
- Do not invent repo details—if something is missing/unclear, say so and propose how to verify.
- Bias toward deterministic, reproducible, and CI-validated changes.
- Keep future PRs small and incremental.

---

## TASKS

### A) Audit the Repo

1. Map the current structure:
   - Boundaries: `src/`, `experiments/`, `scripts/`, `tests/`, `docs/`, `data/`
   - Entrypoints and runners (identify "one true" runner; find competing scripts)
   - Experiment configs and output layout (confirm run output contract)
   - Reporting entrypoint and its I/O contract
   - Drift detection pipeline and its contract
   - Bidding + training pipelines and where they live

2. Summarize "what exists" vs "what should exist":
   - What is core and stable
   - What is legacy/deprecated
   - What violates intended boundaries (if anything)

3. Verify known issues status:
   - Empty docs: Are they still 0 bytes?
   - experiments/README.md: Is config list accurate?
   - DRIFT.md: Does schema match fixture?

4. Identify additional leak points (beyond known issues):
   - Nondeterminism (seed enforcement, per-deal seed derivation, RNG sources)
   - Duplicate runners / multiple ways to do the same thing
   - Code placed in wrong layer
   - Generated artifacts written outside run dirs
   - Configs drifting / unclear config precedence

5. Identify "thin ice" areas:
   - Areas likely to break determinism or correctness
   - Brittle tests or xfails hiding problems
   - Drift comparator edge cases

Deliverable: 10–20 bullet repo summary + known issues status + any new leak points with mitigations.

---

### B) Repo Cleanup Plan (staged, PR-sized, low-risk)

1. Classify files/folders: Keep (core) / Move (wrong location) / Quarantine (deprecated but referenced) / Delete (dead)
2. Propose target structure: Define what belongs in each folder; what is forbidden; single "gold paths" for: run experiment, generate report, run suite, compare drift
3. Enforcement proposals: Additional repo-linter rules if needed
4. Risk/reward for each step
5. Cleanup PR sequence (5–10 PRs): goal, scope, acceptance criteria, gates

Deliverable: Ranked actions + PR plan + "do not touch yet" list.

---

### C) Docs Plan + Drafts

1. Docs map: path → purpose → status → priority

| Path | Status | Priority | Notes |
|------|--------|----------|-------|
| docs/01_core/ARCHITECTURE.md | Good | — | Accurate |
| docs/01_core/BASELINE.md | Good | — | Accurate |
| docs/01_core/DRIFT.md | Good | — | Accurate (fixed PR #78) |
| docs/01_core/EXPERIMENTS.md | Good | — | Accurate |
| docs/01_core/METRICS.md | Good | — | Accurate |
| docs/01_core/REPRODUCIBILITY.md | Good | — | Accurate |
| docs/01_core/SCORING.md | Good | — | Matches code |
| docs/02_agent/AGENTS.md | Good | — | Strong operational doc |
| docs/02_agent/PR_PROMPT_TEMPLATES.md | Good | — | Parallel-safe + auth gate |
| docs/DEVELOPMENT.md | Good | — | Matches Makefile/CI |
| experiments/README.md | Good | — | Accurate (fixed PR #77) |
| docs/archive/** | Stale | — | Has ARCHIVED banner |

**Deleted (PR #76):** docs/01_core/ROADMAP.md, SCHEMA_VERSIONING.md, STYLEGUIDE.md, TESTING_STRATEGY.md, docs/CHANGELOG.md, docs/CONTRIBUTING.md

2. Draft highest leverage docs aligned to current gates

Deliverable: 2–4 fully verified/updated docs + status assessment for others.

---

### D) Roadmap from Here (sequenced PRs)

**Status:** PR #81 is complete. Drift detection is now production-ready: "drift happens → issue is readable/actionable" — which is the whole point.

#### Parallel Batch (run 2–3 agents at once) — Low risk, low conflict

**PR #82 — baseline_matchups readability (docs-only)**
- Files: `experiments/configs/baseline_matchups.yaml` (maybe a tiny doc pointer)
- Goal: Add comments/structure to baseline_matchups.yaml
- Scope: Explicitly call out the 4 strategies and 16 matchups
- Acceptance: YAML parses, `make check`

**PR #83 — comparator behavior tests**
- Files: `tests/...` + maybe `scripts/compare_rollup.py` only if tiny refactor for testability
- Goal: Insurance for drift — stop drift regressions
- Scope: Test that skipped configs don't fail; test that real drift fails
- Acceptance: New tests pass, `make check`

**PR #84 — results schema guard extension**
- Files: existing schema guard test(s)
- Goal: Keep scope tight — only validate presence/types for keys drift depends on
- Scope: Ensure guards cover fields drift depends on (`hands`, `avg_tricks`, etc.)
- Acceptance: Tests pass, `make check`

#### Critical Path (must be solid before expanding scope)

After #81, the critical path is:
1. **#83 Comparator tests** (stop drift regressions)
2. **#84 Schema guard** (stop accidental contract breakage)
3. **#82 Readability** (prevents human error / misinterpretation)

Once those land, drift v1 becomes "boring" — which is exactly what you want.

#### Tier 1: Hardening + Signal Quality (still low risk)

**PR #85 — comparator ergonomics v2 (non-breaking)**
- Improve output formatting for issues/CLI (group by config, show expected/actual/delta)
- If already covered in #79/#81, skip

**PR #86 — fixture validation guard**
- Add a tiny test that:
  - Fixture file parses
  - Required config keys exist
  - Values are numeric
  - fixture schema_version matches expected
- This prevents "fixture got accidentally edited" errors

**PR #87 — rollup contract doc**
- A single doc page: rollup.json schema (what's emitted vs computed), and what drift uses

#### Tier 2: Expand Drift Context Without Gating

**PR #88 — secondary metrics in drift issue (report-only)**
- Include win_rate/tie_rate/points in the issue output if they exist, but do not gate on them
- This helps debugging without raising false alarms

#### Tier 3: Auction Boundary Clarity (don't do bidding yet)

**PR #89 — auction_smoke explicitly smoke-only everywhere**
- Ensure suite/docs/workflow/comparator all treat it consistently (skip drift, still run wiring)
- If already fully consistent after recent fixes, skip

#### Tier 4: Future-Facing (only after drift is stable)

**PR #90 — model evaluation report spec (v1)**
- Define what a "decision-ready" report looks like (tables, deltas, confidence)
- This is the bridge to retraining OLS / better strategies

#### Long-term considerations

- **baseline_overnight suite**: n_per: 10000, multiple seeds for research-grade validation
- **Drift "secondary signals"**: Report (not gate on) win_rate, tie_rate, points
- **Auction path future**: Add auction metrics drift checks once bidding policy exists
- **Training reintroduction**: Only via config-driven approach
- **Bidding strategy evaluation**: Extend baseline once play strategies stabilized

---

## OUTPUT FORMAT (required)

1. Repo Summary (10–20 bullets)
2. Known Issues Status (verify each from KNOWN ISSUES section)
3. Additional Leak Points + Mitigations (if any found beyond known issues)
4. Cleanup Plan
   - Ranked actions
   - PR sequence with acceptance criteria
   - "Do not touch yet" list
5. Docs Map (path → status → priority)
6. Docs Assessment (2–4 docs verified/updated; status of others)
7. Roadmap
   - Next 5 PRs detailed (with acceptance criteria)
   - Medium/long-term milestones

---

## VERIFICATION COMMANDS

Run these to verify current state:

```bash
# Verify empty docs were deleted (should all fail with "No such file")
ls docs/01_core/ROADMAP.md docs/01_core/SCHEMA_VERSIONING.md docs/01_core/STYLEGUIDE.md docs/01_core/TESTING_STRATEGY.md docs/CHANGELOG.md docs/CONTRIBUTING.md

# experiments/README.md config list (should show 10 configs)
ls experiments/configs/
# Compare to README listing

# DRIFT.md schema vs fixture (should match)
cat data/fixtures/baseline_full_expected.json
# Compare to docs/01_core/DRIFT.md schema example

# Verify drift comparator works
python scripts/compare_rollup.py --help

# Verify CI workflow exists
ls .github/workflows/baseline_full_drift.yml

# Run make check to validate everything
make check
```

---

## NOTE

- Do not claim something exists unless you can point to it in the ZIP.
- When unsure, say what you looked for and how to verify.
- Bias toward minimal changes that strengthen correctness, determinism, and agent execution reliability.
- Verify known issues before proposing fixes — some may have been resolved since last review.
