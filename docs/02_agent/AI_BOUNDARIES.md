# AI Agent Boundaries

**Hard rules for AI agents working in this repository.**

For detailed workflow guidance, see [AGENTS.md](AGENTS.md).
For system structure, see [docs/01_core/ARCHITECTURE.md](../01_core/ARCHITECTURE.md).

---

## Never Do (Hard Constraints)

### ❌ Do not create new experiment runners
**Use**: `experiments/run_experiment.py` (the canonical runner)

**Rationale**: Multiple competing entrypoints create confusion and maintenance burden.

### ❌ Do not put CLI scripts in `src/`
**Rule**: `src/` is library code only. CLI entrypoints belong in `scripts/` or `experiments/`.

**Rationale**: Library code must be importable without side effects.

### ❌ Do not commit generated outputs
**Forbidden paths**:
- `data/runs/**` — All experiment outputs
- `data/models/**` — Model binaries
- `data/training/**` — Training data
- `data/hand_logs/**` — Loose logs
- `data/reports/**` — Legacy reports
- `data/_deprecated/**` — Deprecated artifacts

**Allowed**: `data/fixtures/**` only (tiny, intentional test fixtures referenced by tests/docs)

**Rationale**: Generated artifacts bloat git history and conflict across runs.

### ❌ Do not edit or extend `experiments/_deprecated/`
**Rule**: Deprecated code is frozen. Do not add features or fix bugs in deprecated scripts.

**Rationale**: Deprecated code exists for backward compatibility only. Use canonical entrypoints instead.

---

## Always Do (Required Patterns)

### ✅ Require determinism by default
**Rule**: Experiments must specify `--seed` unless explicitly opting out via `--allow-nondeterministic`.

**Example (correct)**:
```bash
uv run python experiments/run_experiment.py --config <config> --seed 42 --n_per 100
```

**Example (exploration only)**:
```bash
uv run python experiments/run_experiment.py --config <config> --allow-nondeterministic --n_per 100
```

**Rationale**: Deterministic runs enable reproducibility and regression testing.

### ✅ Write outputs only inside run directories
**Rule**: All experiment outputs must be written under `data/runs/<run_id>/`.

**No writes to**:
- `data/reports/` (legacy)
- `data/models/` (legacy)
- Repository root or other top-level paths

**Rationale**: Keeps outputs isolated, reproducible, and git-ignored by default.

### ✅ Run `make check` before proposing PRs
**Required validation**:
```bash
make check          # Full output
make check-quiet    # Minimal output (preferred for agent workflows)
```

**Rationale**: Ensures consistency with CI gates. All PRs must pass these checks.

### ✅ Respect repo-linter rules
**Enforced by CI**:
- No edits to deprecated areas
- No committed artifacts
- No boundary violations (e.g., `src/` importing `experiments/`)

**Rationale**: Prevents technical debt accumulation.

---

## Canonical Commands for AI Agents

When running experiments and generating reports, use these exact invocation patterns:

```bash
# Run an experiment (always include --seed)
uv run python experiments/run_experiment.py \
  --config experiments/configs/<config>.yaml --seed 42

# Generate a report for a completed run
uv run python scripts/generate_report.py --run-dir data/runs/<run_id>

# Run a suite of experiments
uv run python scripts/run_suite.py \
  --suite experiments/suites/<suite>.yaml --seed 42

# Compare two runs
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline> --candidate data/runs/<candidate> --seed 42
```

**Do not** invoke `run_experiment.py` with flags it does not support (e.g., `--run-id`). The runner auto-generates run IDs with timestamps.

---

## References

- **Workflow guidance**: [docs/02_agent/AGENTS.md](AGENTS.md)
- **System structure**: [docs/01_core/ARCHITECTURE.md](../01_core/ARCHITECTURE.md)
- **Determinism requirements**: [docs/01_core/REPRODUCIBILITY.md](../01_core/REPRODUCIBILITY.md)
- **Data policy**: [docs/01_core/DATA_CONTRACT.md](../01_core/DATA_CONTRACT.md)
