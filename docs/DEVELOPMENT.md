# Development

## Quick start

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
~~~

## Local workflow

**Before committing:**

Pre-commit hooks run automatically on `git commit`:
- Repo linter (on changed files)
- Ruff (on changed files)
- File hygiene (trailing whitespace, etc.)

Pre-commit is **fast** and does **not** run the full test suite.

**Before opening a PR:**

~~~bash
make check
~~~

This runs the full suite including all tests.

## Make targets

| Command | Purpose |
|---------|---------|
| `make check` | Run all checks (same as CI) |
| `make repo-lint` | Repo rules (diff vs origin/main) |
| `make lint` | Ruff check . |
| `make test` | Fast pytest suite |
| `make help` | Show available targets |

## CI

CI runs the same Make targets:

1. `make repo-lint`
2. `make lint`
3. `make test`

This ensures local and CI use identical checks.
