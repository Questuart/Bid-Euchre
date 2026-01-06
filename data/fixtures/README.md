# Fixtures Policy

This directory contains **tiny, intentional test fixtures** that are committed to the repository.

## Rules

1. **Fixtures must be referenced by tests or docs**
   - Each fixture must have a clear purpose
   - Document where it's used (test file path or doc reference)

2. **Keep fixtures small**
   - Recommend: <100KB per file
   - Total: <1MB for all fixtures
   - If a fixture exceeds these limits, it probably doesn't belong here

3. **Good examples** (what belongs here):
   - Tiny deterministic deal samples (for deterministic tests)
   - Tiny expected-summary JSON files (for output validation)
   - Expected test outputs (small JSON/text files)
   - Minimal config examples referenced by docs

4. **Bad examples** (what does NOT belong here):
   - Training CSVs (use `data/runs/<run_id>/` instead)
   - Dashboards or PNGs (generated outputs)
   - JSONL logs (generated outputs)
   - Full run outputs (use `data/runs/<run_id>/` instead)
   - Model binaries or pickles (generated artifacts)

## Adding a new fixture

When adding a fixture:
1. Ensure it's truly needed (can't generate it in the test?)
2. Keep it as small as possible
3. Document its purpose here:

### Current fixtures

*No fixtures yet. Add entries here as fixtures are added.*

**Format**:
- `filename.ext` - Brief description, used by `path/to/test_file.py::test_name`
