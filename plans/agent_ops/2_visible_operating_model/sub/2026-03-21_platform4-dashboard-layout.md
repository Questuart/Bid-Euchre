# SP-2-01: Platform-4 Dashboard-First Steward Layout

**Parent:** Phase 2, Step 0-1 (Platform-4 scope lock + implementation)
**Status:** completed
**Owner:** author-b
**Created:** 2026-03-21

---

## Goal

Create a dashboard-first supervision surface that answers "who owns what and
what needs attention" without requiring author panes to stay foregrounded.

## Done When (from governing plan)

1. The default visible steward layout no longer requires author panes to stay
   foregrounded for ordinary supervision.
2. Hidden-by-default author lanes remain easy to inspect or resume by name.
3. The dashboard surface can answer who owns what and what needs attention.

## Scope Lock

### In scope

- New `src/bid_euchre/ops/dashboard.py` module with:
  - `DashboardView` dataclass (structured dashboard state)
  - `build_dashboard_view()` function that synthesizes from existing data sources
  - `format_dashboard_text()` for human-readable output
  - `format_dashboard_json()` for machine-readable output
- New `dashboard` subcommand in `scripts/internal/ops.py`
- Visibility management: `set_lane_visibility()` and default visibility policy
  (foreground for dashboard/orchestrator/ops/review, background for author-*)
- New `tests/unit/test_ops_dashboard.py`
- Update `src/bid_euchre/ops/__init__.py` module docstring

### Out of scope

- Textual TUI (later, per governing plan optional tooling)
- Platform-5 canonical prompts/skills
- Platform-6 supervisor routines / delta summaries
- Platform-7 worker-pool scaling
- Remote channels (Platform-8/9)
- Any changes to existing `aggregate_status()` / `format_status_text()` APIs

## Design

### Data Sources (all existing, read-only)

| Source | Module | What it provides |
|--------|--------|-----------------|
| Lane registry + status | `ops.status.aggregate_status()` | `StatusReport` with `LaneStatus` objects |
| Task queue | `ops.task_queue.queue_summary()` | Pending/dispatched task packet counts |
| Message bus | `ops.message_bus.inbox_stats(bus_root)` | Per-lane `{"lane_id", "total", "by_status": {"pending": N, "acked": N, ...}}`. Derive `unacked_count = total - by_status.get("acked", 0) - by_status.get("resolved", 0)`. |
| Events | `ops.status._load_recent_events()` | Recent event stream |

### DashboardView Contract

```python
@dataclass
class DashboardSection:
    """One section of the dashboard (foreground or background lanes)."""
    title: str
    lanes: list[LaneStatus]

@dataclass
class AttentionItem:
    """A single item requiring operator attention."""
    lane_id: str
    severity: str  # "high", "medium", "low"
    reason: str
    suggested_action: str | None = None

@dataclass
class InboxHighlight:
    """Summary of unread/unacked messages for a lane."""
    lane_id: str
    unacked_count: int
    oldest_unacked_age: str | None = None  # relative time

@dataclass
class DashboardView:
    """Complete dashboard state for rendering."""
    generated_at: str
    foreground: DashboardSection
    background: DashboardSection
    attention_items: list[AttentionItem]
    inbox_highlights: list[InboxHighlight]
    task_queue_summary: dict[str, Any]
    active_task_count: int
    blocked_task_count: int
    warning_count: int
```

### Visibility Policy

Default visibility assignment (applied when no explicit visibility is set):

| Lane pattern | Default visibility |
|-------------|-------------------|
| `dashboard` | `foreground` |
| `orchestrator` | `foreground` |
| `ops` | `foreground` |
| `review` | `foreground` |
| `issues` | `foreground` |
| `author-*` | `background` |
| `(other)` | `background` |

`set_lane_visibility(lane_id, visibility, runtime_dir)` writes the visibility
field to the worktree registry entry. The dashboard reads `lane.visibility`
(already present in `LaneStatus` from Platform-1) and falls back to the
default policy when the field is None.

### CLI Surface

```
uv run python scripts/internal/ops.py dashboard          # text output
uv run python scripts/internal/ops.py dashboard --json   # JSON output
uv run python scripts/internal/ops.py dashboard --set-visibility <lane> <fg|bg|hidden>
```

### Text Output Format

```
=== Steward Dashboard ===

Foreground Lanes (4)
  orchestrator   [active]   Platform-4 implementation  PR #1230  @ops/platform4  5m ago
  ops            [idle]     —                                    @main            2h ago
  review         [active]   reviewing PR #1230                   @main            now
  issues         [idle]     —                                    @main            1d ago

Background Lanes (4 total, 1 active, 0 attention)
  author-a       [active]   Browser game Phase 0  PR #1200  @feat/browser  10m ago
  author-b       [idle]     —                               @main          3h ago
  author-c       [idle]     —                               @main          1d ago
  author-d       [idle]     —                               @main          2d+

Attention (2)
  [high] author-a: stale: no progress for 45min -> check if agent died
  [medium] review: blocked: CI failing -> inspect CI output

Inbox (1 unacked)
  orchestrator: 1 unacked message (oldest: 15m ago)

Tasks: 3 active, 1 blocked, 12 completed
Task Queue: 2 packets (1 dispatched, 1 pending)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bid_euchre/ops/dashboard.py` | CREATE | Dashboard view builder and formatters |
| `src/bid_euchre/ops/__init__.py` | EDIT | Add dashboard to module docstring |
| `scripts/internal/ops.py` | EDIT | Add `dashboard` subcommand + parser |
| `tests/unit/test_ops_dashboard.py` | CREATE | Unit tests for dashboard module |

## Validation Plan

### Tier 1 (during implementation)
```bash
uv run python -m pytest tests/unit/test_ops_dashboard.py -v
uv run python -m pytest tests/unit/test_ops_status.py -v
```

### Tier 2 (before PR)
```bash
make check-quiet
```

### Smoke check
```bash
uv run python scripts/internal/ops.py dashboard
uv run python scripts/internal/ops.py dashboard --json
```

## Rollback Path

Delete `src/bid_euchre/ops/dashboard.py` and revert the ops.py CLI addition.
The dashboard is purely additive — no existing APIs are modified.

## Known Gaps

- Dashboard does not auto-refresh (future: Platform-6 delta summaries)
- No Textual TUI (governed plan marks this as optional/later)
- Inbox highlights require message_bus to have been used (graceful degradation
  to empty list when no inbox exists)

## Outcome

_(to be filled after implementation)_
