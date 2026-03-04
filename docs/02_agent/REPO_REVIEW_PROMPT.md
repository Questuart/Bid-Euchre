# Repo Review Prompt — AI Agent Execution Protocol

**Version:** 3.5 (Drift-Resilient, Discovery-Driven)
**Last Updated:** February 2026

---

## ROLE

You are an engineering lead performing a comprehensive review of the Bid Euchre repository, a Python card-game simulator built entirely by AI agents. Your objective is to:

1. **Systematically discover** current repo state (modules, configs, scripts, docs)
2. **Verify hard gates** (CI, contracts, rigor standards, boundaries)
3. **Identify issues** (gaps, drift, rigor violations, anti-patterns)
4. **Analyze impact** (severity, risk, effort assessment)
5. **Produce actionable output** (structured issues; roadmap/PRs only when warranted)

**Value Gate:** Only recommend changes that improve model training, evaluation correctness,
or reproducibility. Avoid work that improves code cleanliness but does not improve outcomes.

**Core Philosophy:** This repo prioritizes **technical correctness and statistical rigor** over accessibility or convenience. See `.claude/rules/05_rigor.md` for the authoritative rigor philosophy.

---

## TOOL ACCESS

This prompt is designed to work for both CLI-capable agents and non-CLI agents.
Use the best available tools in your environment.

| Tool | Purpose | Usage Notes |
|------|---------|-------------|
| **Read** | Read files by path | Use for specific file inspection |
| **Search** | Search file contents | Use for pattern-based discovery |
| **Glob** | Find files by pattern | Use for structural enumeration |
| **Shell (if available)** | Run verification commands | Prefer read-only; use for CI checks, counts, imports |
| **Explore (optional)** | Launch exploration agents | Use for complex multi-step searches |

**Execution Guidance:**
- **Run commands in parallel** when independent (multiple Bash/Read in single message)
- **Run sequentially** when dependent (one output informs next input)
- **Discovery-oriented:** Use tools to verify current state, not hardcoded assumptions
- **Evidence-based:** Every claim requires verification (command output, file quote, line reference)
Note: Tool names may vary by environment; use the closest available search/shell tool.
If you do not have CLI/Shell access, use Read/Search/Glob to gather evidence,
and explicitly mark any command you cannot run.

---

## AGENT EXECUTION PROTOCOL

This review follows a **5-phase systematic workflow**. Each phase has specific tool usage patterns and deliverables.

---

## PHASE 1: DISCOVERY (Dynamic State Mapping)

**Goal:** Build an accurate, quantitative map of the current repository state.

**Estimated Tool Calls:** 10-30 (use as needed; avoid unnecessary exploration)

If you do not have CLI access, use Read/Search/Glob to approximate counts and
explicitly mark any command you cannot run.

**Non-CLI evidence example (Discovery):**
```markdown
- Module list: Read `docs/01_core/ARCHITECTURE.md` and compare to `src/bid_euchre/` via Glob.
- Config count: Use Glob `experiments/configs/*.yaml` and count matches.
- Script list: Use Glob `scripts/*.py`.
```

### 1.1 Structure Discovery

**Run these in parallel:**

```bash
# Module count and listing
ls -d src/bid_euchre/*/ | grep -v __pycache__ | wc -l
ls -d src/bid_euchre/*/ | grep -v __pycache__

# Config and suite counts
ls experiments/configs/*.yaml | wc -l
ls experiments/suites/*.yaml | wc -l

# Script count (top-level + internal)
ls scripts/*.py | wc -l
ls scripts/*.py
ls scripts/internal/*.py 2>/dev/null | wc -l

# Test structure
ls -d tests/*/
find tests -name "test_*.py" | wc -l

