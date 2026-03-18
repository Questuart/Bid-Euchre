# Fix Codex Review Loop Parsing Failures
**Date:** 2026-03-18
**Goal:** Fix the output parsing in `codex_review_adapter.py` so that Codex CLI
review results are correctly classified instead of falling through to "Unparseable"
or being blocked by stale-worktree prechecks. Targets 4 root causes identified
from 0/18 success rate on 2026-03-18.

## Background

The autonomous review loop (`review_driver.py` + `codex_review_adapter.py`) failed
on 100% of recent PRs. Evidence from `.claude/runtime/review_loops/pr_*/`:

| Root Cause | PRs Affected | Current Result | Fix Scope |
|-----------|-------------|----------------|-----------|
| RC1: Empty diff (stale worktree) | ~6 | `Unparseable` | IN SCOPE (detect + skip) |
| RC2: Output format mismatch | PR 808, 818, 819 | `Unparseable` | IN SCOPE (parser fix) |
| RC3: PV2 precheck false positive | PR 812-817 | `stopped_ci_failure` | IN SCOPE (severity demotion) |
| RC4: Hook not triggered | PR 822 | No sentinel | OUT OF SCOPE |

### RC1 Evidence (verified from saved artifacts)
PRs #800, #809, #820 raw Codex output (from `.claude/runtime/review_loops/`
across worktrees `author-b` and `author-c`):
```
`git diff 13ba62ee...` is empty in this worktree, so there are no tracked code
changes to review relative to the provided merge base.
```
```
`git diff 3e77dcb7...` is empty in this worktree, so there are no committed
changes to review relative to `main`. I only see untracked plan-session files,
which are outside the requested diff.
```
Key phrases for pattern matching: "is empty in this worktree",
"no tracked code changes", "no committed changes to review",
"no code changes relative to `main`".

### RC2 Evidence (PR 818 raw output)
```
- [P1] Use valid tmux pane indices for the dashboard layout — /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/.claude/tmux/steward-session.sh:90-95
  On a stock tmux setup, pane indices start at `0`...

- [P2] Resolve the primary checkout before building steward worktree paths — /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/.claude/tmux/steward-session.sh:36-42
  If this launcher is started from an existing linked worktree...

- [P2] Guard the `caffeinate` wrapper on hosts that do not provide it — /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/.claude/tmux/steward-session.sh:67-67
  On Linux or any machine without the macOS-only `caffeinate` utility...
```
Three mismatches vs `_FINDING_LINE_RE`:
1. **Field order reversed:** message before file (not file before message)
2. **Absolute paths:** `/Users/...` instead of `src/...` or `scripts/...`
3. **Line ranges:** `90-95` instead of single `90`

### RC3 Evidence (PRs 812-817)
All blocked by `PV2: Plan file does not exist: plans/sessions/2026-03-17_infra-incident-enforcement.md`.
The plan exists on the PR branch but not in the stale worktree cwd. PV2 is `P1`
(blocking), so the loop halts before ever reaching Codex.

## Plan

### Step 0: Capture test fixtures from real artifacts (test-first)
**Impact:** Grounds all subsequent steps in verified reality

Before writing any regex changes, capture raw Codex outputs as test fixtures:
1. Copy PR #818 `raw_output` (RC2 reversed format, 3 findings)
2. Copy PR #800 `raw_output` (RC1 empty diff)
3. Copy PR #820 `raw_output` (RC1 empty diff, alternate phrasing)

These become string constants in the test file. All new regex patterns must
parse these fixtures correctly — test-first, not assumption-first.

### Step 1: Add empty-diff detection to `_CLEAN_REVIEW_PATTERNS`
**Impact:** Fixes RC1 (highest impact — 6+ PRs)

Add patterns to `_CLEAN_REVIEW_PATTERNS` (line 152) that recognize empty-diff
responses. Patterns derived from **actual saved Codex output** (Step 0 fixtures):
- `"is empty in this worktree"` — exact phrase from PR #800, #809
- `"no tracked code changes"` — exact phrase from PR #800
- `"no committed changes to review"` — exact phrase from PR #820
- `"no code changes relative to"` — exact phrase from PR #809
- `"nothing to review"` / `"no changes to review"` — defensive variants

When matched, `invoke_codex_cli()` returns `success=True` with zero findings
instead of `success=False` with "Unparseable" error. This is semantically correct:
an empty diff means there is genuinely nothing wrong.

