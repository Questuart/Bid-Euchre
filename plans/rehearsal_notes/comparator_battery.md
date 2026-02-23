# Dress Rehearsal: Comparator Battery Infrastructure

**Date:** 2026-02-23
**PR:** feat/comparator-battery

## What Was Clear

- The `_CLASS_TO_NAME` mapping approach (explicit dict) is simpler and more
  reliable than CamelCase-to-snake conversion, especially for acronym-heavy
  names like "OLSa".
- JSON output contract works cleanly: stdout is pure JSON when
  `--output-format json`, diagnostics go to stderr.
- Ancestor-walking pattern for path resolution (from PR #407) transfers
  cleanly to the dashboard's `_resolve_me_delta()`.
- Bundle validator extension is minimal and backward-compatible: both
  comparator keys are optional, null-tolerant.

## What Was Ambiguous / Invented

- **Plan flag name mismatch:** The execution plan (line ~403) uses `--format json`
  but implementation uses `--output-format json` to avoid shadowing Python's
  `format` builtin. The plan doc needs a one-word patch.
- **ME delta sign convention:** Plan says `hybrid_olsa.net_eppd - modeloespecifico.net_eppd`.
  In R0, this is negative (-0.81) since ME outperforms hybrid R0. The dashboard
  shows em-dash for R0 (battery-only), so this is moot until R1.
- **Existing test import pattern:** `test_auction_comparator.py` used
  `sys.path.insert` which is an anti-pattern per project rules. Fixed to use
  importlib.util pattern consistent with other script tests.

## R0 Battery Results (seed=42, n_per=10,000)

| Bidder | net_eppd |
|--------|----------|
| modeloespecifico | 2.2912 |
| hybrid_olsa | 1.4811 |
| rankthetank | -3.1703 |
| fiveheadfred | -3.5211 |
| stricthellraiser | -6.1144 |

## Pre-Existing Issues Found

1. **R0 bundle timestamp** has fractional seconds (`02:02:32.021368Z`) which
   the validator's regex rejects. Not a regression from this PR.
2. **R0 bundle incumbent** is `null` (no predecessor), causing `validate_bundle_files_exist()`
   to fail with AttributeError. Also pre-existing.

## Errors During Rehearsal

None from the new code. All 1,577 tests pass, `make check` green.

## Plan Patch Needed

Change `--format json` to `--output-format json` in the execution plan's
R0 battery command (single-word change, cosmetic).