# Documentation structure
find docs -name "*.md" | wc -l
ls docs/01_core/*.md
ls docs/02_agent/*.md
ls docs/03_TODO/*.md

# Notebook count (active only, exclude archives)
find notebooks -name "*.ipynb" -not -path "*/archive/*" -not -path "*/.archive/*" | wc -l
```

### 1.2 Version Context

**Run these in parallel:**

```bash
# Latest PR number
gh pr list --state merged --limit 1 --json number --jq '.[0].number'

# Recent commits (last 10)
git log --oneline -10

# Total commits
git rev-list --count HEAD

# Repo age
git log --reverse --format=%ai | head -1
```

### 1.3 Module Health

**Run these sequentially (dependencies matter):**

```bash
# Verify core imports work
uv run python -c "from bid_euchre.core import Card, create_deck; print('core OK')"
uv run python -c "from bid_euchre.sim.simulation import play_single_hand; print('sim OK')"
uv run python -c "from bid_euchre.strategy import GreedyStrategy; print('strategy OK')"

# Verify datasets
uv run python -c "from bid_euchre.datasets.bidless import BidlessDatasetCollector; print('datasets OK')"
uv run python -c "from bid_euchre.datasets.bidless_outcomes import BidlessOutcomesCollector; print('bidless_outcomes OK')"

# Verify features
uv run python -c "from bid_euchre.features.hand_eval import get_hand_features; print('features OK')"

# Verify validation
uv run python -c "from bid_euchre.validation.schemas import validate_meta_v2; print('validation OK')"

# Verify diagnostics
uv run python -c "from bid_euchre.diagnostics.notebook_data import load_or_generate_outcomes; print('diagnostics OK')"
uv run python -c "from bid_euchre.diagnostics.sanity_tests import run_sanity_tests; print('sanity_tests OK')"
uv run python -c "from bid_euchre.diagnostics.notebook_validation import ValidationResult; print('notebook_validation OK')"

# Verify analysis
uv run python -c "from bid_euchre.analysis.paired import compute_paired_deltas; print('analysis OK')"

# Verify strategies
uv run python -c "from bid_euchre.strategy import GluttonStrategy, GluttonIsolatedStrategy; print('glutton OK')"

# Verify Arc C+ modules (batch, eligibility, splits, freeze, promotion)
uv run python -c "from bid_euchre.experiments.batch import BatchMetadata; print('batch OK')"
uv run python -c "from bid_euchre.reporting.eligibility import compute_eligibility; print('eligibility OK')"
uv run python -c "from bid_euchre.models.splits import SplitManifest; print('splits OK')"
uv run python -c "from bid_euchre.models.freeze import freeze_artifact, verify_frozen; print('freeze OK')"
uv run python -c "from bid_euchre.validation.promotion import check_artifacts_frozen; print('promotion OK')"

# Verify reporting (chart generators)
uv run python -c "from bid_euchre.reporting.charts import generate_contract_faceted_charts; print('charts OK')"

# Verify logging and utils
uv run python -c "from bid_euchre.logging.game_logger import GameLogger; print('logging OK')"
uv run python -c "from bid_euchre.core.time import utc_now_iso; print('time OK')"

# Verify scoring (top-level module)
uv run python -c "from bid_euchre.scoring import compute_points; print('scoring OK')"

# Verify Arc D modules (diagnostics extensions)
uv run python -c "import bid_euchre.diagnostics.semantic_gate; print('semantic_gate OK')"
uv run python -c "from bid_euchre.diagnostics.split_guard import require_split; print('split_guard OK')"

# Verify Arc D modules (models extensions)
uv run python -c "import bid_euchre.models.train_hybrid_olsa; print('train_hybrid_olsa OK')"
uv run python -c "import bid_euchre.models.feature_selection; print('feature_selection OK')"

# Verify Arc D modules (reporting extensions)
uv run python -c "import bid_euchre.reporting.arc_d_report; print('arc_d_report OK')"

# Verify Arc D modules (validation extensions)
uv run python -c "import bid_euchre.validation.arc_d_bundle; print('arc_d_bundle OK')"
uv run python -c "from bid_euchre.validation.arc_d_gate import normalize_eval_metrics; print('arc_d_gate OK')"

# Dynamic: also verify any modules not listed above
# ls -d src/bid_euchre/*/ | grep -v __pycache__
# (check if any module directories exist that aren't covered by the imports above)
```

**Deliverable:** Quantitative structure table with actual counts (do not compare to hardcoded expected values — record what you find).

---

## PHASE 2: VERIFICATION (Hard Gates & Contracts)

**Goal:** Validate that the repo complies with all hard gates, contracts, and rigor standards.

**Estimated Tool Calls:** 10-35 (use as needed; avoid unnecessary exploration)

If you do not have CLI access, report that CI could not be run and continue only
with file-based evidence, clearly marking gaps.

### 2.1 CI Gates (MANDATORY)

**Run full CI check (always required):**

```bash
# Full validation suite (includes: repo-lint, lint, test, notebook-check, docs-check)
make check
```

**If `make check` fails:** Stop the review and report the failure summary and logs
in the Verification Evidence section. Do not proceed to later phases unless asked.
If you cannot run CLI commands, explicitly state that CI could not be run and
request a CLI-capable agent to execute `make check` before continuing.

**Breakdown individual checks (if make check fails):**

```bash
make repo-lint      # Repository linter
make lint           # Ruff check (lint only)
make test           # Pytest fast suite
make notebook-check # Jupytext sync + outputs cleared
make docs-check     # Documentation freshness
```

**Verify repo-linter rules:** Read `scripts/lint_repo.py` and count all `check_*` functions.

```bash
# Count rules (do NOT rely on a hardcoded number — derive from source)
grep -c "^def check_" scripts/lint_repo.py

