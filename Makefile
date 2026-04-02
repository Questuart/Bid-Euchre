.PHONY: help sync ensure-venv repo-lint lint test check check-quiet check-gated notebook-sync notebook-check notebook-run notebook-run-full notebook-run-arc-d review-smoke review-quick review-full promotion-gate bid-train-teachers bid-eval-tiny bid-loop bidless-diagnostics docs-check browser-smoke
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
	@echo "  make check-quiet        - full check, minimal output (logs to tmpfile)"
	@echo "  make check-gated        - check-quiet with concurrency cap (max 3 lanes)"
	@echo "  make repo-lint          - repo linter (diff vs origin/main)"
	@echo "  make lint               - ruff check ."
	@echo "  make test               - pytest fast suite"
	@echo "  make notebook-sync      - sync paired notebooks (Jupytext)"
	@echo "  make notebook-check     - verify sync + outputs cleared"
	@echo "  make notebook-run       - execute notebooks (SMOKE mode, ~10s)"
	@echo "  make notebook-run-full  - execute notebooks (QUICK mode, ~2-5min)"
	@echo "  make notebook-run-arc-d - execute Arc D notebooks (SMOKE mode)"
	@echo "  make browser-smoke      - Playwright browser smoke suite (requires: pip install playwright && playwright install chromium)"
	@echo "  make review-smoke       - SMOKE test review infrastructure (~30s)"
	@echo "  make review-quick       - QUICK test review infrastructure (~5min, needs Codex auth)"
	@echo "  make review-full        - FULL test review infrastructure (~15min, needs Codex auth)"
	@echo "  make docs-check         - docs freshness gate (path refs + script list)"
	@echo "  make promotion-gate     - promotion CI gate (requires ARTIFACT_DIR + ROLLUP_JSON)"
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
	$(PYTHON) -m ruff check -q .

test:
	@echo ">>> Pytest (fast suite)"
	PYTHONPATH=.:src $(PYTHON) -m pytest -q -m "not slow and not browser" --ignore=tests/browser tests/

ensure-venv:
	@[ -d .venv ] || { echo ">>> Bootstrapping venv (fresh worktree detected)"; uv sync --extra dev; }

check: ensure-venv repo-lint lint test notebook-check docs-check
	@echo "✓ All checks passed"

check-quiet:
	@CHECK_LOG=$$(mktemp /tmp/make-check-XXXXXX); \
	echo ">>> Running full check (logs → $$CHECK_LOG)"; \
	if $(MAKE) check > "$$CHECK_LOG" 2>&1; then \
		echo "✓ All checks passed (details: $$CHECK_LOG)"; \
	else \
		echo "✗ Checks FAILED (full log: $$CHECK_LOG)"; \
		echo "--- Failure extract ---"; \
		grep -n -i -A 3 'FAILED\|ERROR\|error:\|failed' "$$CHECK_LOG" | head -40; \
		exit 1; \
	fi

# --- Gated check (caps concurrent make check across lanes) ---
CHECK_SEMAPHORE_DIR ?= /tmp/make-check-slots
MAX_CHECK_CONCURRENT ?= 3

check-gated:
	@mkdir -p $(CHECK_SEMAPHORE_DIR); \
	SLOT_FILE=$(CHECK_SEMAPHORE_DIR)/$$$$; \
	WAIT_COUNT=0; \
	while [ $$(ls $(CHECK_SEMAPHORE_DIR)/ 2>/dev/null | wc -l | tr -d ' ') -ge $(MAX_CHECK_CONCURRENT) ]; do \
		if [ $$WAIT_COUNT -eq 0 ]; then \
			echo ">>> Waiting for validation slot ($$(ls $(CHECK_SEMAPHORE_DIR)/ | wc -l | tr -d ' ')/$(MAX_CHECK_CONCURRENT) in use)..."; \
		fi; \
		WAIT_COUNT=$$((WAIT_COUNT + 1)); \
		sleep $$(( (RANDOM % 10) + 5 )); \
	done; \
	if [ $$WAIT_COUNT -gt 0 ]; then \
		echo ">>> Slot acquired after ~$$((WAIT_COUNT * 7))s wait"; \
	fi; \
	touch "$$SLOT_FILE"; \
	EXIT_CODE=0; \
	$(MAKE) check-quiet || EXIT_CODE=$$?; \
	rm -f "$$SLOT_FILE"; \
	exit $$EXIT_CODE

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

NOTEBOOK ?=

notebook-run-arc-d:
	@echo ">>> Executing Arc D notebooks (SMOKE mode)"
ifdef NOTEBOOK
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode smoke --pattern "$(NOTEBOOK)"
else
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode smoke --pattern "notebooks/arc_d/**/*.ipynb"
endif

review-smoke: ## SMOKE test review infrastructure (~30s)
	@echo ">>> Review infrastructure SMOKE test"
	PYTHONPATH=scripts/internal $(PYTHON) scripts/internal/test_review_infra.py --mode smoke

review-quick: ## QUICK test review infrastructure (~5min, needs Codex auth)
	@echo ">>> Review infrastructure QUICK test"
	PYTHONPATH=scripts/internal $(PYTHON) scripts/internal/test_review_infra.py --mode quick

review-full: ## FULL test review infrastructure (~15min, needs Codex auth)
	@echo ">>> Review infrastructure FULL test"
	PYTHONPATH=scripts/internal $(PYTHON) scripts/internal/test_review_infra.py --mode full

