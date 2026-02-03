# Quality Bar for Bid Euchre Repository

## Code Quality Standards

- **Determinism Required**: All experiments and simulations must produce identical results for identical seeds and configs. No global randomness in hot paths.

- **Scope Lock**: Changes must stay within their declared scope. No drive-by cleanups or refactoring unrelated to the PR goal.

- **Proof Provided**: Every behavioral change must include reproduction commands, test results, and validation proof in the PR description.

- **No Artifact Commits**: Never commit generated files under `data/runs/` or `data/reports/`. These are ignored by design.

- **Contract Compliance**: Changes to rules, logging, or metrics must comply with `docs/01_core/` contracts. Violating these breaks downstream analysis.

- **Test Coverage**: Core changes (rules, scoring, simulation) require unit tests. Strategy changes require deterministic smoke tests.

- **Clean Imports**: `src/` modules cannot import from `experiments/` or `tests/`. Maintain architectural boundaries.

- **Lint Compliance**: All code must pass `make repo-lint` and `make lint`. No exceptions for formatting or import violations.

- **Documentation Sync**: Code changes that affect contracts must update corresponding `docs/01_core/` documentation.

- **Performance Conscious**: Simulation and strategy code should be efficient. Performance regressions require justification and benchmarks.

- **Reproducible Experiments**: All experimental results must be reproducible with exact commands, seeds, and configs provided in PRs.

- **Single Responsibility**: One concept per PR. Mixed changes (refactor + feature) are not allowed.
