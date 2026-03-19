<!-- review-tier: medium -->
# Skills Expansion: 7 New Skills + 3 Retirements + 4 Updates + 3 Meta-Improvements
**Date:** 2026-03-19
**Goal:** Implement the 7 skill gaps, retire 3 stale skills, update 4 existing skills,
and apply 3 meta-improvements identified from Thariq's "Lessons from Building Claude Code:
How We Use Skills" analysis, mapped against our existing 15 skills.

**Source:** https://x.com/trq212/status/2033949937936085378

## Context

Our existing skills heavily cover **code quality/review** (5 skills) and
**planning/execution** (4 skills) but have zero coverage in:
- Product Verification (experiment running)
- Data Fetching & Analysis (statistical analysis)
- Runbooks (symptom-driven debugging)
- CI/CD & Deployment (pre-PR validation)
- Infrastructure Operations (worktree management)

This plan adds skills for each gap and applies Thariq's three meta-best-practices
(gotchas sections, folder-as-skill, usage measurement) to the full skill suite.

## Delivery Strategy

**Single PR** with all 7 new skills + 3 meta-improvements. Rationale:
- All changes are `.claude/skills/` markdown + optional shell scripts
- No source code changes — zero regression risk
- Skills are independently useful but thematically unified
- Splitting into 7+ PRs would be pure churn for docs-only changes

**Estimated scope:** ~10 new files (7 SKILL.md + 3 supporting files), ~10 edits
to existing files (5 Gotchas additions + 4 tool-name fixes + 2 doc reference updates
for reviewing-plans retirement), 3 deletions (retired skills).

## Plan

### Phase 1: High-Priority Skills (3 skills)

#### 1.1 `running-experiments` (Product Verification)

**File:** `.claude/skills/running-experiments/SKILL.md`

**Trigger description:** "Guides experiment execution: config validation, seeded runs,
suite execution, and result comparison. Use when running experiments, comparing runs,
or validating strategy changes."

**Content outline:**
- Phase 0: Pre-flight (verify worktree, check config exists, dry-run validation)
- Phase 1: Smoke Run (quick_test.yaml, --seed 42, --n-per 10)
- Phase 2: Suite Execution (run_suite.py, choosing appropriate suite)
- Phase 3: Comparison (compare_runs.py with bootstrap, --format markdown for PR)
- Phase 4: Interpretation (what the output metrics mean, pass/fail thresholds)

**Gotchas section:**
- Missing `--seed` silently produces non-reproducible results
- `--n-per 10` is smoke-only; production needs ≥50,000 (per `05_rigor.md`)
- `--allow-nondeterministic` voids all comparison claims
- `compare_runs.py` requires both runs to use the same config structure
- Output goes to `data/runs/<run_id>/` — never commit these

**Key commands to embed:**
```
uv run python experiments/run_experiment.py --seed 42 --dry-run --config <cfg>
uv run python experiments/run_experiment.py --seed 42 --config <cfg> --n_per 10
uv run python scripts/run_suite.py --suite <suite> --seed 42 --n-per 20
uv run python scripts/compare_runs.py --baseline <b> --candidate <c> --seed 42 --n-bootstrap 10000 --format markdown
```

**References (progressive disclosure):** Link to `docs/01_core/EXPERIMENTS.md`,
`docs/01_core/REPRODUCIBILITY.md`, `docs/01_core/METRICS.md`

---

#### 1.2 `analyzing-results` (Data Fetching & Analysis)

**File:** `.claude/skills/analyzing-results/SKILL.md`

**Trigger description:** "Guides statistical analysis of experiment results: reading
comparator output, interpreting metrics, checking significance, and producing
committed evidence artifacts. Use when analyzing experiment runs or preparing
statistical claims for reports."

**Content outline:**
- Phase 1: Load Results (read run metadata, identify comparator output files)
- Phase 2: Statistical Checklist (ANOVA/t-tests, CIs, effect sizes, sample size validation)
- Phase 3: Interpretation (net_eppd, CVaR, bid_rate, H2H win rate thresholds)
- Phase 4: Artifact Commitment (notebook → committed JSON, traceability requirements)

