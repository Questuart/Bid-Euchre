# SP-4-01: Export & Replay Validation

**ID:** SP-4-01
**Parent:** Phase 4 — Data Pipeline
**Status:** completed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-14

---

## Goal

Build JSONL export tooling for hosted-play decisions and validate that
exported data supports deterministic hand replay. This enables future
training pipeline ingestion of human decision data.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `scripts/internal/export_hosted_decisions.py` | ~120 | CLI export: DB → JSONL |
| `web/export.py` | ~80 | Export logic (shared by CLI and potential API) |
| `tests/unit/hosted_play/test_export.py` | ~150 | Export format + replay tests |

Total: 3 files, ~350 lines.

## JSONL Export Format

Each decision exports as one JSON line:

```json
{
    "schema_version": 1,
    "event": "hosted_decision",
    "match_uuid": "a1b2c3d4-...",
    "match_seed": 42,
    "hand_number": 3,
    "deal_id": 7,
    "turn_number": 12,
    "seat": 0,
    "phase": "bid",
    "decision_source": "human",
    "ai_model": "heuristic",
    "dealer_seat": 2,
    "hand": [["S","A"], ["S","K"], ["H","J"], ["H","T"], ["D","Q"],
             ["D","T"], ["C","A"], ["C","K"], ["C","Q"], ["C","T"]],
    "auction_transcript": [
        {"seat": 3, "action": "pass", "n": 0},
        {"seat": 0, "action": "pending"}
    ],
    "current_high_bid": 0,
    "contract_type": null,
    "trump": null,
    "trick_plays": [],
    "completed_tricks": [],
    "legal_actions": [
        {"n": 0},
        {"n": 1, "contract": "S"},
        {"n": 1, "contract": "H"},
        {"n": 1, "contract": "D"},
        {"n": 1, "contract": "C"},
        {"n": 1, "contract": "HIGH"},
        {"n": 1, "contract": "LOW"}
    ],
    "chosen_action": {"n": 5, "contract": "S"},
    "decision_time_ms": 4200,
    "timestamp": "2026-03-15T20:30:00Z"
}
```

For card-play decisions, includes `trick_plays` (current trick so far)
and `completed_tricks` (earlier tricks in this hand).

## Export CLI (`export_hosted_decisions.py`)

```bash
# Export all decisions from a database
uv run python scripts/internal/export_hosted_decisions.py \
    --db data/hosted/bideuchre.db \
    --output data/hosted/export/decisions.jsonl

# Export specific match
uv run python scripts/internal/export_hosted_decisions.py \
    --db data/hosted/bideuchre.db \
    --match-uuid a1b2c3d4-... \
    --output data/hosted/export/match_a1b2c3d4.jsonl

# Export only human decisions (for training)
uv run python scripts/internal/export_hosted_decisions.py \
    --db data/hosted/bideuchre.db \
    --human-only \
    --output data/hosted/export/human_decisions.jsonl
```

## Replay Validation

A replay test verifies that exported data is sufficient to reproduce the hand:

1. Read a JSONL decision record
2. From the `hand`, `dealer_seat`, and `match_seed`/`deal_id`, regenerate the deal
3. Verify the regenerated hands match the logged hands
4. Replay all decisions in order
5. Verify legality of each action using `get_legal_indices()` / bid legality
6. Verify trick winners match using `trick_winner()`
7. Verify final scoring matches using `compute_points()`

This proves the logged data is complete and consistent with the core rules.

## Export Logic (`web/export.py`)

```python
def export_decisions(
    db_session,
    output_path: Path,
    match_uuid: Optional[str] = None,
    human_only: bool = False,
) -> int:
    """Export decisions from DB to JSONL. Returns count of records exported."""

def decision_to_jsonl(decision_row, match_row, hand_row) -> dict:
    """Convert a DB decision row + context to JSONL-exportable dict."""

def validate_replay(jsonl_path: Path) -> list[str]:
    """Replay all decisions in a JSONL file, return list of errors (empty = valid)."""
```

## Required Tests (`test_export.py`)

1. **Round-trip** — create match in DB → export to JSONL → parse → verify all fields present
2. **Replay correctness** — export a completed hand → replay → verify legality + outcomes
3. **Human-only filter** — export with `human_only=True` → verify no AI decision rows
4. **Match filter** — export specific match UUID → verify no other match data
5. **Schema compliance** — verify exported JSONL matches the documented schema
6. **Empty DB** — export from empty DB → produces empty file, no errors

## Validation Command

```bash
uv run python -m pytest tests/unit/hosted_play/test_export.py -v
```

## Future Integration Points (Not V1)

These are noted for context but explicitly deferred:

- **Shadow decisions:** Log what other AI models would have chosen. Requires
  `AIManager.get_shadow_decisions()` — add post-MVP.
- **Dual-write primary persistence:** Deferred. V1 keeps the database as the
  source of truth and produces JSONL only through export tooling.
- **Training pipeline adapter:** Map exported JSONL to the format expected by
  `datasets/eval_dataset.py`. May require a thin adapter script.
- **Leaderboard stats:** Compute aggregate stats from decision data. Add
  as a post-MVP phase.

## Outcome

**Completed 2026-03-24.** All deliverables shipped across 5 PRs:

| PR | Deliverable |
|----|-------------|
| #1529 | `decision_to_jsonl` export function + schema tests |
| #1533 | Fixture factory helpers for hosted_play export tests |
| #1535 | `export_decisions` batch export with filter support |
| #1538 | `export_hosted_decisions` CLI script |
| #1545 | `validate_replay` JSONL correctness verifier |

Validation: all hosted_play tests pass (`tests/unit/hosted_play/`).
