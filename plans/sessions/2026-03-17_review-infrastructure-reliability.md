# Review Infrastructure Reliability

<!-- review-tier: medium -->

**Date:** 2026-03-17
**Status:** PROPOSED
**Scope:** Fix timeout failures, add diagnostic logging, add test coverage for plan review and PR review loops

---

## Problem

Both review loops share `_run_with_pty()` in `codex_plan_review_adapter.py`:

1. **Marginal timeouts:** Codex takes 187-229s; 300s timeout leaves 70-110s margin. Medium/governing plans exceed this. 5/9 plan reviews timeout. PR #757 also hit 3× Codex failure.
2. **Fragile output parsing:** 2/9 plan reviews fail with "unparseable output."
3. **No diagnostic logging:** Raw output not persisted; post-mortem impossible.
4. **Zero timeout test coverage:** Tests mock `_run_with_pty`, so the `returncode is None` branch is never exercised.

**Secondary (done):** `~/.codex/skills/review-handoff/SKILL.md` YAML fix applied out-of-band (unquoted colon in description).

## Evidence

| Key | Tier | Duration | Outcome |
|-----|------|----------|---------|
| d5f76ec7 | small | 187s | Success |
| 6b5779ad | medium | 229s | Success |
| 42eae5c3 | medium | 302s | Timeout (300s) |
| 9ddb0a76 | medium | 301s | Timeout (300s) |
| cce919ff | medium | 301s | Timeout (300s) |
| 7aeba3c2 | medium | 422s | Timeout (300+120s) |
| c3261aa6 | governing | 422s | Timeout (300+120s) |
| 4f3d1d8e | medium | 160s | Unparseable output |
| 786ea10c | medium | 217s | Unparseable output |

---

## Fix Plan

### PR 1: Timeouts + diagnostic logging (PR 2 and PR 3 depend on this)

#### 1a: Increase timeouts + env var overrides

In `codex_plan_review_adapter.py`:
- `_run_with_pty` default: 300 → 600
- `invoke_codex_plan_review` default: 300 → 600
- `invoke_claude_failsafe` default: 120 → 300

In `codex_review_adapter.py`:
- `DEFAULT_TIMEOUT_SECONDS`: 300 → 600

Env var overrides (also serve as **rollback mechanism** if 600s causes issues):
- `CODEX_REVIEW_TIMEOUT` (default 600)
- `CLAUDE_FAILSAFE_TIMEOUT` (default 300)

#### 1b: Persist raw output for all reviews

Add `output_dir: Path | None = None` parameter to `invoke_codex_plan_review()` and `invoke_claude_failsafe()` signatures. When provided, write raw output to `<output_dir>/codex_output_raw.txt` on all outcomes (success, timeout, parse failure).

In `plan_review_driver.py`: pass `output_dir=base_dir` to both adapter functions.

> **Note:** This is a signature change to two public functions. Existing callers pass no `output_dir` and get the old behavior (no file written).

#### 1c: Structured logging in `_run_with_pty`

- Log at start: command, timeout, cwd
- Log every 60s: elapsed time, output bytes so far, process alive
- Log at end: elapsed time, return code, output size, timed_out flag

In `invoke_codex_plan_review` / `invoke_claude_failsafe`:
- Log pre-flight: command, timeout value
- Log post-flight: exit code, output size, findings count, parse patterns matched/failed

#### Files
- `scripts/internal/codex_plan_review_adapter.py` — timeouts, signatures, logging, raw output
- `scripts/internal/codex_review_adapter.py` — timeout constant
- `scripts/internal/plan_review_driver.py` — pass output_dir to adapters

### PR 2: Test coverage for timeout paths (depends on PR 1)

#### 2a: Unit tests for adapter timeout/error branches

`tests/unit/test_codex_plan_review_adapter.py` (extend):
- `_run_with_pty` returns `(None, "partial...")` → assert `success=False`, "Timeout" in error
- `_run_with_pty` returns `(2, "error msg")` → assert `success=False`, exit code in error
- `invoke_claude_failsafe` with `claude` not in PATH → assert error mentions PATH
- `invoke_claude_failsafe` with `subprocess.TimeoutExpired` → assert timeout error

`tests/unit/test_codex_review_adapter.py` (extend):
- Same timeout pattern for PR review adapter

#### 2b: Integration tests for failure scenarios

`tests/integration/test_plan_review_loop.py` (extend):
- Codex returns unparseable output → verify fallback triggers
- Both Codex and Claude fail → verify synthetic CRITICAL finding, correct `stop_reason`

#### 2c: PTY runner tests (real subprocess, no mocks)

`tests/unit/test_pty_runner.py` (new):
- `["sleep", "10"]` with `timeout=1` → `(None, "")`, completes in ~1s
- `["echo", "hello"]` with `timeout=10` → `(0, ...)`, completes quickly
- Script that outputs then hangs → partial output captured, timeout fires