**Gotchas section:**
- Visual-only validation is a blocker per `05_rigor.md` — always pair with statistical test
- N < 2,000 insufficient for bias detection; N < 50,000 insufficient for production claims
- Notebook outputs are gitignored — trace claims to committed JSON artifacts
- Effect sizes (Cohen's d, R²) required alongside p-values
- Multiple comparison corrections needed when testing >3 hypotheses

**Key metrics reference table:**
| Metric | Script | Minimum N | What it measures |
|--------|--------|-----------|-----------------|
| net_eppd | compare_runs.py | 2,000 | Expected points per deal delta |
| CVaR | compare_runs.py | 5,000 | Tail risk (worst-case performance) |
| H2H win rate | run_arc_d_h2h_battery.py | 2,000 | Head-to-head match win percentage |
| R² | compare_runs.py | 1,000 | Variance explained by model |

**References:** Link to `docs/01_core/METRICS.md`, `.claude/rules/deferred/05_rigor.md`,
`.claude/rules/deferred/45_notebook_boundary.md`

---

#### 1.3 `debugging-ci` (Runbooks)

**File:** `.claude/skills/debugging-ci/SKILL.md`

**Trigger description:** "Symptom-driven runbook for CI failures, review loop issues,
and make check errors. Use when CI is red, review status is stuck, or validation
commands fail."

**Content outline — symptom → diagnosis → fix table:**

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| `make check` fails on ruff | Read error output | `ruff check --fix && ruff format` on cited files |
| `make check` fails on pytest | Identify failing test | Run targeted: `uv run pytest tests/unit/test_X.py -k "test_name"` |
| `make check` fails on notebook-check | Notebook outputs not cleared | `make notebook-sync` then verify |
| `make check` fails on docs-check | Docs freshness stale | `uv run python scripts/check_docs_freshness.py` to identify |
| `make check` fails on repo-lint | Import boundary violation | Check `src/` not importing from `experiments/` or `tests/` |
| CI red on GitHub after push | Check which job failed | `gh pr checks <PR>` then read failure log |
| Review status stuck `pending` | Loop crashed or never started | Check `.claude/runtime/review_loops/pr_<N>/state.json` |
| Review status stuck `pending` (>1hr) | Fallback workflow should fire | Manual: `scripts/internal/set_review_status.sh success "Manual override"` |
| Review loop in `failure` | Blocking precheck found | Read state.json for blocker details, fix in PR |
| `git push` rejected | Branch behind main | `git fetch origin main && git rebase origin/main` |
| Worktree hook blocks edits | Working on main checkout | Create worktree: `git worktree add ../Bid-Euchre-<name> -b <branch>` |

**Escalation protocol:**
1. Try the automated fix from the table
2. If still failing, read full error output and apply targeted fix
3. If infrastructure issue (not code), check `scripts/internal/` for relevant tooling
4. If stuck, manual status override + open GitHub issue

**References:** Link to `.claude/rules/deferred/60_review_gate.md`,
`scripts/internal/review_driver.py`, `scripts/internal/set_review_status.sh`

---

### Phase 2: Medium-Priority Skills (2 skills)

#### 2.1 `managing-worktrees` (Infrastructure Operations)

**File:** `.claude/skills/managing-worktrees/SKILL.md`

**Trigger description:** "Manages git worktrees: creation, cleanup, and protection rules.
Use when creating new worktrees, cleaning up after merges, or checking worktree status."

**Content outline:**
- Create: `git worktree add ../Bid-Euchre-<name> -b <branch>`
- List: `git worktree list`
- Status check: Working tree clean? `git -C <path> status --short`
- Safe cleanup protocol (3-step: check protected list → verify PR merged → verify clean)

**Protected worktrees (hardcoded list):**
```
Bid-Euchre-steward-author
Bid-Euchre-steward-author-b
Bid-Euchre-steward-author-c
Bid-Euchre-steward-author-d
Bid-Euchre-steward-author-scratch
Bid-Euchre-steward-review
Bid-Euchre-steward-ops
```

**Gotchas section:**
- NEVER run `git worktree prune` — it removes stale entries indiscriminately
- NEVER remove any worktree matching `*steward*`
- Always save diffs before removing dirty worktrees: `git -C <path> diff > /tmp/<name>.diff`
- The UserPromptSubmit hook auto-creates worktrees when blocked — don't fight it
- Worktree names should match branch names for discoverability

**References:** Link to `.claude/rules/75_worktree_protection.md`

---

#### 2.2 `validating-changes` (CI/CD)

**File:** `.claude/skills/validating-changes/SKILL.md`

**Trigger description:** "Guides the two-tier testing workflow: targeted tests during
development (Tier 1) and full validation before PRs (Tier 2). Use when deciding
which tests to run or when make check fails."

**Content outline:**
- Tier 1 decision tree:
  - Changed `src/bid_euchre/foo/bar.py` → run `tests/unit/test_bar.py`
  - Changed `__init__.py` exports → widen to Tier 2 immediately
  - Changed test fixtures or conftest → widen to Tier 2 immediately
  - Changed function signatures used across modules → widen to Tier 2
  - Unsure what depends on change → `grep -rl "from bid_euchre.foo" tests/`
- Tier 2: `make check-quiet` (preferred) or `make check` (for debugging)
- After review fixes: small (1-2 files) → Tier 1; broad (3+) → Tier 2

**Gotchas section:**
- Don't run `make check` repeatedly during active development — it's slow
- `make check-quiet` logs to tmpfile — read the log on failure
- `make notebook-check` verifies sync + outputs cleared but does NOT execute notebooks
- `make notebook-run` (SMOKE) and `make notebook-run-full` (QUICK) execute but are NOT in `make check`
- `make repo-lint` catches import boundary violations — `src/` must NOT import from `experiments/` or `tests/`

**References:** Link to `.claude/rules/15_testing_tiers.md`,
`.claude/rules/10_workflow.md`

---

### Phase 3: Lower-Priority Skills (2 skills)

#### 3.1 `adding-strategies` (Code Scaffolding)

**File:** `.claude/skills/adding-strategies/SKILL.md`

**Trigger description:** "Scaffolds a new bot strategy: implementation, export, registration,
tests, config, and smoke validation. Use when adding a new bidding or playing strategy."

**Content outline — checklist:**
1. Implement in `src/bid_euchre/strategy/<name>.py`
   - Class must accept `seed` parameter
   - Use `random.Random(seed)` for all randomness — never global `random.*`
2. Export in `src/bid_euchre/strategy/__init__.py`
3. Register in `src/bid_euchre/experiments/config.py` → `StrategyConfig.create_strategy()`
4. Add unit tests in `tests/unit/test_<name>.py`
5. Add/update YAML config in `experiments/configs/`
6. Run seeded smoke: `uv run python experiments/run_experiment.py --seed 42 --config <cfg> --n_per 10`

**Gotchas section:**
- Strategies MUST use local `random.Random(seed)`, never global `random.*` — C1 blocker
- The `create_strategy()` registry in `config.py` is the canonical mapping
- Strategy class names should match the YAML config `strategy_type` field
- Test both bidding and playing decisions, not just construction

**References:** Link to `docs/01_core/ARCHITECTURE.md`,
`src/bid_euchre/strategy/__init__.py`, `src/bid_euchre/experiments/config.py`

---

#### 3.2 `triaging-issues` (Business Process)

**File:** `.claude/skills/triaging-issues/SKILL.md`

**Trigger description:** "Triages GitHub issues and review findings into labeled,
prioritized follow-up work. Use when creating follow-up issues from review findings
or organizing outstanding work."

**Content outline:**
- Label taxonomy (from `60_review_gate.md`):
  | Label | Color | Applied to |
  |-------|-------|------------|
  | `follow-up` | `#fbca04` | All follow-up issues |
  | `fix:bug` | `#d73a4a` | C1, C2 findings |
  | `fix:convention` | `#0075ca` | Auto-fix patterns, C4 |
  | `fix:test` | `#e4e669` | T1 findings |
  | `fix:docs` | `#0e8a16` | X2 findings |
  | `fix:process` | `#c5def5` | X1, X3, N1/N2/N3 |
- Priority mapping: BLOCK findings → immediate fix PR; WARN → follow-up issue
- Deduplication: Search existing issues before creating (`gh issue list --label follow-up`)
- Batching convention: Group related findings into batch PRs (e.g., "fix: convention follow-up batch N")

**Gotchas section:**
- Always check for existing issues before creating duplicates
- Link follow-up issues to the originating PR
- Batch related fixes — don't create one PR per finding
- `fix:bug` label items (C1, C2) should be prioritized over `fix:convention`

**References:** Link to `.claude/rules/deferred/60_review_gate.md`

---

### Phase 4: Skill Retirements (3 skills)

#### 4.1 Retire `reviewing-plans`

**Reason:** Already marked `DEPRECATED` in its own frontmatter. Replaced by `/review-plan`
which provides independent review via Codex CLI + Claude failsafe. The deprecated skill
is retained only for backward compatibility and is "no longer auto-triggered."

**Action:** Delete `.claude/skills/reviewing-plans/SKILL.md` and its directory.

**Live reference cleanup required:**
- `docs/02_agent/PLAN_REVIEW_RUBRIC.md` (lines 5, 13): Update `/reviewing-plans` → `/review-plan`
- `.claude/hooks/README.md` (line 87): History note — update to past tense mentioning replacement
- `plans/arc_d_v2/lineage_plan.md` (line 770): Frozen/COMPLETE plan — no update needed
- Archive plans (`plans/archive/`): Historical records — no update needed

---

#### 4.2 Retire `drafting-rung-reports`

**Reason:** Tightly coupled to Arc D v2 lineage workflow (R0-R3 promotion reports,
comparator rankings, H2H battery analysis, measurement integrity reviews). Arc D v2
is **COMPLETE** as of 2026-03-19. The skill references `data/artifacts/arc_d/r{N}/`
artifact paths, R{N-1} cross-rung comparison patterns, and promotion decision JSON
schemas that are specific to that initiative.

**Action:** Delete `.claude/skills/drafting-rung-reports/SKILL.md` and its directory.
If a new lineage initiative starts (e.g., browser game evaluation), a fresh skill
should be created from scratch rather than resurrecting this one.

---

#### 4.3 Retire `narrating-reports`

**Reason:** Same as `drafting-rung-reports` — this skill is exclusively about adding
narrative overlays to Arc D v2 rung reports. It references `promotion_decision_r{N}.json`,
`rung_bundle_r{N}.json`, `REPORT_NARRATIVE_CONVENTIONS.md`, and section-by-section
commentary patterns (S2-S9) that are specific to the completed lineage.

**Action:** Delete `.claude/skills/narrating-reports/SKILL.md` and its directory.

---

### Phase 5: Skill Updates (3 skills)

#### 5.1 Update `fixing-bugs`

**Issue:** References `TodoWrite` (line 22: "Track progress with TodoWrite"). `TodoWrite`
was renamed to the TUI task system (`TaskCreate`/`TaskUpdate`/`TaskList`).

**Action:** Replace `TodoWrite` reference with `TaskCreate`/`TaskUpdate`.

---

#### 5.2 Update `executing-plans`

**Issue:** References `TodoWrite` in two places (line 38: "Track progress with TodoWrite",
line 75: "Mark unit as blocked in TodoWrite"). Same migration needed.

**Action:** Replace both `TodoWrite` references with `TaskCreate`/`TaskUpdate`.

---

#### 5.3 Update `summarizing-sessions`

**Issue:** References "Task tool (`subagent_type: general-purpose`)" (line 69) for spawning
a reviewer agent. The tool is actually `Agent` (not "Task tool"), and the `subagent_type`
parameter syntax is correct but the tool name is wrong.

**Action:** Change "Task tool" → "Agent tool" in the reviewer agent spawn section.

---

#### 5.4 Update `reviewing-repo`

**Issue:** References "Task tool (`subagent_type: general-purpose`)" (line 22) for spawning
sub-agents. Same stale tool-name issue as `summarizing-sessions`.

**Action:** Change "Task tool" → "Agent tool".

---

### Phase 6: Meta-Improvements (3 changes)

#### 6.1 Add Gotchas Sections to Existing Skills

**Target skills** (those lacking gotchas that would benefit):
- `reviewing-changes/SKILL.md` — Add gotchas about common dispatcher mistakes
- `executing-plans/SKILL.md` — Add gotchas about agent context window limits
- `shipping-changes/SKILL.md` — Add gotchas about worktree cleanup edge cases
- `planning-code-first/SKILL.md` — Add gotchas about stale line number references
- `recovering-context/SKILL.md` — Add gotchas about MEMORY.md truncation

Each gotchas section: 3-5 bullets of common failure modes specific to that skill,
drawn from actual project experience (e.g., the agent reliability rule, the MEMORY.md
200-line limit, the worktree protection list).

#### 6.2 Folder-as-Skill Enhancement

Where appropriate, add supporting files to skill folders:

| Skill | New File | Purpose |
|-------|----------|---------|
| `running-experiments` | `QUICK_REFERENCE.md` | Command cheat-sheet for copy-paste |
| `debugging-ci` | `SYMPTOM_TABLE.md` | Separable symptom→fix lookup table |
| `analyzing-results` | `CHECKLIST.md` | Statistical rigor checklist (from `05_rigor.md` gold standard) |

These are progressive-disclosure files — the SKILL.md references them but they're
only loaded on demand, keeping the main skill focused.

#### 6.3 Skill Usage Measurement (Deferred — Needs Hook Design)

Thariq recommends PreToolUse hooks for skill invocation logging. This requires:
- A hook on the `Skill` tool matcher
- A log file at `.claude/runtime/skill_usage.jsonl`
- Fields: timestamp, skill_name, session_id

**Recommendation:** Defer to a separate PR. Hook changes affect all sessions and
deserve their own review cycle. Document the design here for future implementation.

---

## Files

### New Files (10)
- `.claude/skills/running-experiments/SKILL.md` — Experiment execution guide
- `.claude/skills/running-experiments/QUICK_REFERENCE.md` — Command cheat-sheet
- `.claude/skills/analyzing-results/SKILL.md` — Statistical analysis guide
- `.claude/skills/analyzing-results/CHECKLIST.md` — Rigor checklist
- `.claude/skills/debugging-ci/SKILL.md` — Symptom-driven CI runbook
- `.claude/skills/debugging-ci/SYMPTOM_TABLE.md` — Separable lookup table
- `.claude/skills/managing-worktrees/SKILL.md` — Worktree operations guide
- `.claude/skills/validating-changes/SKILL.md` — Two-tier testing guide
- `.claude/skills/adding-strategies/SKILL.md` — Strategy scaffolding checklist
- `.claude/skills/triaging-issues/SKILL.md` — Issue triage and labeling guide

### Deleted Files (3)
- `.claude/skills/reviewing-plans/SKILL.md` — Deprecated, replaced by `/review-plan`
- `.claude/skills/drafting-rung-reports/SKILL.md` — Arc D v2 specific, lineage COMPLETE
- `.claude/skills/narrating-reports/SKILL.md` — Arc D v2 specific, lineage COMPLETE

### Modified Files (10)
- `.claude/skills/reviewing-changes/SKILL.md` — Add Gotchas section
- `.claude/skills/executing-plans/SKILL.md` — Add Gotchas section + fix TodoWrite → Tasks
- `.claude/skills/shipping-changes/SKILL.md` — Add Gotchas section
- `.claude/skills/planning-code-first/SKILL.md` — Add Gotchas section
- `.claude/skills/recovering-context/SKILL.md` — Add Gotchas section
- `.claude/skills/fixing-bugs/SKILL.md` — Fix TodoWrite → Tasks
- `.claude/skills/summarizing-sessions/SKILL.md` — Fix "Task tool" → "Agent tool"
- `.claude/skills/reviewing-repo/SKILL.md` — Fix "Task tool" → "Agent tool"
- `docs/02_agent/PLAN_REVIEW_RUBRIC.md` — Update `/reviewing-plans` → `/review-plan`
- `.claude/hooks/README.md` — Update history note for `/reviewing-plans` retirement

### Deferred (not in this PR)
- `.claude/settings.json` — Skill usage hook (Phase 6.3)

## Validation

Since this is a docs/skills-only PR:
- `make check` will pass (no Python changes)
- CI `dorny/paths-filter` will skip heavy steps
- Manual validation: verify each skill triggers correctly via description matching

## Acceptance Criteria

- [ ] All 7 new skill directories created with SKILL.md
- [ ] 3 supporting files (QUICK_REFERENCE, SYMPTOM_TABLE, CHECKLIST) created
- [ ] 3 stale skills retired (reviewing-plans, drafting-rung-reports, narrating-reports)
- [ ] 4 existing skills updated (TodoWrite → Tasks + "Task tool" → "Agent tool")
- [ ] Live references to `/reviewing-plans` updated in docs and hooks README
- [ ] 5 existing skills updated with Gotchas sections
- [ ] Each skill has correct frontmatter (name, description)
- [ ] Description fields are trigger-oriented (not summaries)
- [ ] Each skill references authoritative docs via progressive disclosure
- [ ] No Python source code changes
- [ ] `make check` passes

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Skills too verbose → context bloat | Medium | Keep SKILL.md focused; use supporting files for details |
| Description triggers too broad → false invocations | Low | Test descriptions against common queries |
| Gotchas become stale as project evolves | Medium | Gotchas reference rules/docs, not hardcoded values |
| Single PR too large for review | Low | All files are independent markdown — reviewable in parallel |

## Outcome
<!-- Filled after implementation -->
- PR: pending
- Notes: —
