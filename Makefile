.PHONY: help sync repo-lint lint test check notebook-sync notebook-check notebook-run notebook-run-full docs-check promotion-gate bid-train-teachers bid-eval-tiny bid-loop bidless-diagnostics
.DEFAULT_GOAL := help

PYTHON ?= uv run python
REPO_LINT_BASE ?= origin/main
REPO_LINT_HEAD ?= HEAD

# Teacher baseline loop configuration
TEACHERS ?= strict_raiser heuristics
CONTRACTS ?= C D H S HIGH LOW
RUN_BASE ?= data/runs
SEED ?= 42
N_PER ?= 20

help:
	@echo ""
	@echo "Setup:"
	@echo "  make sync               - install dependencies with uv"
	@echo ""
	@echo "Gold path targets:"
	@echo "  make check              - repo-lint + ruff + tests"
	@echo "  make repo-lint          - repo linter (diff vs origin/main)"
	@echo "  make lint               - ruff check ."
	@echo "  make test               - pytest fast suite"
	@echo "  make notebook-sync      - sync paired notebooks (Jupytext)"
	@echo "  make notebook-check     - verify sync + outputs cleared"
	@echo "  make notebook-run       - execute notebooks (SMOKE mode, ~10s)"
	@echo "  make notebook-run-full  - execute notebooks (QUICK mode, ~2-5min)"
	@echo "  make docs-check         - docs freshness gate (path refs + script list)"
	@echo "  make promotion-gate     - repo-lint + notebook gate (for promotion PRs)"
	@echo ""
	@echo "Teacher baseline targets:"
	@echo "  make bid-train-teachers - train teacher artifacts (all contracts)"
	@echo "  make bid-eval-tiny      - run bid_eval_tiny suite"
	@echo "  make bid-loop           - train teachers then eval tiny"
	@echo ""
	@echo "Diagnostics:"
	@echo "  make bidless-diagnostics DATASET_DIR=path/to/datasets"
	@echo ""

sync:
	@echo ">>> Syncing dependencies with uv"
	uv sync

repo-lint:
	@echo ">>> Repo linter"
	$(PYTHON) scripts/lint_repo.py --base $(REPO_LINT_BASE) --head $(REPO_LINT_HEAD)

lint:
	@echo ">>> Ruff"
	$(PYTHON) -m ruff check .

test:
	@echo ">>> Pytest (fast suite)"
	PYTHONPATH=.:src $(PYTHON) -m pytest -m "not slow" tests/

check: repo-lint lint test notebook-check docs-check
	@echo "✓ All checks passed"

notebook-sync:
	@echo ">>> Jupytext sync (notebooks)"
	$(PYTHON) -c "import glob, subprocess, sys; files=sorted(glob.glob('notebooks/**/*.ipynb', recursive=True)); sys.exit(0) if not files else None; cmd=[sys.executable, '-m', 'jupytext', '--sync', *files]; sys.exit(subprocess.call(cmd))"

notebook-check:
	@echo ">>> Notebook hygiene checks"
	$(PYTHON) -c "import glob, subprocess, sys; files=sorted(glob.glob('notebooks/**/*.ipynb', recursive=True)); sys.exit(0) if not files else None; cmd=[sys.executable, '-m', 'jupytext', '--sync', *files]; code=subprocess.call(cmd); sys.exit(code) if code else None; cmd=[sys.executable, '-m', 'nbstripout', '--verify', *files]; sys.exit(subprocess.call(cmd))"
	@git diff --exit-code -- notebooks/

notebook-run:
	@echo ">>> Executing notebooks (SMOKE mode)"
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode smoke

notebook-run-full:
	@echo ">>> Executing notebooks (QUICK mode)"
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode quick

docs-check:
	@echo ">>> Docs freshness check"
	$(PYTHON) scripts/check_docs_freshness.py

promotion-gate: repo-lint
	@echo ">>> Promotion gate (notebook execution + gate artifact)"
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode smoke --gate-output-dir /tmp/notebook_review/
	$(PYTHON) -c "import json; g=json.load(open('/tmp/notebook_review/notebook_gate.json')); assert g['overall_status']=='PASS', f'Notebook gate: {g[\"overall_status\"]}'"
	@echo "✓ Promotion gate passed"

# Generate unique run ID for teacher training
TEACHER_RUN_ID = teacher_baseline_$(shell date -u +%Y%m%d_%H%M%S)_$(shell printf "%04x" $$RANDOM)

bid-train-teachers:
	@echo ">>> Training teacher artifacts"
	@echo "Run ID: $(TEACHER_RUN_ID)"
	@echo "Teachers: $(TEACHERS)"
	@echo "Contracts: $(CONTRACTS)"
	@echo "Output base: $(RUN_BASE)/$(TEACHER_RUN_ID)/artifacts/"
	@mkdir -p $(RUN_BASE)/$(TEACHER_RUN_ID)/artifacts
	@for teacher in $(TEACHERS); do \
		for contract in $(CONTRACTS); do \
			echo "Training $$teacher/$$contract..."; \
			PYTHONPATH=src $(PYTHON) scripts/train_bidder.py \
				--teacher $$teacher \
				--contract $$contract \
				--output $(RUN_BASE)/$(TEACHER_RUN_ID)/artifacts/$$teacher-$$contract.json \
				--seed $(SEED); \
		done; \
	done
	@echo "✅ Teacher training complete"
	@echo "Artifacts written to: $(RUN_BASE)/$(TEACHER_RUN_ID)/artifacts/"

bid-eval-tiny:
	@echo ">>> Running bid_eval_tiny suite"
	@echo "Suite: experiments/suites/bid_eval_tiny.yaml"
	@echo "Seed: $(SEED)"
	@echo "N_PER: $(N_PER)"
	PYTHONPATH=src $(PYTHON) scripts/run_suite.py \
		--suite experiments/suites/bid_eval_tiny.yaml \
		--seed $(SEED) \
		--n-per $(N_PER)
	@echo "✅ bid_eval_tiny complete"
	@echo "Find latest run in: $(RUN_BASE)/"

bid-loop: bid-train-teachers bid-eval-tiny
	@echo "✅ Teacher baseline loop complete"

# Bidless diagnostics
DATASET_DIR ?= data/runs/latest/datasets

bidless-diagnostics:
	@echo ">>> Running bidless diagnostics"
	@echo "Dataset: $(DATASET_DIR)"
	PYTHONPATH=src $(PYTHON) scripts/run_bidless_diagnostics.py --dataset $(DATASET_DIR)
