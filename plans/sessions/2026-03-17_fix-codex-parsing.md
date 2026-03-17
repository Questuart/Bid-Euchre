# Fix Codex CLI Output Parsing

**Date:** 2026-03-17
**Branch:** `claude/fix-codex-parsing-12cFv`
**Scope:** `scripts/internal/codex_review_adapter.py`, tests

## Problem

Codex CLI (`codex review --base main`) returns natural-language prose reviews
instead of structured `[P1] file:line — message` findings. The parser has two
regex formats but neither matches prose output. The fail-safe at line 385
correctly detects this as "unparseable" (non-empty output, zero findings, no
clean-review signal), returns `success=False`, and after 3 retries the review
loop stops with `STOPPED_REVIEW_FAILURE`.

**Root cause:** The `_PROMPTS` dict (lines 46-71) contains formatting
instructions but these are **never sent to Codex CLI** because `--base` and a
positional prompt are mutually exclusive in `codex-cli v0.114.0+`. The comment
at line 43 acknowledges this: "The CLI relies on repo-level AGENTS.md for
review guidance." But AGENTS.md has no output format instructions for Codex.

This same issue affects the plan review adapter (`codex_plan_review_adapter.py`).

## Analysis

### What Codex CLI actually outputs

Codex CLI produces free-form markdown reviews. Common patterns observed:
- Prose paragraphs describing findings
- Markdown bullet lists with file references
- Numbered lists with issues
- Occasionally structured output matching our patterns (when Codex happens to
  format similarly)

### Current parsing chain

1. `_FINDING_LINE_RE` — `[P1] file:line — message`
2. `_ALT_SEVERITY_RE` — `[CRITICAL][C1] file:line — message`
3. Neither matches → zero findings
4. Fail-safe: non-empty + no clean signal → `success=False`
5. After 3 retries → `STOPPED_REVIEW_FAILURE`

### Why retrying doesn't help

Codex CLI has no formatting instructions (prompt can't be passed), so each
retry produces the same style of natural-language output. Retrying is
deterministically futile for this failure mode.

## Plan

### Step 1: Add natural-language prose parsing to `parse_codex_output()`

Add a third parsing layer that extracts findings from prose/markdown output.
Key patterns to match:

**Pattern A: Markdown bullets with file references**
```
- `src/foo.py:42` — issue description
- **src/bar.py:10**: issue description
```

**Pattern B: File reference anywhere in a line with severity keywords**
```
In src/foo.py line 42, there's an unseeded random call...
src/bar.py:20 has a merge conflict marker
```

**Pattern C: Structured markdown headings + bullets**
```
### Critical Issues
- Unseeded random in `src/foo.py:42`

### Warnings
- Missing test for behavior change in `src/bar.py`
```

Implementation approach:
- Add `_parse_prose_format(line, context_lines)` function
- Use regex to extract `file:line` references from prose lines
- Infer severity from surrounding context (heading keywords, severity words)
- Default to P2 when severity is ambiguous (conservative — won't block merge)
- Only trigger prose parsing when standard + alt parsing find zero results

**Files:** `scripts/internal/codex_review_adapter.py`

### Step 2: Expand clean-review signal patterns

The `_CLEAN_REVIEW_PATTERNS` regex misses several common Codex phrasings:

```python
# Additional patterns to add:
- "all good" / "all looks good"
- "no concerns" / "no issues"
- "changes are clean"
- "nothing to flag"
- "approved" / "ship it"
- Summary-only output with positive sentiment and no file references
```

Also add a heuristic: if the output has no file path references at all
(no `src/`, no `.py`, no `file:line` pattern), it's likely either clean
or too vague to extract findings from — treat as clean with a warning log.

**Files:** `scripts/internal/codex_review_adapter.py`

### Step 3: Add CODEX.md with output format instructions

Codex CLI reads `CODEX.md` from the repo root (similar to how Claude reads
`CLAUDE.md`). Create a minimal `CODEX.md` that instructs Codex to use the
structured output format:

```markdown
# CODEX.md

When reviewing code changes, format each finding as:
[severity] file:line — message (check_id)

Severity levels:
- [P0] — Critical: merge conflicts, security issues
- [P1] — Blocking: correctness bugs, unseeded randomness
- [P2] — Non-blocking: style, conventions, minor improvements

If no issues found, respond with: "No issues found."
```

This is the most impactful fix — it addresses the root cause by providing
format instructions through the channel Codex CLI actually reads.

**Files:** `CODEX.md` (new file, root of repo)

### Step 4: Update tests

Add test fixtures and cases for:
- Prose output with file references → extracted findings
- Prose output with no file references → treated as clean
- Various "clean review" phrasings → matched by expanded patterns
- CODEX.md-guided structured output (same as existing tests, validates no regression)

**Files:** `tests/unit/test_codex_review_adapter.py`

### Step 5: Validation

- Run `uv run python -m pytest tests/unit/test_codex_review_adapter.py`
- Run `make check-quiet`

## Priority Order

1. **Step 3 (CODEX.md)** — Highest impact, addresses root cause
2. **Step 2 (clean signal expansion)** — Quick win, prevents false failures on clean reviews
3. **Step 1 (prose parsing)** — Defense in depth when CODEX.md instructions aren't followed
4. **Step 4 (tests)** — Throughout, alongside each step
5. **Step 5 (validation)** — Final gate

## Risks

- **CODEX.md format**: Need to verify Codex CLI actually reads this file. If
  it uses a different convention (e.g., `.codex/instructions.md`), adjust path.
- **Prose parsing false positives**: A line like "I looked at src/foo.py and it's fine"
  could be falsely extracted as a finding. Mitigation: require both a file reference
  AND a severity indicator (keyword or heading context).
- **Over-broad clean detection**: Could mask real findings. Mitigation: log warnings
  when using heuristic clean detection, save raw output for audit.

## Outcome

_To be filled after implementation._
