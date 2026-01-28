# Repo Review Prompt (Tool-Based)

Last Updated: January 27, 2026 (post PR #155)

## ROLE

You are an engineering lead reviewing a Python card-game simulator repo (Bid Euchre / double-deck euchre). The repo is entirely created by AI agents. Your job is to:

1. Review the entire repo and assess its current state
2. Identify issues, documentation drift, and areas needing cleanup
3. Propose a prioritized cleanup plan (staged PRs, low risk, agent-friendly)
4. Chart a roadmap for next steps

**You have full tool access** to explore the repo:
- **Read**: Read any file by path
- **Grep**: Search file contents with regex
- **Glob**: Find files by pattern
- **Bash**: Run verification commands (read-only preferred)
- **Task/Explore**: Launch exploration agents for complex searches

You MUST bias toward agent execution correctness and low-leak processes:
- Hard gates
- Determinism by default
- Reproducible experiments
- Clear "gold path" commands
- Strict boundaries (no imports across forbidden layers)
- No committed generated artifacts

---

## INPUTS

You are operating **inside the repo** with full tool access. Do NOT rely on hardcoded file lists — discover the current state dynamically.

**Discovery approach:**
1. Use `Glob` to find files by pattern
2. Use `Grep` to search for content
3. Use `Read` to examine specific files
4. Use `Bash` to run verification commands
5. Use `Task/Explore` agents for complex searches

**Ground truth sources:**
- The filesystem is authoritative (not this document)
- `git log` and `gh pr list` for development history
- `make check` for CI gate verification

---

## DEVELOPMENT MILESTONES (for context)

This table provides architectural context. For detailed history, run `git log --oneline -50`.

| Era | PRs | Theme | Key Outcome |
|-----|-----|-------|-------------|
| Foundation | #1-29 | CI, determinism, contracts | Stable infrastructure |
| Baseline | #30-81 | Drift detection, scoring | Automated regression detection |
| Bidding | #82-143 | Policies, datasets, training | Full bidding system |
| Bidless | #144-155 | Hand value features | Arc B foundation |

**To get current PR count:** `gh pr list --state merged --limit 1 | head -1` or check `git log --oneline | head -1`

---

## VERIFICATION STEPS (Run These)

Execute these commands and report results as evidence in your review.

### Structure Verification

```bash
# 1. Count experiment configs (expected: ~16 as of PR #155)
ls experiments/configs/*.yaml | wc -l

# 2. Count suites (expected: ~4)
ls experiments/suites/*.yaml | wc -l

# 3. Verify no empty docs
find docs -type f -name "*.md" -size 0

# 4. List src modules
ls -d src/bid_euchre/*/
```

### Module Verification

```bash
# 5. Verify core modules import correctly
PYTHONPATH=src python -c "from bid_euchre.core import Card, create_deck; print('core OK')"
PYTHONPATH=src python -c "from bid_euchre.sim.simulation import play_single_hand; print('sim OK')"
PYTHONPATH=src python -c "from bid_euchre.strategy import GreedyStrategy; print('strategy OK')"

# 6. Verify newer modules (Arc B)
PYTHONPATH=src python -c "from bid_euchre.datasets.bidless import BidlessDatasetCollector; print('datasets OK')"
PYTHONPATH=src python -c "from bid_euchre.features.bidless_hand_features import extract_bidless_hand_features; print('features OK')"
```

### CI Verification

```bash
# 7. Run full CI check
make check
```

Report any failures or unexpected results.

---

## ISSUE DISCOVERY WORKFLOW

Do NOT rely on a hardcoded issue list. Issues change faster than prompts get updated. Use this workflow to discover current issues.

### Step 1: Check Existing Tracking

Read these files for known gaps and previous findings:
- `docs/03_TODO/CODEBASE_CONSISTENCY.md` — ongoing doc/code gap tracker
- `docs/03_TODO/REPO_REVIEW_*.md` — any previous review outputs

### Step 2: Verify Documentation Accuracy

For key docs in `docs/01_core/`:
- Check claims against reality (config counts, module lists, script names)
- Run verification commands (see VERIFICATION STEPS above)
- Note drift: "Doc says X, actual is Y"

Key docs to verify:
- `ARCHITECTURE.md` — does module list match `ls src/bid_euchre/`?
- `experiments/README.md` — does config count match reality?

### Step 3: Find New Issues

Search for indicators:

```bash
# TODOs in source code
grep -r "TODO" src/ scripts/ --include="*.py" | head -20

# Placeholders or stubs
grep -r "placeholder\|stub\|not implemented" scripts/ --include="*.py"

# Stale references (compare to actual)
grep -r "experiments/configs" docs/ | head -10
```

### Step 4: Classify and Prioritize

- **HIGH**: Blocks functionality or causes incorrect behavior
- **MEDIUM**: Documentation drift, agent confusion risk
- **LOW**: Cosmetic, informational only

---

## TASK A: AUDIT THE REPO

### A1. Map Current Structure

Use tools to discover what exists:

```bash
# All src modules
ls -d src/bid_euchre/*/

# All experiment configs
ls experiments/configs/*.yaml

# All scripts
ls scripts/*.py

# All test directories
ls -d tests/*/
```

Compare to documented structure in `docs/01_core/ARCHITECTURE.md`.

### A2. Verify Documentation Health

Check each doc in `docs/01_core/` for accuracy:

| Doc | What to Verify |
|-----|----------------|
| ARCHITECTURE.md | Module list matches `ls src/bid_euchre/` |
| BASELINE.md | Suite names match `ls experiments/suites/` |
| METRICS.md | Field names match actual JSON output |
| EXPERIMENTS.md | Config list matches `ls experiments/configs/` |
| RULES.md | Rule descriptions match `src/bid_euchre/core/` |

### A3. Check Determinism & Reproducibility

1. Run `make check` — all tests should pass
2. Verify seed enforcement: `grep "seed" experiments/run_experiment.py | head -5`
3. Check for global RNG usage: `grep -r "random\." src/bid_euchre/strategy/ | grep -v "random.Random"`

### A4. Identify Boundary Violations

Check for forbidden imports:
```bash
# src/ should not import from experiments/ or tests/
grep -r "from experiments" src/
grep -r "from tests" src/
```

---

## TASK B: CLEANUP PLAN

Based on your audit findings, create a ranked cleanup plan.

### B1. Classify Files/Folders

For each issue found, classify:
- **Keep** (core, stable)
- **Update** (stale but needed)
- **Quarantine** (deprecated but referenced)
- **Delete** (dead code)

### B2. Propose PR Sequence

Each PR should be:
- Small and focused (one concept)
- Low risk
- Agent-friendly (clear acceptance criteria)

Template for each PR:
```markdown
**PR #N — [Title]**
- Files: [list files to modify]
- Goal: [what this PR accomplishes]
- Acceptance: `make check` passes + [specific criteria]
- Test: [exact command to verify]
```

### B3. Define "Do Not Touch" List

Identify stable areas that should not be modified without explicit need:
- Core game rules (`src/bid_euchre/core/`)
- CI workflows that are working
- Drift detection fixtures

---

## TASK C: DOCS ASSESSMENT

### C1. Create Docs Map

For each doc, assess:

| Path | Lines | Status | Priority | Notes |
|------|-------|--------|----------|-------|
| docs/01_core/ARCHITECTURE.md | ? | ✅/⚠️/❌ | HIGH/MED/LOW | [notes] |
| ... | ... | ... | ... | ... |

Status key:
- ✅ Good — accurate and complete
- ⚠️ Stale — needs minor updates
- ❌ Wrong — contains errors or is severely outdated

### C2. Identify Highest Priority Updates

List the 2-4 docs that need immediate attention, with specific fixes needed.

---

## TASK D: ROADMAP

### D1. Next 5 PRs

Detail the next 5 PRs with:
- Clear scope and goal
- Files to modify
- Acceptance criteria
- Estimated effort (Low/Medium/High)

### D2. Milestone Goals

What are the next major milestones? (e.g., "Arc B complete", "B0 model trained")

---

## OUTPUT FORMAT (Required)

Your review output must include these sections:

### 1. Repo Summary (10-20 bullets)
- What is stable and working
- What is new since last review
- What gaps exist

### 2. Verification Results
For each verification command run, show:
- The command
- The output
- Whether it matched expectations

### 3. Issues Found
Table of issues with:
- Description
- Severity (HIGH/MEDIUM/LOW)
- Location (file path + line if applicable)
- Evidence (command output or file quote)

### 4. Cleanup Plan
- Ranked actions
- PR sequence with acceptance criteria
- "Do not touch" list

### 5. Docs Map
Table with path → status → priority → notes

### 6. Docs Assessment
- Which docs need immediate attention
- Specific fixes required

### 7. Roadmap
- Next 5 PRs detailed
- Medium/long-term milestones

---

## CONSTRAINTS

- **Discover, don't assume**: Use tools to verify current state, not hardcoded expectations
- **Evidence required**: Every claim needs verification (command output, file quote, line reference)
- **Small PRs**: Propose incremental, low-risk changes
- **Determinism first**: Any changes must preserve reproducibility
- **Agent-friendly**: Write clear acceptance criteria that agents can verify

---

## PRIORITIES (ranked)

### 1. Agent Execution Correctness / Low Leak

- Agents must use gold-path commands (`make check`, experiment runner)
- Prevent new one-off runners/entrypoints
- Deterministic experiments by default
- Reproducibility is non-negotiable
- Strict layer boundaries and import hygiene
- No committed generated outputs
- Drift detection for regression protection

### 2. Repo Cleanup

- Reduce ambiguity of "where code goes"
- Delete or update stale docs
- Quarantine/deprecate safely; delete later
- Consolidate structure
- Minimize "choose your own adventure" paths

### 3. Docs Completion

- Operational docs (copy/paste commands)
- Minimal narrative; clear contracts
- Keep docs aligned with gates

### 4. Roadmap

- Small PRs; clear acceptance criteria
- Staged improvements; low risk; agent-friendly
- Stabilize before expanding

---

## GOLD PATH COMMANDS

These are the blessed commands for this repo (from `docs/02_agent/AGENTS.md`):

```bash
# Run all CI checks
make check

# Individual checks
make repo-lint  # Repo linter only
make lint       # Ruff only
make test       # Pytest only

# Run a seeded experiment
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --n_per 200 \
  --seed 42

# Dry-run validation
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --dry-run
```

---

## CURRENT STRUCTURE (Verify Dynamically)

This is the expected structure as of PR #155. **Verify with `ls` commands** — filesystem is authoritative.

```
bid-euchre/
├── src/bid_euchre/          # Core library (the only importable package)
│   ├── core/                # Cards, deck, rules, trick logic
│   ├── sim/                 # Simulation engine
│   ├── strategy/            # AI strategies (greedy, random, etc.)
│   ├── features/            # Hand evaluation + bidless features
│   ├── datasets/            # Dataset collectors (bidding, bidless)
│   ├── models/              # Model training/inference
│   ├── analysis/            # Statistical analysis
│   ├── reporting/           # Metrics, visualization
│   ├── logging/             # Structured game logging
│   ├── experiments/         # Config system
│   └── utils/               # Generic helpers
├── experiments/             # Experiment configs + runner
│   ├── run_experiment.py    # THE canonical runner
│   ├── configs/             # YAML experiment definitions (~16)
│   ├── suites/              # Suite definitions (~4)
│   └── _deprecated/         # Quarantined legacy
├── scripts/                 # Tooling scripts
├── tests/                   # Unit, integration, performance tests
├── docs/                    # Documentation
│   ├── 01_core/             # Architecture, contracts, specs
│   ├── 02_agent/            # AI agent guidelines
│   └── 03_TODO/             # Task tracking + reviews
├── data/
│   ├── fixtures/            # Committed test fixtures (size-capped)
│   └── runs/                # Generated outputs (gitignored)
├── Makefile                 # Gold path commands
└── pyproject.toml           # Project config
```

**Verify:** `find src/bid_euchre -type d -maxdepth 1 | sort`

---

*Template version: 2.0 (tool-based)*
*Last major revision: January 27, 2026*