docs-check:
	@echo ">>> Docs freshness check"
	$(PYTHON) scripts/check_docs_freshness.py

browser-smoke: ensure-venv
	@echo ">>> Browser smoke suite (Playwright)"
	@$(PYTHON) -c "import playwright" 2>/dev/null || { echo "ERROR: playwright not installed."; echo "  Run: uv pip install playwright pytest-playwright && playwright install chromium"; exit 1; }
	PYTHONPATH=.:src $(PYTHON) -m pytest -q -m "browser" tests/browser/

GATE_OUTPUT_DIR ?= /tmp/promotion-gate-artifacts
ARTIFACT_DIR ?=
ROLLUP_JSON ?=
SPLIT_MANIFEST_DIR ?=
SEMANTIC_GATE_DIR ?=

promotion-gate: repo-lint
	@echo ">>> Promotion gate"
	@echo "Step 1: Notebook smoke with gate artifacts"
	PYTHONPATH=src $(PYTHON) scripts/run_notebooks.py --mode smoke --gate-output-dir $(GATE_OUTPUT_DIR)
	@echo "Step 2: Assert notebook gate PASS"
	$(PYTHON) -c "import json, sys; g=json.load(open('$(GATE_OUTPUT_DIR)/notebook_gate.json')); sys.exit(0 if g['gate_status']=='PASS' else 1)"
	@echo "Step 3: Verify artifact freeze and rollup binding"
	@if [ -z "$(ARTIFACT_DIR)" ] || [ -z "$(ROLLUP_JSON)" ]; then \
		echo "ERROR: ARTIFACT_DIR and ROLLUP_JSON are required for promotion gate."; \
		echo "Usage: make promotion-gate ARTIFACT_DIR=/path/to/artifacts ROLLUP_JSON=/path/to/rollup.json"; \
		exit 1; \
	elif [ ! -d "$(ARTIFACT_DIR)" ]; then \
		echo "ERROR: ARTIFACT_DIR not found: $(ARTIFACT_DIR)"; \
		exit 1; \
	elif [ ! -f "$(ROLLUP_JSON)" ]; then \
		echo "ERROR: ROLLUP_JSON not found: $(ROLLUP_JSON)"; \
		exit 1; \
	else \
		echo "  Validating rollup: $(ROLLUP_JSON)..."; \
		PYTHONPATH=src $(PYTHON) -c "import json, sys; r=json.load(open('$(ROLLUP_JSON)')); bp=r.get('batch',{}).get('batch_purpose',''); print(f'  Rollup batch_purpose={bp}'); sys.exit(0) if bp=='promotion' else (print('  WARNING: batch_purpose is not promotion'), sys.exit(0))[1]"; \
		echo "  Checking frozen status in $(ARTIFACT_DIR)..."; \
		PYTHONPATH=src $(PYTHON) -c "from bid_euchre.models.freeze import verify_frozen; import pathlib, sys; exempt={'meta.json','rollup.json','canonical_summary.json','training_metrics.json'}; artifacts=[p for p in pathlib.Path('$(ARTIFACT_DIR)').glob('*.json') if p.name not in exempt and not p.name.startswith('split_manifest')]; failed=[p.name for p in artifacts if not verify_frozen(p)]; print(f'  Checked {len(artifacts)} artifacts, {len(failed)} not verified'); sys.exit(1) if failed else sys.exit(0)"; \
	fi
	@if [ -n "$(SPLIT_MANIFEST_DIR)" ]; then \
		echo "Step 4: Validate split manifests in $(SPLIT_MANIFEST_DIR)"; \
		if [ ! -d "$(SPLIT_MANIFEST_DIR)" ]; then \
			echo "ERROR: SPLIT_MANIFEST_DIR not found: $(SPLIT_MANIFEST_DIR)"; \
			exit 1; \
		fi; \
		PYTHONPATH=src $(PYTHON) -c "import json, pathlib, sys; manifests=list(pathlib.Path('$(SPLIT_MANIFEST_DIR)').glob('split_manifest*.json')); bad=[m.name for m in manifests if json.load(open(m)).get('split_type')!='three_way']; print(f'  Checked {len(manifests)} manifests, {len(bad)} not three_way'); sys.exit(1) if bad else sys.exit(0)"; \
	fi
	@echo "Step 5: Validate semantic gate"
	@test -n "$(SEMANTIC_GATE_DIR)" || { echo "ERROR: SEMANTIC_GATE_DIR is required for promotion"; exit 1; }
	@test -f "$(SEMANTIC_GATE_DIR)/semantic_gate_val.json" || { echo "ERROR: semantic_gate_val.json not found"; exit 1; }
	@test -f "$(SEMANTIC_GATE_DIR)/semantic_gate_test.json" || { echo "ERROR: semantic_gate_test.json not found"; exit 1; }
	@PYTHONPATH=src $(PYTHON) -c "import json, sys; \
		v=json.load(open('$(SEMANTIC_GATE_DIR)/semantic_gate_val.json')); \
		t=json.load(open('$(SEMANTIC_GATE_DIR)/semantic_gate_test.json')); \
		ok = v['gate_status']=='PASS' and t['gate_status']=='PASS'; \
		print(f'  val={v[\"gate_status\"]}  test={t[\"gate_status\"]}'); \
		sys.exit(0 if ok else 1)"
	@echo "Promotion gate passed"

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
