.PHONY: help sync repo-lint lint test check bid-train-teachers bid-eval-tiny bid-loop bidless-diagnostics
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

check: repo-lint lint test
	@echo "✓ All checks passed"

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