#### Files
- `tests/unit/test_codex_plan_review_adapter.py`
- `tests/unit/test_codex_review_adapter.py`
- `tests/unit/test_pty_runner.py` (new)
- `tests/integration/test_plan_review_loop.py`

### PR 3: Tiered end-to-end infrastructure tests (depends on PR 1)

Standalone test runner (not pytest, not in `make check`) that exercises real
review infrastructure. Follows the experiment runner's SMOKE/QUICK/FULL pattern.

```
uv run python scripts/internal/test_review_infra.py --mode smoke   # ~30s
uv run python scripts/internal/test_review_infra.py --mode quick   # ~5min
uv run python scripts/internal/test_review_infra.py --mode full    # ~15min
```

#### SMOKE (~30s) — no Codex auth needed

| Test | Validates |
|------|-----------|
| S1: PTY basic | `_run_with_pty(["echo","hello"])` returns output |
| S2: PTY timeout | `_run_with_pty(["sleep","30"], timeout=2)` returns `(None,"")` |
| S3: Tier detection | Known content → correct tier |
| S4: State persistence | Save/load round-trip |
| S5: Output parsing | Known Codex output samples → correct findings |
| S6: Codex auth check | `_check_codex_auth()` against `~/.codex/auth.json` |
| S7: Claude CLI detection | `shutil.which("claude")` → not None |

**Pass criteria:** All 7 pass.

#### QUICK (~5min) — needs Codex auth

| Test | Validates |
|------|-----------|
| Q1: Plan review (small) | `run_plan_review_loop()` on fixture → parseable result within 600s |
| Q2: Plan review (medium) | Same on medium fixture → parseable result (findings expected) within 600s |
| Q3: Raw output persisted | `codex_output_raw.txt` exists after Q1/Q2 |
| Q4: Claude failsafe | Force Codex failure via non-zero exit, verify failsafe runs |
| Q5: PR review invocation | `invoke_codex_cli()` in test worktree → parseable output |

> Q4 mechanism: set `CODEX_REVIEW_CMD` to a script that exits non-zero, which
> causes the Codex adapter to return `success=False`, triggering the failsafe cascade.

**Pass criteria:** Q1+Q3 required, Q2/Q4/Q5 advisory.

**Fixtures:** `tests/fixtures/plans/small_fixture.md` (20 lines), `tests/fixtures/plans/medium_fixture.md` (80 lines, deliberate issues).

#### FULL (~15min) — comprehensive reliability

| Test | Validates |
|------|-----------|
| F1: All 3 tiers | Small/medium/governing fixtures all complete |
| F2: Latency profile | min/median/p95/max per tier; assert p95 < timeout |
| F3: Parser accuracy | 5 reviews, all produce valid findings or clean signal (no "unparseable") |
| F4: Timeout recovery | Force `CODEX_REVIEW_TIMEOUT=5`; verify error, state.json, raw output |
| F5: Failsafe chain | Force both failures → synthetic CRITICAL finding |
| F6: PR review loop | Single round in test worktree (advisory) |
| F7: Concurrent reviews | 2 parallel plans, separate state dirs (advisory) |

**Pass criteria:** F1-F5 required, F6-F7 advisory.

**Additional fixture:** `tests/fixtures/plans/governing_fixture.md` (200 lines).

#### Output format: structured JSON with test/status/latency/details per test.

#### Makefile targets: `review-smoke`, `review-quick`, `review-full`

#### Files
- `scripts/internal/test_review_infra.py` (new)
- `tests/fixtures/plans/{small,medium,governing}_fixture.md` (new)
- `Makefile`

---

## Validation

```bash
# PR 1
PYTHONPATH=scripts/internal uv run python -c "
from codex_plan_review_adapter import invoke_codex_plan_review
from pathlib import Path
r = invoke_codex_plan_review(Path('plans/sessions/TEMPLATE.md'), 'small')
print(f'success={r.success}, latency={r.latency_seconds:.0f}s, error={r.error}')
"

# PR 2
uv run python -m pytest tests/unit/test_codex_plan_review_adapter.py -v -k timeout
uv run python -m pytest tests/unit/test_pty_runner.py -v
uv run python -m pytest tests/integration/test_plan_review_loop.py -v -k failsafe
make check-quiet

# PR 3
make review-smoke    # ~30s
make review-quick    # ~5min, needs Codex auth
make review-full     # ~15min, after all PRs merged
```

## Outcome

- PRs: #777 (timeouts+logging), #785 (test coverage), #784 (test harness), #790 (Q5/F6+Q3 fix)
- Plans archive: #770 (13 completed plans archived)
- YAML fix: `~/.codex/skills/review-handoff/SKILL.md` (out-of-band)
- FULL validation: 14/14 PASS, Codex latency 304-351s (was timing out at 300s)
- All PRs merged to main