# List all rule names
grep "^def check_" scripts/lint_repo.py | sed 's/def //; s/(.*//;'
```

**Rule Categories** (stable summary — derive exact rules from source):

| Category | Purpose | Examples |
|----------|---------|----------|
| **Data policy** | Prevent artifact leakage | No generated artifacts in `data/runs/`, fixture allowlist |
| **Import boundaries** | Enforce layer separation | `src/` cannot import `experiments/` or `tests/`; no `sys.path.insert`; no `import experiments` |
| **Determinism** | Enforce reproducibility | No global `random.*` in `src/`; experiments require `--seed` |
| **Code quality** | Prevent stubs and misplacement | No empty test functions; no `argparse` in `src/` |
| **Workflow** | Protect frozen folders | No changes to `_deprecated/`; no new scripts in frozen dirs; no `.DS_Store` |
| **Promotion** | Artifact integrity gates | Artifacts require freeze (`frozen_at` + `artifact_sha256`); gate schema validation; split manifest schema |

Run `make repo-lint` to verify all rules pass. Read `scripts/lint_repo.py` for the authoritative rule list.

### 2.2 Rigor Validation

**Goal:** Verify statistical rigor standards for production or decision-making artifacts.
Exploratory notebooks should be flagged but are not required to have full tests/CIs.

**Sample Size Validation:**

```bash
# Check config sample sizes (n_per values)
grep -h "n_per" experiments/configs/*.yaml | awk '{print $NF}' | sort -n

# Identify configs with inadequate sample sizes (<2000 for inference)
grep -H "n_per:" experiments/configs/*.yaml | awk -F: '{if ($3 < 2000) print $1 " has inadequate sample size: " $3}'
```

**Statistical Test Presence:**

```bash
# Find notebooks with statistical tests
find notebooks -name "*.ipynb" -not -path "*/archive/*" -exec grep -l "f_oneway\|ttest\|bootstrap\|mannwhitneyu\|chi2_contingency" {} \;

# Find notebooks with plots but potentially missing tests
find notebooks -name "*.ipynb" -not -path "*/archive/*" -exec grep -l "plt\." {} \; | while read nb; do
  if ! grep -q "f_oneway\|ttest\|bootstrap" "$nb"; then
    echo "POTENTIAL RIGOR GAP: $nb (has plots, no obvious statistical tests)"
  fi
done
```

**Fail-Fast Gate Verification:**

```bash
# Search for assert-style sanity checks
grep -r "assert.*p_value\|assert.*between\|assert.*nunique" notebooks/ src/

# Search for rigor anti-patterns
grep -rn "looks balanced\|looks good\|appears to" notebooks/ | head -10
```

**Hardcoded Value Detection:**

```bash
# Find potential hardcoded seat/trump values
grep -rn "seat.*=.*0[^-9]" notebooks/ experiments/ | grep -v "for seat in\|all seats" | head -10
grep -rn "trump.*=.*['\"]H['\"]" notebooks/ src/ | head -10
```

**Confidence Interval Usage:**

```bash
# Find CI usage
grep -r "confidence.*interval\|CI\s*=\|bootstrap" notebooks/ src/bid_euchre/diagnostics/
```

**Deliverable:** Rigor compliance table with:
- Sample size distribution (min, median, max across configs)
- Notebook coverage (X/Y have statistical tests, Z/Y have CIs)
- Anti-pattern count (hardcoded values, visual-only validation claims)

### 2.3 Boundary Compliance

**Import Hygiene:**

```bash
# Verify no forbidden imports in src/
grep -r "from experiments\|from tests" src/ --include="*.py"

# Expected: No results (hard boundary enforced by repo-linter)
```

**Frozen Folder Check:**

```bash
# Verify experiments/_deprecated/ is not modified (except README/new additions)
git log --oneline --since="2025-11-01" -- experiments/_deprecated/ | grep -v "README\|quarantine"

# Verify no new scripts in frozen folders
ls experiments/comparisons/*.py experiments/training/*.py 2>/dev/null
```

**Artifact Leakage:**

```bash
# Check for uncommitted artifacts in working tree
find data/runs data/reports data/models -type f 2>/dev/null | head -5

# Check git status for accidental staging
git status data/
```

### 2.4 Documentation Accuracy

**Contract Doc Verification:**

For each contract doc, verify claims against reality:

| Doc | Verification Command | Status |
|-----|---------------------|--------|
| `ARCHITECTURE.md` | Compare module list to `ls src/bid_euchre/` | ✅/⚠️/❌ |
| `EXPERIMENTS.md` | Verify config count matches `ls experiments/configs/` | ✅/⚠️/❌ |
| `DATA_CONTRACT.md` | Check schema versions in `validation/schemas.py` | ✅/⚠️/❌ |
| `FLOW_DIAGRAM.md` | Verify module references exist | ✅/⚠️/❌ |

**Command Verification:**

```bash
# Extract commands from docs and test them (if CLI available)
grep -h "^python\|^make\|^PYTHONPATH\|^uv run" docs/01_core/*.md docs/02_agent/*.md | head -10

# Test sample commands (dry-run safe)
uv run python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42 --dry-run
```

**Deliverable:** Documentation accuracy table with drift details.

### 2.5 Promotion Workflow Verification

**Goal:** Verify the promotion workflow infrastructure is functional.

```bash
# Check if promotion-gate target exists
make -n promotion-gate 2>&1 | head -5

# Verify freeze/splits/eligibility modules import
uv run python -c "
from bid_euchre.models.freeze import freeze_artifact, verify_frozen, require_frozen
from bid_euchre.models.splits import SplitManifest, create_grouped_split
from bid_euchre.reporting.eligibility import compute_eligibility
from bid_euchre.validation.promotion import check_artifacts_frozen
print('promotion imports OK')
"

# Verify promotion lint rules exist in repo-linter
grep "def check_.*artifact\|def check_.*gate\|def check_.*split\|def check_.*registry" scripts/lint_repo.py
```

**Deliverable:** Promotion workflow status (functional/broken/partial).

---

## PHASE 3: ISSUE DISCOVERY (Gap Analysis)

**Goal:** Identify all issues, gaps, and improvement opportunities using automated detection.

**Estimated Tool Calls:** 20-30

### 3.1 Known Issues Review

**Read existing tracking docs:**

```bash
# List TODO tracker files
ls docs/03_TODO/*.md

# Check for previous review outputs
ls docs/03_TODO/REPO_REVIEW_*.md
```

**Read:** `docs/03_TODO/CODEBASE_CONSISTENCY.md` for ongoing doc/code gaps.

### 3.2 Automated Detection

**TODO Scanning:**

```bash
# TODOs in source code
grep -rn "TODO\|FIXME\|HACK\|XXX" src/ scripts/ --include="*.py" | wc -l
grep -rn "TODO\|FIXME\|HACK\|XXX" src/ scripts/ --include="*.py" | head -20

# TODOs in docs
grep -rn "TODO" docs/ --include="*.md" | wc -l
```

**Empty Test Detection:**

```bash
# Find test files
find tests -name "test_*.py" | wc -l

# Check for empty test functions (repo-linter should catch)
grep -rn "def test_.*:.*pass$" tests/
```

**Unseeded Experiment Detection:**

```bash
# Find experiment invocations in docs without --seed
grep -rn "python experiments/run_experiment.py" docs/ | grep -v -- "--seed\|--allow-nondeterministic" | head -10
```

**Stale Reference Detection:**

```bash
# Find references to config names and verify they still exist
grep -roh "experiments/configs/[a-z_]*.yaml" docs/ | sort -u | while read cfg; do
  if [ ! -f "$cfg" ]; then
    echo "STALE REF: $cfg referenced in docs but does not exist"
  fi
done

# Find references to scripts and verify they still exist
grep -roh "scripts/[a-z_]*.py" docs/ | sort -u | while read scr; do
  if [ ! -f "$scr" ]; then
    echo "STALE REF: $scr referenced in docs but does not exist"
  fi
done
```

### 3.3 Drift Detection

**Compare documented structure to reality:**

```bash
# Module count drift
# Doc claim: Read ARCHITECTURE.md module list
# Reality: ls -d src/bid_euchre/*/ | grep -v __pycache__ | wc -l