**Files:** `scripts/internal/codex_review_adapter.py` (lines 152-180)

### Step 2: Add reversed-format regex for `[P1] message — file:line-range`
**Impact:** Fixes RC2 field order mismatch

Add a new `_REVERSED_FINDING_RE` regex and `_parse_reversed_format()` function.

Regex pattern (derived from PR #818 actual output):
```
^[-•*]\s*\[(?P<severity>P[012])\]\s+(?P<message>.+?)\s*[—–-]+\s*(?P<file>/[^\s:]+|(?:src|tests|scripts|experiments|notebooks|\.claude)/[^\s:]+)(?::(?P<line>\d+)(?:-\d+)?)?
```

Key design decisions:
- Match optional leading bullet `- ` followed by `[P0|P1|P2]`
- Message comes before the dash separator, file path after
- Absolute paths: accept `/...` paths, strip repo root prefix using `os.getcwd()`
- Relative paths: accept known prefixes (`src/`, `scripts/`, `.claude/`, etc.)
- Line ranges: `\d+(?:-\d+)?` — extract start line only

**Parse ordering (F2):** Add as a new `_parse_reversed_format()` called in
`parse_codex_output()` **between** Pass 1 (structured) and Pass 2 (prose).
This prevents ambiguity with the standard format regex since the reversed
format has a distinct structure (message-first, file-last with absolute path).

```python
# Pass 1: structured formats (standard, alt, table)
# Pass 1.5: reversed format (message — file:line)  ← NEW
# Pass 2: prose fallback (only if Passes 1+1.5 found nothing)
```

**Files:** `scripts/internal/codex_review_adapter.py`

### Step 3: Expand `_PROSE_FILE_REF_RE` for non-.py extensions
**Impact:** Fixes RC2 prose fallback gap

Current regex (line 120-123):
```python
r"(?P<file>(?:src|tests|scripts|experiments|notebooks)/[^\s:,`\"']+\.py)"
```

Fix: Expand the extension list to include common non-Python files:
```python
r"\.(?:py|sh|yaml|yml|json|toml|md|cfg|txt)"
```

**Absolute path handling (F4):** Do NOT add arbitrary absolute paths to the
prose regex — this risks matching system paths in diagnostic context. Instead,
constrain to paths containing a known repo-relative segment:
```python
# Relative paths (existing, expanded extensions)
r"(?:src|tests|scripts|experiments|notebooks|\.claude)/[^\s:,`\"']+\.(?:py|sh|yaml|yml|json|toml|md|cfg|txt)"
```

The reversed-format regex (Step 2) already handles absolute paths with the
explicit `[P1] message — /abs/path` structure, where false-positive risk is
low because the `[P1]` prefix gates the match. The prose fallback should
stay conservative.

**Files:** `scripts/internal/codex_review_adapter.py` (lines 120-123)

### Step 4: Handle line ranges in all 4 regexes
**Impact:** Completes RC2 fix

**Exhaustive checklist (F3):**
- [ ] `_FINDING_LINE_RE` (line 82): `(?::(?P<line>\d+))?` → `(?::(?P<line>\d+)(?:-\d+)?)?`
- [ ] `_ALT_SEVERITY_RE` (line 96): same change
- [ ] `_TABLE_ROW_RE` (line 113): `(?P<line>\d*)` → `(?P<line>\d*)(?:-\d+)?`
- [ ] `_PROSE_FILE_REF_RE` (line 122): both `(?P<line>\d+)` and `(?P<line2>\d+)` → add `(?:-\d+)?`
- [ ] `_REVERSED_FINDING_RE` (new, Step 2): already includes range handling

**Files:** `scripts/internal/codex_review_adapter.py`

### Step 5: Demote PV2 from P1 to P2 (non-blocking)
**Impact:** Fixes RC3 (5 PRs)

The plan validation precheck `PV2` ("Plan file does not exist") fires because the
driver runs in the stale worktree where the PR branch files are not checked out.
Until the driver is fixed to checkout the PR branch (out of scope), PV2 should be
demoted to `P2` (non-blocking, warning) so it does not halt the loop.

**Tradeoff (F5):** This means a real missing plan file (author forgot to commit it)
also becomes non-blocking. This is acceptable because:
- PV1 (plan reference in PR body) already catches "no plan mentioned"
- PV3 (plan content check) catches empty/boilerplate plans
- The gap is only "plan referenced but file not committed" — uncommon, low-severity
- The proper fix (driver checks out PR branch) is tracked in follow-up item #1

Alternative considered: Skip PV2 entirely when the worktree branch differs from the
PR branch. This is more correct but requires the driver to detect worktree state,
which is closer to the architectural fix. Demotion is simpler and sufficient.

**Files:** `scripts/internal/review_driver.py` (find PV2 severity assignment,
change `"P1"` to `"P2"`)

### Step 6: Add comprehensive tests (test-first from fixtures)
**Impact:** Locks behavior for all new patterns

Write tests BEFORE implementation (Step 0 fixtures are the source of truth).
New test fixtures and cases in `tests/unit/test_codex_review_adapter.py`:

1. **Empty-diff detection tests:**
   - `test_empty_diff_detected_as_clean` — PR #800 exact raw output
   - `test_empty_diff_alternate_phrasing_clean` — PR #820 exact raw output
   - `test_no_changes_to_review_clean` — "no changes to review" variant

2. **Reversed format tests:**
   - `test_parse_reversed_format_pr818_full_replay` — full PR #818 raw output,
     assert 3 findings with correct severities (P1, P2, P2), files, and lines
   - `test_parse_reversed_format_absolute_path_stripped` — absolute path → relative
   - `test_parse_reversed_format_line_range_extracts_start` — `90-95` → `90`
   - `test_parse_reversed_format_with_bullet` — leading `- ` prefix
   - `test_parse_reversed_format_relative_path` — relative path variant

3. **Expanded prose tests:**
   - `test_prose_matches_sh_file` — `.sh` extension
   - `test_prose_matches_yaml_file` — `.yaml` extension
   - `test_prose_no_match_system_path` — `/usr/bin/bash` should NOT match

4. **Line range tests (all 4 regexes):**
   - `test_standard_format_line_range` — `src/foo.py:10-20` extracts `10`
   - `test_alt_format_line_range` — `[CRITICAL] file:10-20 — msg`
   - `test_table_format_line_range` — table with range column
   - `test_prose_format_line_range` — prose with `:10-20`

5. **Parse ordering tests:**
   - `test_reversed_format_tried_before_prose` — a line matching both reversed
     and prose formats should be parsed as reversed (higher fidelity)
   - `test_standard_format_preferred_over_reversed` — standard `[P1] file:line — msg`
     should still be parsed by the original regex, not the reversed one

**Files:** `tests/unit/test_codex_review_adapter.py`

### Step 7: Run `make check-quiet` (Tier 2 validation)
Full validation before PR.

## Files
- `scripts/internal/codex_review_adapter.py` — parser fixes (Steps 1-4)
- `scripts/internal/review_driver.py` — PV2 demotion (Step 5)
- `tests/unit/test_codex_review_adapter.py` — new tests (Step 6)

## Out of Scope / Follow-up

These are logged for future work but explicitly excluded from this PR:

1. **Worktree-mismatch architectural fix (RC1/RC3 root cause):** The driver should
   checkout the PR branch or create an ephemeral worktree before running Codex.
   This would fix both empty-diff (RC1) and stale-precheck (RC3) at the root cause
   level. Requires significant refactoring of `review_driver.py`. **Create a GitHub
   issue after this PR merges.**

2. **Plan review adapter (`codex_plan_review_adapter.py`) parity:** The plan review
   adapter has similar parsing code that may need the same fixes. Separate PR.

3. **Hook registration (RC4):** PR #822 had no sentinel file. Likely a session
   without hooks configured. Separate investigation. Independent of this fix —
   verified in diagnosis that RC4 does not affect ability to validate Steps 1-5
   in production (hooks fire correctly in author-a/b/c/scratch worktrees; #822
   was created from an external session).

4. **Absolute path stripping heuristic robustness:** The reversed-format parser
   strips absolute paths using `os.getcwd()` as repo root. This could break if
   Codex reports paths outside the repo directory. Acceptable for now since Codex
   runs in the repo directory. A more robust fix would pass the repo root explicitly.

## Validation

### Unit tests (Tier 1)
```bash
uv run python -m pytest tests/unit/test_codex_review_adapter.py -v
```

### Replay test (automated, included in Step 6)
The PR #818 full replay test (`test_parse_reversed_format_pr818_full_replay`)
uses the exact raw Codex output as a string constant, not a file read. This
ensures the test is self-contained and doesn't depend on local runtime artifacts.

### Full suite (Tier 2)
```bash
make check-quiet
```

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
