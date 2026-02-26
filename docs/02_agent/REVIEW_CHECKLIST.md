# Pre-PR Review Checklist

Before claiming a PR is "done," ensure ALL of these are true:

- [ ] **Base Proof Verified**: Branch is based on main (`git merge-base --is-ancestor main HEAD`)
- [ ] **Scope Lock**: Only touched files explicitly declared in PR scope. No unrelated changes.
- [ ] **Diff Hygiene**: `git diff --name-only main...HEAD` shows only scoped files
- [ ] **Validation Run**: `make check` (or `make check-quiet`) passes OR `make repo-lint && make lint` passes
- [ ] **Tests Green**: At minimum `pytest -m "not slow"` passes
- [ ] **No Artifacts**: No generated files under `data/runs/` or `data/reports/` committed
- [ ] **PR Template Complete**: ALL "##" headers from `.github/pull_request_template.md` present in PR body
- [ ] **Repro Command**: Exact reproduction command with seed/config included in PR description
- [ ] **Clean Main Ready**: Can `git checkout main && git pull --ff-only origin main` successfully
- [ ] **Contract Compliance**: Changes to core rules/logging/metrics comply with `docs/01_core/` docs

Mark each box and provide proof in PR description.

## Quality Standards

These standards apply to all code changes in addition to the checklist above.

- **Clean Imports**: `src/` modules cannot import from `experiments/` or `tests/`. Maintain architectural boundaries.
- **Documentation Sync**: Code changes that affect contracts must update corresponding `docs/01_core/` documentation.
- **Performance Conscious**: Simulation and strategy code should be efficient. Performance regressions require justification and benchmarks.
- **Reproducible Experiments**: All experimental results must be reproducible with exact commands, seeds, and configs provided in PRs.