# Config count drift
# Doc claim: Read from EXPERIMENTS.md or previous REPO_REVIEW
# Reality: ls experiments/configs/*.yaml | wc -l

# Script list drift
# Doc claim: Read ARCHITECTURE.md script list
# Reality: ls scripts/*.py
```

### 3.4 Rigor Gaps

**Visual-Only Validation Detection:**

```bash
# Find notebooks with "looks" claims but no statistical backing
grep -rn "looks balanced\|looks good\|appears balanced\|seems reasonable" notebooks/ | head -10
```

**Missing Statistical Tests:**

```bash
# Find analysis notebooks and check for statistical tests
# Discover active notebooks dynamically (do NOT hardcode paths)
find notebooks -name "*.ipynb" -not -path "*/archive/*" -not -path "*/.archive/*" | while read nb; do
  if grep -q "plt\.\|plot\|chart\|figure" "$nb" 2>/dev/null; then
    if ! grep -q "f_oneway\|ttest\|bootstrap\|mannwhitneyu\|chi2" "$nb" 2>/dev/null; then
      echo "MISSING TESTS: $nb"
    fi
  fi
done
```

**Inadequate Sample Sizes:**

```bash
# Flag configs with n_per < 2000 (rigor threshold for bias detection)
grep -H "n_per:" experiments/configs/*.yaml | awk -F: '{if ($3 < 2000) print $1 " has inadequate sample size: " $3}'
```

**Hardcoded Configuration Anti-Pattern:**

```bash
# Find single-seat or single-trump hardcoding
grep -rn "seat\s*=\s*0[^-9]" notebooks/ src/ | grep -v "range\|for seat\|all seats" | head -10
grep -rn "trump\s*=\s*['\"]H['\"]" notebooks/ src/ | head -10
```

**Missing Confidence Intervals:**

```bash
# Find mean/metric reporting without CI
grep -rn "\.mean()\|\.median()" notebooks/ | head -20
# Manual review: check if surrounding code has CI calculation
```

**Deliverable:** Issue discovery tables with automated detection results.

---

## PHASE 4: ANALYSIS (Prioritized Assessment)

**Goal:** Classify issues by severity, impact, and effort.

**Estimated Tool Calls:** 5-10 (mostly analysis, fewer reads)

### 4.1 Severity Classification

**Classify each issue found in Phase 3:**

- **CRITICAL:** Breaks functionality, violates hard gates, introduces nondeterminism
- **HIGH:** Documentation drift causing agent confusion, missing rigor validation
- **MEDIUM:** TODOs in production code, stale references, incomplete tests
- **LOW:** Cosmetic issues, informational gaps, minor doc improvements

**Examples:**

| Severity | Example Issues |
|----------|---------------|
| CRITICAL | Global `random.` usage in src/, unseeded experiments in production configs |
| HIGH | ARCHITECTURE.md module list doesn't match `ls src/bid_euchre/`, missing statistical tests in analysis notebooks |
| MEDIUM | TODOs in src/, empty test stubs, hardcoded `seat=0` in demo notebooks |
| LOW | Typos in docs, missing docstrings, cosmetic doc drift |

### 4.2 Impact Assessment

**For each issue, assess:**

1. **Affected Workflows:** What breaks if unfixed? (CI, experiments, analysis, onboarding)
2. **Risk:** Likelihood of causing errors (high/medium/low)
3. **Effort:** Estimated fix complexity (trivial/small/medium/large)

**Deliverable:** Prioritized issue registry with severity, impact, risk, effort.

---

## PHASE 5: OUTPUT GENERATION (Actionable Deliverables)

**Goal:** Produce structured, actionable outputs for immediate use.

**Estimated Tool Calls:** 0-5 (mostly synthesis)

### 5.1 Executive Summary

**Format:**

```markdown
## Executive Summary

**Repo Health Score:** X/100

| Component | Score | Status | Notes |
|-----------|-------|--------|-------|
| CI Gates | <score>/100 | ✅/⚠️/❌ | <actual make check result> |
| Module Health | <score>/100 | ✅/⚠️/❌ | <actual>/<total> modules import correctly |
| Documentation Accuracy | <score>/100 | ✅/⚠️/❌ | <count> docs with drift |
| Rigor Compliance | <score>/100 | ✅/⚠️/❌ | <count>/<total> analysis notebooks have tests |
| Boundary Compliance | <score>/100 | ✅/⚠️/❌ | <violations found or "No violations"> |
| Test Coverage | <score>/100 | ✅/⚠️/❌ | <empty stubs count>, <total test files> |

**Key Achievements Since Last Review:**
<populate from `git log` between last review and HEAD — do not copy examples from this template>

**Blockers:**
<list any CRITICAL issues, or "None">

**High-Priority Issues (Immediate Attention Required):**
<top 3-5 issues from Phase 4, with evidence>
```

### 5.2 Verification Evidence

**Format:** Command → Output → Assessment table

If any command could not be run (no CLI), record it with "NOT RUN" and explain why.

| Verification | Command | Output | Status |
|--------------|---------|--------|--------|
| Module count | `ls -d src/bid_euchre/*/ \| grep -v __pycache__ \| wc -l` | `<actual>` | ✅/⚠️/❌ |
| Config count | `ls experiments/configs/*.yaml \| wc -l` | `<actual>` | ✅/⚠️/❌ |
| Suite count | `ls experiments/suites/*.yaml \| wc -l` | `<actual>` | ✅/⚠️/❌ |
| Script count | `ls scripts/*.py \| wc -l` | `<actual>` | ✅/⚠️/❌ |
| Test count | `find tests -name "test_*.py" \| wc -l` | `<actual>` | ✅/⚠️/❌ |
| Latest PR | `gh pr list --state merged --limit 1` | `<actual>` | ✅/⚠️/❌ |
| CI gates | `make check` | `<PASSED/FAILED>` | ✅/⚠️/❌ |
| Core imports | (see Phase 1.3) | `<OK/FAIL>` | ✅/⚠️/❌ |
| Repo-linter rules | `grep -c "^def check_" scripts/lint_repo.py` | `<actual>` | ✅/⚠️/❌ |

### 5.3 Issue Registry

**Format:** Structured table with evidence

| ID | Severity | Location | Issue | Evidence | Recommendation |
|----|----------|----------|-------|----------|----------------|
| I001 | `<severity>` | `<file:line>` | `<description>` | `<command or quote>` | `<specific fix>` |

### 5.4 Cleanup Plan

**Format:** PR sequence with dependencies (only if issues warrant PR sequencing).
Only include if requested or if ≥1 critical issue requires sequencing.

```markdown
## Cleanup Plan — PR Sequence (Template)

**PR — <title>**
- **Files:** <list files>
- **Goal:** <outcome tied to model training/evaluation/reproducibility>
- **Acceptance:** `make check` passes + <specific criteria>
- **Effort:** Trivial/Small/Medium/Large
- **Dependencies:** <if any>
```

### 5.5 Rigor Assessment

**Format:** Quantitative rigor metrics (template; populate only if relevant)

```markdown
## Rigor Assessment (Template)

### Sample Size Coverage
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| <metric> | <value> | <threshold> | ✅/⚠️/❌ |

### Statistical Test Coverage
| Notebook Category | With Tests | Total | Coverage | Status |
|-------------------|------------|-------|----------|--------|
| <category> | <x>/<y> | <y> | <pct> | ✅/⚠️/❌ |

### Fail-Fast Gate Coverage
| Location | Gates Found | Status |
|----------|-------------|--------|
| <location> | <count> | ✅/⚠️/❌ |

### Anti-Pattern Detection
| Anti-Pattern | Count | Examples | Status |
|--------------|-------|----------|--------|
| <pattern> | <count> | <examples> | ✅/⚠️/❌ |

### Gold Standard Checklist Compliance (Production/Decision)
| Criterion | Pass Rate | Status |
|-----------|-----------|--------|
| <criterion> | <pct> | ✅/⚠️/❌ |

**Actions (Optional):** Only for production/decision artifacts.
```

### 5.6 Documentation Roadmap (Optional)

**Only include if requested or if ≥1 critical issue requires sequencing.**

```markdown
## Documentation Roadmap (Template)

**Priority 1 (Immediate):**
- <doc> — <specific fix>

**Priority 2 (High):**
- <doc> — <specific fix>

**Priority 3 (Medium):**
- <doc> — <specific fix>

**New Docs Needed (Optional):**
- <doc> — <purpose>
```

### 5.7 Development Roadmap (Optional)

**Only include if requested or if ≥1 critical issue requires sequencing.**

```markdown
## Development Roadmap (Template)

**Next 3-5 PRs (Optional):**
- PR — <title> (scope, files, acceptance, effort, risk)

**Medium-Term Milestones (Optional):**
- <milestone> — <goal> — <target>

**Long-Term Vision (Optional):**
- <vision item>
```

---

## CONSTRAINTS

**No Hardcoded Repo Facts:**
- ❌ Do not embed fixed counts, PR numbers, or file lists as ground truth in review output
- ✅ Use tool-driven discovery to determine current state at review time
- ✅ Every claim about repo structure must be verified by the reviewing agent at runtime

**Prompt Freshness Checks:**
- ✅ Verify every referenced script and CLI flag exists before using it
- ✅ Do not include fixed counts in output unless generated during this review run
- ✅ Mark unverifiable commands as `NOT RUN` with reason
- ✅ If a command in this prompt fails, note it as a prompt staleness issue in the Issue Registry

**Discovery Over Assumptions:**
- ✅ Use tools to verify current state
- ❌ Do not rely on hardcoded expectations
- ✅ Filesystem is authoritative, not this document

**Evidence Required:**
- ✅ Every claim needs verification (command output, file quote, line ref)
- ❌ No assertions without proof
- ✅ Show command → output → assessment

**CI Required:**
- ✅ Always run `make check` and report results
- ❌ Do not skip CI in reviews

**Recommendation Scope:**
- ✅ Default to top 5 issues by impact (expand only if requested)
- ❌ Avoid speculative or low-outcome recommendations

**Small PRs:**
- ✅ Propose incremental, low-risk changes
- ❌ No multi-concept mega-PRs
- ✅ Clear acceptance criteria per PR

**Determinism First:**
- ✅ Any changes must preserve reproducibility
- ❌ No unseeded experiments in production
- ✅ Seed enforcement is non-negotiable

**Agent-Friendly Output:**
- ✅ Write clear, executable acceptance criteria
- ❌ No ambiguous "improve X" tasks
- ✅ Specific commands agents can verify

---

## PRIORITIES (Ranked)

### 1. Agent Execution Correctness (Highest)

**Rigor first, accessibility second.** See `.claude/rules/05_rigor.md` for philosophy.

- **Statistical validity:** Sample sizes, hypothesis tests, confidence intervals, effect sizes
- **Reproducibility:** Deterministic experiments, explicit seeds, version-controlled configs
- **Fail-fast validation:** Assert-style sanity gates, early error detection
- **Hard gates:** CI must pass, no committed artifacts, strict boundaries
- **Gold-path commands:** `make check`, canonical runner only
- **No global randomness:** Local RNG instances for determinism
- **Drift detection:** Regression protection for baselines

### 2. Rigor Enforcement

- **Sample size adequacy:** Flag n_per < 2000 as critical for inference claims
- **Statistical test coverage:** No "looks balanced" without ANOVA/chi-square
- **Confidence intervals:** All reported metrics need uncertainty quantification
- **Anti-pattern elimination:** No hardcoded seats/trumps, no visual-only validation
- **Confounder control:** Balance factors, randomize assignments, document limitations
Note: Apply rigor requirements to production or decision-making artifacts.
Exploratory notebooks may be flagged but are not required to meet full rigor gates.

### 3. Repo Cleanup

- **Reduce ambiguity:** Clear "where code goes" guidelines
- **Delete or update stale docs:** No drift between docs and reality
- **Quarantine safely:** Deprecate in `_deprecated/`, delete later
- **Consolidate structure:** Minimize competing canonical paths
- **Import hygiene:** Enforce layer boundaries strictly

### 4. Documentation Completeness

- **Operational docs:** Copy/paste commands that work
- **Contract clarity:** Clear schemas, invariants, acceptance criteria
- **Minimal narrative:** Focus on contracts, not stories
- **Alignment with gates:** Docs must reflect CI enforcement

### 5. Roadmap Clarity

- **Small PRs, clear acceptance:** Agent-executable criteria
- **Staged improvements:** Low risk, incremental value
- **Stabilize before expanding:** No new features until rigor standards met

---

## GOLD PATH COMMANDS

These are the **blessed canonical commands** for this repo. Run `make help` for the complete, up-to-date target list.

**Authoritative sources:** `Makefile`, `docs/02_agent/AGENTS.md`, `.claude/CLAUDE.md`

### CI Validation

```bash
# Run all CI checks (required before PR)
# Composition: repo-lint + lint + test + notebook-check + docs-check
make check

# Individual checks
make repo-lint      # Repository linter (derive rule count from source)
make lint           # Ruff check (lint only)
make test           # Pytest fast suite
make notebook-check # Jupytext sync + outputs cleared
make docs-check     # Documentation freshness gate
```

### Experiment Execution

```bash
# Seeded experiment (production)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/<config>.yaml --n_per 2000

# Quick smoke test (exploratory only, not for inference)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/quick_test.yaml --n_per 200

# Dry-run validation (no simulation)
uv run python experiments/run_experiment.py --seed 42 --dry-run \
  --config experiments/configs/<config>.yaml
```

### Report Generation

```bash
# Generate report for a run
uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id>

# Regenerate existing report
uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id> \
  --overwrite
```

### Run Comparison

```bash
# Compare two runs with bootstrap statistics
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline_run_id> \
  --candidate data/runs/<candidate_run_id> \
  --seed 42 --n-bootstrap 10000 --format markdown
```

### Notebook Execution

```bash
# Execute notebooks in SMOKE mode (~10s, quick validation)
make notebook-run

# Execute notebooks in QUICK mode (~2-5min, more thorough)
make notebook-run-full
```

### Promotion Gate

```bash
# Run promotion gate (requires env vars — check Makefile for current interface)
make promotion-gate
```

### Bidding / Training Target Discovery

```bash
# Discover available bidding and training targets
make help | grep -i "bid\|train\|teacher\|loop"
```

### Config Validation

```bash
# Validate config files (auto-discovers configs; no positional args needed)
uv run python scripts/validate_configs.py
```

---

## CURRENT STRUCTURE (Orientation Only)

**Do not treat this as ground truth.** Use the discovery commands in Phase 1.1 to determine actual counts and contents.

**Authoritative sources:**
- `.claude/CLAUDE.md` — Session entrypoint
- `docs/01_core/ARCHITECTURE.md` — Module structure

```
bid-euchre/
├── .claude/                     # Claude Code session configuration
│   ├── CLAUDE.md                # Entrypoint (imports authoritative docs)
│   └── rules/                   # Session rules (rigor, workflow, determinism, data, PRs)
├── src/bid_euchre/              # Core library
│   ├── core/                    # Cards, deck, rules, trick logic
│   ├── sim/                     # Simulation engine
│   ├── strategy/                # AI strategies
│   ├── features/                # Hand evaluation + bidless features
│   ├── datasets/                # Dataset collectors
│   ├── models/                  # Model training/inference, splits, freeze
│   ├── diagnostics/             # Visualization, analysis, health checks, notebook validation
│   ├── reporting/               # Metrics, evaluation, charts, eligibility
│   ├── logging/                 # Structured game logging
│   ├── validation/              # Schema validation, promotion gates
│   ├── analysis/                # Statistical analysis, paired comparisons
│   ├── experiments/             # Config system, batch metadata
│   └── scoring.py               # Top-level scoring module
│   # (verify via: ls -d src/bid_euchre/*/ | grep -v __pycache__)
├── experiments/                 # Experiment configs + runner
│   ├── run_experiment.py        # THE canonical runner
│   ├── configs/                 # YAML experiment definitions
│   ├── suites/                  # Suite definitions
│   └── _deprecated/             # Frozen (legacy, do not modify)
│   # (verify via: ls experiments/configs/*.yaml | wc -l)
├── scripts/                     # Blessed tooling entrypoints
│   ├── internal/                # Internal-only scripts
│   └── *.py                     # Top-level blessed scripts
│   # (verify via: ls scripts/*.py | wc -l)
├── tests/                       # Test suite
│   ├── unit/                    # Fast, isolated tests
│   ├── integration/             # Multi-component tests
│   ├── property/                # Property-based tests (Hypothesis)
│   └── performance/             # Benchmarks
│   # (verify via: find tests -name "test_*.py" | wc -l)
├── notebooks/                   # Interactive analysis
│   ├── arc_d/                   # Arc D evaluation notebooks (r0/, r1/, ...)
│   ├── phase0_bidless/          # Bidless analysis notebooks
│   ├── sandbox/                 # Exploratory notebooks and blog charts
│   └── _templates/              # Notebook templates
│   # (verify via: find notebooks -name "*.ipynb" -not -path "*/archive/*" | wc -l)
├── docs/                        # Documentation
│   ├── 01_core/                 # Architecture, contracts, specs
│   ├── 02_agent/                # AI agent guidelines (incl. this file)
│   ├── 03_TODO/                 # Task tracking + reviews
│   ├── 05_experiments/          # Experiment operational docs
│   ├── 04_reports/              # Consolidated reports
│   ├── archive/                 # Historical/frozen docs (do not modify)
│   ├── images/                  # Documentation images (SVG, etc.)
│   └── FLOW_DIAGRAM.md          # Top-level flow diagram (not in 01_core/)
├── data/
│   ├── fixtures/                # Committed test fixtures (≤100KB each)
│   └── runs/                    # Generated outputs (gitignored)
├── Makefile                     # Gold path commands (run `make help`)
├── pyproject.toml               # Project config
└── .github/
    ├── workflows/ci.yml         # CI pipeline
    └── pull_request_template.md # PR template (required)
