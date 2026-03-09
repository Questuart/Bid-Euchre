# Skill ↔ Deterministic Prechecks Integration

## Goal

Refactor `/reviewing-changes` SKILL.md Phases 1-2 to invoke
`deterministic_prechecks.check_diff()` instead of duplicating pattern
detection inline. This ensures both the autonomous review loop and the
manual skill use identical detection logic.

## Changes

### 1. `scripts/internal/deterministic_prechecks.py` — Add missing patterns

Add convention patterns present in SKILL.md Phase 1 but missing from module:
- `print(f"DEBUG"` / `print(">>>"` → debug print in library code
- `type(x) == T` → use `isinstance()` instead

Both are P2 convention findings, same as existing patterns.

### 2. `.claude/skills/reviewing-changes/SKILL.md` — Phase 1 refactor

Replace the manual "Patterns to Flag" table in Phase 1 with:

```
Run deterministic prechecks on the diff:
  uv run python -c "
  import sys; sys.path.insert(0, 'scripts/internal')
  from deterministic_prechecks import check_diff
  import json
  findings = check_diff()
  print(json.dumps([f.to_dict() for f in findings], indent=2))
  "
```

Include the module output as findings in the report. P0/P1 findings
map to BLOCK; P2 findings map to WARN.

### 3. `.claude/skills/reviewing-changes/SKILL.md` — Phase 2 refactor

For BLOCK checks (C1, C2, X3): note that deterministic_prechecks already
covers these. Claude should still read files for N1/N2 (notebook checks)
which require semantic understanding.

WARN checks (C3, C4, N1-N3, T1, X1, X2) remain manual — they require
code comprehension, not pattern matching.

### 4. Tests

Add tests for the new convention patterns in
`tests/unit/test_deterministic_prechecks.py`.

## Files

- `scripts/internal/deterministic_prechecks.py` (modify)
- `.claude/skills/reviewing-changes/SKILL.md` (modify)
- `tests/unit/test_deterministic_prechecks.py` (modify)

## Outcome

(To be filled after implementation)
