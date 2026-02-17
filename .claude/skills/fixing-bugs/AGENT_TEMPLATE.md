# Bug Fix Agent Template

Each spawned agent receives instructions in this format:

```markdown
## Bug Fix Agent: [Category]

**Failure**: [error type] in [module]

**Your Mission**:
1. Read the failing test: [test file path]
2. Read relevant source: [source file path]
3. Implement minimal fix (don't over-engineer)
4. Run affected tests: `uv run pytest tests/path/to/test.py::test_name`
5. If fix reveals cascading failure, fix that too
6. Report final diff

**Constraints**:
- Fix only what's broken
- Prefer simple solutions
- Don't refactor unrelated code
- Run tests after each change

**Exit Criteria**:
All affected tests passing, diff reported back.
```