```

---

## DEVELOPMENT MILESTONES (Historical Context, Non-Normative)

**These milestones document architectural epochs. They are historical context only — verify current state via `git log` and `gh pr list`.**

| Era | PRs | Theme | Key Outcomes |
|-----|-----|-------|-------------|
| **Foundation** | #1–29 | CI, determinism, contracts | Stable infrastructure, repo-linter, gold paths |
| **Baseline** | #30–81 | Drift detection, scoring | Automated regression detection, metric rollup |
| **Bidding** | #82–143 | Policies, datasets, training | Full bidding system, auction mode, B1 models |
| **Bidless** | #144–155 | Hand value features | Arc B foundation, bidless dataset, feature engineering |
| **Validation & Rigor** | #156–190 | Schema validation, rigor enforcement | Quality gates hardened, statistical rigor, notebook standards |
| **Bidless Production** | #191–249 | Canonical bidless dataset, GluttonStrategy | Paired analysis, play policy gates, outcomes dataset |
| **Arc B Bidding** | #250–290 | OLSa bidders, teacher policies | 16 bidding PRs, model training, strategy registration |
| **Arc C Infrastructure** | #310–323 | Batch metadata, promotion workflow | Eligibility engine, split manifests, artifact freeze, CI gates |
| **Promotion Hardening** | #324–332 | Freeze enforcement, registry lint | Content-based hash validation, workflow automation, 7 skills |
| **Phase 0 Report** | #333–345 | Report charts, diagnostics, skill audit | 5 chart suites, contract-faceted analysis, Phase 0 report r4 |
| **Phase 0 Hardening** | #346–357 | Docs freshness CI, /review skill, feature rename, report corrections | docs-check gate, self-healing review prompt, offsuit_non_ace_count, stale metric fixes |
| **Feature Review** | #358–369 | Feature trimming, pre-Phase-1 cleanup | 41→39 features, LTC/quick_tricks added, 4 redundant removed |
| **HITL Notebook Gates** | #370–376 | Notebook evaluation template, semantic gate engine | 12-check gate (2 tiers), model rung report template, eligibility engine |
| **Arc D Planning** | #377–388 | OLSa-Hybrid bidder plan, execution plan v3 | 18-PR plan across 10 waves, 31 review decisions |
| **Arc D Implementation** | #389–396 | Hybrid OLSa bidder, off/def sub-models, gate runner, reporting | HybridOLSaBidder, off/def R5a architecture, Arc D gate runner, 3 opt-in gate checks |
| **R0 Eval & Reporting** | #397–416 | Eval redesign, comparator battery, R0 baseline lock | JSONL eval parser, comparator battery, R0 promotion, report upgrade |
| **R0 Notebooks** | #417–438 | Notebook templates, instantiation, review fixes | 5 notebook templates, 9 review-fix PRs, formal reports, auction health |
| **R0→R1 Transition** | #439–446 | H2H battery, ablation, gate calibration | OLSaBidder dual-format, H2H battery runner, threshold calibration |

**Current state:** Derive via:

```bash
gh pr list --state merged --limit 1 --json number --jq '.[0].number'
git rev-list --count HEAD
git log --oneline -5
```

---

## REPO-LINTER RULES

**Source of truth:** `scripts/lint_repo.py`

Do not rely on a hardcoded rule list. Derive the current rules from source:

```bash
# Count rules
grep -c "^def check_" scripts/lint_repo.py

