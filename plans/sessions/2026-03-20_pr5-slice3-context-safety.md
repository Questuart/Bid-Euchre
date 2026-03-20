# PR-5 Slice 3: Context-Safety Scanning

**Date:** 2026-03-20
**Parent:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` → PR-5 closeout slice 3
**Branch:** `codex/steward-author-c`
**Lane:** author-c

## Goal

Add a context-safety scanner that gates memory/summary/skill promotion paths.
Content is classified as **allow / warn / reject** before it enters high-autonomy
auto-load or promotion flows.

## Design

### New module: `src/bid_euchre/ops/context_safety.py`

A focused scanner with these responsibilities:

1. **Policy definition** — a set of named rules, each with:
   - `rule_id` (str)
   - `description` (str)
   - `check` function `(content: str, metadata: dict) -> RuleResult`
   - `severity` — `reject` or `warn`

2. **Built-in rules (v1):**
   | Rule ID | Severity | Detects |
   |---------|----------|---------|
   | `secret_pattern` | reject | API keys, tokens, passwords in content |
   | `shell_injection` | reject | Shell-like commands / backtick execution patterns |
   | `path_traversal` | reject | `../` path traversal, absolute paths outside repo |
   | `missing_provenance` | reject | Content without source_file or added_by |
   | `oversized_content` | warn | Content exceeding size threshold (default 10KB) |
   | `binary_content` | reject | Non-UTF-8 / binary data |

3. **Result contract:**
   ```python
   @dataclass
   class ScanResult:
       outcome: Literal["allow", "warn", "reject"]
       findings: list[ScanFinding]
       content_hash: str  # SHA-256 for audit trail

   @dataclass
   class ScanFinding:
       rule_id: str
       severity: Literal["warn", "reject"]
       message: str
       location: str | None  # line number or byte offset
   ```

4. **Integration points:**
   - `scan_content(content, metadata) -> ScanResult` — main entry point
   - `scan_memory_entry(entry: MemoryEntry) -> ScanResult` — typed wrapper for memory entries
   - `format_scan_text(result) -> str` — human-readable output
   - `format_scan_json(result) -> dict` — machine-readable output

### Wire into `add_entry()` in `memory.py`

Add a `safety_scan` parameter (default `True`) to `add_entry()`. When enabled:
- Scan entry value before persisting
- Reject → raise `ValueError` with findings
- Warn → log warnings, persist with `_safety_warnings` tag
- Allow → persist normally

### CLI surface in `build_curated_memory.py`

Add a `scan` subcommand:
```
uv run python scripts/internal/build_curated_memory.py scan --text "content..."
uv run python scripts/internal/build_curated_memory.py scan --file path/to/content
```

Dry-run mode shows what would be allowed/warned/rejected without persisting.

### Tests: `tests/unit/test_ops_context_safety.py`

| Test | Covers |
|------|--------|
| `test_safe_content_allowed` | Clean content → allow |
| `test_secret_detected` | API key pattern → reject |
| `test_shell_injection_detected` | Backtick command → reject |
| `test_path_traversal_detected` | `../../../etc/passwd` → reject |
| `test_missing_provenance_rejected` | Empty source_file → reject |
| `test_oversized_content_warned` | 15KB content → warn (not reject) |
| `test_binary_content_rejected` | Null bytes → reject |
| `test_multiple_findings` | Content with 2+ issues → reports all |
| `test_scan_result_deterministic` | Same input → same hash + findings |
| `test_add_entry_with_scan_rejects` | add_entry refuses unsafe content |
| `test_add_entry_scan_disabled` | add_entry with safety_scan=False bypasses |
| `test_warn_content_persists_with_tag` | Warned content gets `_safety_warnings` tag |

### Docs update: `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

Add a "Context Safety" section documenting:
- What is scanned and when
- The allow/warn/reject contract
- How to disable scanning (e.g., `--no-scan` flag)
- How to inspect scan results

## Files Changed

| File | Action |
|------|--------|
| `src/bid_euchre/ops/context_safety.py` | **New** — scanner module |
| `src/bid_euchre/ops/__init__.py` | Update docstring |
| `src/bid_euchre/ops/memory.py` | Wire `safety_scan` into `add_entry()` |
| `tests/unit/test_ops_context_safety.py` | **New** — scanner tests |
| `tests/unit/test_ops_memory.py` | Add tests for scan integration |
| `scripts/internal/build_curated_memory.py` | Add `scan` subcommand |
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Add Context Safety section |

## Acceptance Criteria

- [x] Context-safety scanner exists at `src/bid_euchre/ops/context_safety.py`
- [x] Clear allow/warn/reject outcome contract
- [x] `add_entry()` uses scanner by default
- [x] CLI dry-run path for operator inspection
- [x] Docs explain the safety boundary
- [x] Tests cover happy path and all unhappy paths
- [x] `make check-quiet` passes

## Outcome

PR #1024 — `ops: add context-safety scanning for promoted operator content`

Delivered all acceptance criteria. Post-review fixes tightened shell injection
regexes to reduce false positives (H1/H2/M4), added `TYPE_CHECKING` import
for `MemoryEntry` (M2), and made CLI dry-run skip provenance when `--source`/`--by`
are omitted (M1).
