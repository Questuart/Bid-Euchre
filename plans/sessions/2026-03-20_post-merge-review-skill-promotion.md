# Post-Merge Review Fixes: Skill Promotion & CI Extras

**Date:** 2026-03-20
**Source:** Post-merge review findings for PRs #1054 and #1050
**Scope:** Security hardening of skill_promotion.py + Makefile consistency fix
**Branch:** `fix/post-merge-skill-promotion-hardening`

## Context

Post-merge review of PR #1054 (skill promotion workflow) and PR #1050
(CI efficiency) identified actionable findings. This plan covers the
immediate-fix items.

## Findings Summary

| # | Source | Severity | Description | Status |
|---|--------|----------|-------------|--------|
| F1 | #1054 | CRITICAL | Path traversal via unvalidated `candidate_id` in `review_skill()`, `promote_skill()`, `get_candidate()` | Fix now |
| F2 | #1054 | MEDIUM | Name not re-validated after loading candidate from disk in `promote_skill()` | Fix now |
| F3 | #1054 | LOW | YAML front matter: `name` field unquoted (description already fixed) | Fix now |
| F4 | #1054 | LOW | HTML comment injection — interpolated values can contain `-->` | Fix now |
| H1 | #1050 | LOW | Makefile `ensure-venv` uses `--all-extras` while CI uses `--extra dev` | Fix now |

## Implementation Plan

### Task 1: Add `candidate_id` validation (F1 — CRITICAL)

**File:** `src/bid_euchre/ops/skill_promotion.py`

Add a `_validate_candidate_id()` helper that validates the input is a
well-formed UUID (via `uuid.UUID(candidate_id)`). Call it at the top of:
- `review_skill()` (line 219, before path construction on line 220)
- `promote_skill()` (line 272, before path construction on line 275)
- `get_candidate()` (line 427, before path construction on line 428)

Implementation:
```python
def _validate_candidate_id(candidate_id: str) -> None:
    """Validate candidate_id is a well-formed UUID to prevent path traversal."""
    try:
        uuid.UUID(candidate_id)
    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid candidate ID '{candidate_id}': must be a valid UUID."
        )
```

### Task 2: Re-validate name after loading from disk (F2 — MEDIUM)

**File:** `src/bid_euchre/ops/skill_promotion.py`

In `promote_skill()`, after loading the candidate (line 279), add:
```python
name_errors = validate_skill_name(candidate.name)
if name_errors:
    raise ValueError(
        f"Candidate '{candidate_id}' has invalid skill name "
        f"'{candidate.name}': {'; '.join(name_errors)}"
    )
```

This defends against tampered candidate JSON files on disk.

### Task 3: Quote YAML `name` field in `_render_skill_md` (F3 — LOW)

**File:** `src/bid_euchre/ops/skill_promotion.py`, line 452

Change:
```python
f"name: {candidate.name}\n"
```
To:
```python
f'name: "{candidate.name}"\n'
```

### Task 4: Sanitize HTML comment values (F4 — LOW)

**File:** `src/bid_euchre/ops/skill_promotion.py`, `_render_skill_md()`

Add a helper to strip `-->` from values interpolated into HTML comments:
```python
def _sanitize_comment(value: str | None) -> str:
    """Strip HTML comment close sequence to prevent injection."""
    if value is None:
        return "None"
    return str(value).replace("-->", "—>")
```

Apply to all HTML comment interpolations (lines 457-463).

### Task 5: Fix Makefile `ensure-venv` extras (H1 — LOW)

**File:** `Makefile`, line 63

Change:
```makefile
@[ -d .venv ] || { echo ">>> Bootstrapping venv (fresh worktree detected)"; uv sync --all-extras; }
```
To:
```makefile
@[ -d .venv ] || { echo ">>> Bootstrapping venv (fresh worktree detected)"; uv sync --extra dev; }
```

This aligns local `make check` with CI's `uv sync --frozen --extra dev`.

### Task 6: Add tests for new validation

**File:** `tests/unit/test_ops_skill_promotion.py`

Add tests:
1. `test_review_rejects_path_traversal_candidate_id` — `review_skill("../../etc")` raises ValueError
2. `test_promote_rejects_path_traversal_candidate_id` — same for `promote_skill`
3. `test_get_candidate_rejects_path_traversal_id` — same for `get_candidate`
4. `test_promote_rejects_tampered_name` — candidate with manually altered name raises ValueError
5. `test_render_sanitizes_html_comments` — HTML comment injection is stripped
6. `test_review_rejects_non_uuid_candidate_id` — non-UUID strings rejected
7. `test_render_yaml_name_quoted` — verify name field is quoted in output

### Task 7: Run validation

- Tier 1: `uv run python -m pytest tests/unit/test_ops_skill_promotion.py -v`
- Tier 2: `make check-quiet`

## Parallelism Assessment

- **Tasks 1-5** are independent code edits in different file regions — can be done sequentially in one pass.
- **Task 6** (tests) depends on Tasks 1-4 being implemented.
- **Task 7** depends on all prior tasks.
- No parallelism needed — single-author sequential execution is fastest.

## Acceptance Criteria

- [ ] All three `candidate_id`-accepting functions validate UUID format
- [ ] `promote_skill()` re-validates `candidate.name` after disk load
- [ ] YAML front matter `name` field is quoted
- [ ] HTML comment values are sanitized
- [ ] Makefile `ensure-venv` uses `--extra dev`
- [ ] New tests pass and existing tests unbroken
- [ ] `make check-quiet` passes

## Outcome

_To be filled after implementation._