# List all rule names
grep "^def check_" scripts/lint_repo.py | sed 's/def //; s/(.*//;'

# Run the linter
make repo-lint
```

**Rule categories** (stable, unlikely to drift):

| Category | Purpose |
|----------|---------|
| **Data policy** | Prevent artifact leakage; fixture allowlist and size limits |
| **Import boundaries** | `src/` isolation from `experiments/` and `tests/`; no `sys.path.insert`; no `import experiments` package |
| **Determinism** | No global `random.*` in `src/`; experiments require `--seed` |
| **Code quality** | No empty test stubs; no `argparse` in `src/` |
| **Workflow** | Frozen folders (`_deprecated/`, `comparisons/`, `training/`); no `.DS_Store` |
| **Promotion** | Artifact freeze checks (`frozen_at` + `artifact_sha256`); gate artifact schema; split manifest schema; registry consistency |

---

## OUTPUT FORMAT (Required Deliverables)

Your review output **MUST** include all sections below in this order:

### 1. Executive Summary
- Repo Health Score (X/100 with component breakdown)
- Key achievements since last review (derive from git log)
- Blockers (if any)
- High-priority issues (top 3-5; keep to top 5 by impact)

### 2. Verification Evidence
- Table: Command → Output → Status
- Include all verification commands run in Phase 2
- All counts and values must be from this review run (not copied from templates)

### 3. Issue Registry
- Table: ID | Severity | Location | Issue | Evidence | Recommendation
- Default: include top 5 issues by impact (expand only if requested)
- Sort by severity (CRITICAL → HIGH → MEDIUM → LOW)

### 4. Cleanup Plan (Optional)
- Include only if issues warrant PR sequencing
- PR sequence with clear scope, files, acceptance criteria
- Dependencies diagram (if applicable)
- Effort estimates (Trivial/Small/Medium/Large)

### 5. Rigor Assessment
- Sample size coverage table (production/decision artifacts vs exploratory)
- Statistical test coverage table (production/decision artifacts vs exploratory)
- Fail-fast gate coverage
- Anti-pattern detection results
- Gold standard checklist compliance
Note: Apply rigor requirements to production or decision-making artifacts.
Exploratory notebooks may be flagged but are not required to meet full rigor gates.

### 6. Documentation Roadmap (Optional)
- Priority 1 (immediate), Priority 2 (high), Priority 3 (medium)
- New docs needed
- Stale docs to update/delete

### 7. Development Roadmap (Optional)
- Next 5 PRs (detailed with acceptance criteria)
- Medium-term milestones (3-6 months)
- Long-term vision (6-12 months)

---

## ERROR HANDLING PROTOCOL

**If a verification command fails:**

1. **Record the failure** in the verification evidence table
2. **Classify severity** (CRITICAL if CI gate, HIGH if contract violation, MEDIUM otherwise)
3. **Add to issue registry** with specific error message
4. **Propose fix** in cleanup plan with acceptance criteria
5. **Continue review** (do not halt on first failure)

**Exception:** If `make check` fails, stop the review after recording the failure
summary and do not proceed to later phases unless explicitly asked.

**If a tool call fails:**

1. **Retry once** with adjusted parameters
2. **Document the error** in output
3. **Use alternative tool** if available (e.g., Read instead of Bash)
4. **Note limitation** in executive summary

**If a doc reference is stale:**

1. **Note the drift** in issue registry
2. **Use filesystem as ground truth** (not the stale doc)
3. **Add doc update to cleanup plan**

**If a command from this prompt fails:**

1. **Note it as a prompt staleness issue** in the issue registry
2. **Record the actual working command** if you can determine one
3. **Continue with alternative verification**

---

## AGENT EXECUTION TIPS

**Phased Execution:**
- Complete each phase fully before moving to next
- Each phase builds on previous (Discovery → Verification → Analysis → Output)
- Estimated total tool calls: 60-90 across all phases

**Parallel vs Sequential:**
- **Parallel:** Structure discovery (all `ls`/`wc` commands), module imports (independent)
- **Sequential:** Verification commands (some depend on previous output), issue analysis

**Discovery Over Hardcoding:**
- **Always verify:** Config counts, module lists, script names
- **Never assume:** Use tools even for "known" values
- **Filesystem is truth:** If doc disagrees with `ls`, trust `ls`

**Evidence Chain:**
- **Command → Output → Assessment:** Show your work
- **Quote line numbers:** `file.py:45` not just "file.py"
- **Include context:** Show 3-5 lines around issue, not just the line

**Rigor Focus:**
- Lead with statistical validity checks (Phase 2.2, Phase 3.4)
- Flag visual-only validation as HIGH severity
- Treat inadequate sample sizes as blockers for inference claims
- Quantify rigor metrics (percentages, counts, not "some" or "many")

---

*Template version: 3.4 (Drift-Resilient, Discovery-Driven)*
*Previous versions: 3.3 (February 18, 2026), 3.2, 3.1 (February 4, 2026), 3.0 (February 1, 2026)*
