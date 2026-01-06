.PHONY: help repo-lint lint test check
.DEFAULT_GOAL := help

PYTHON ?= python
REPO_LINT_BASE ?= origin/main
REPO_LINT_HEAD ?= HEAD

help:
	@echo ""
	@echo "Gold path targets:"
	@echo "  make check      - repo-lint + ruff + tests"
	@echo "  make repo-lint  - repo linter (diff vs origin/main)"
	@echo "  make lint       - ruff check ."
	@echo "  make test       - pytest fast suite"
	@echo ""

repo-lint:
	@echo ">>> Repo linter"
	$(PYTHON) scripts/lint_repo.py --base $(REPO_LINT_BASE) --head $(REPO_LINT_HEAD)

lint:
	@echo ">>> Ruff"
	$(PYTHON) -m ruff check .

test:
	@echo ">>> Pytest (fast suite)"
	PYTHONPATH=.:src $(PYTHON) -m pytest -m "not slow" tests/

check: repo-lint lint test
	@echo "✓ All checks passed"
