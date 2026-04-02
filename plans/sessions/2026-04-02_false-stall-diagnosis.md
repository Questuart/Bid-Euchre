# False-Stall Diagnosis: Orchestrator Misdiagnosis During `make check` Runs

> **Task:** `54b70580741a` — Analyze orchestrator false-stall diagnosis during
> make check background runs
>
> **Date:** 2026-04-02
> **Author:** analyst-a

## Problem Statement

The orchestrator repeatedly misdiagnoses author lanes as "stalled" or "failed
to commit" when they are actually waiting for `make check` to complete. This
causes:

1. **Premature redispatches** (same task dispatched 3+ times to different lanes)
2. **Wasted lane context** (clearing lanes that were mid-validation)
3. **Incorrect status reports** ("lane stalled" when it's healthy)

## Root Cause Analysis

The false-stall problem stems from **two independent detection paths** that
both fail to distinguish "waiting for make check" from "truly idle":

### Path A: Automated Stall Detection (`check_stalled_lanes`)

**Location:** `src/bid_euchre/ops/monitor.py:838-1100`

The automated monitor uses a 3-signal composite:

| Signal | Source | Limitation |
|--------|--------|-----------|
| Dispatch age | Task queue timestamps | Correct — no issue here |
| Activity epoch | `tmux display-message #{pane_activity}` | **Partial** — see below |
| Active-work guard | `_detect_active_work()` on pane capture | **Insufficient** — see below |

**Finding 1: `_capture_pane_content` captures too little.**
At `monitor.py:1190`, the stall detection capture uses:
```python
["tmux", "capture-pane", "-t", target, "-p"]
```
This captures only the **visible terminal area** (~20-30 lines). No `-S` flag.
Meanwhile, the `capture-pane` skill (used by the orchestrator manually) recommends
`-S -50` for 50 lines of scrollback. When Claude Code's TUI is running a Bash
tool, the spinner/progress indicator can be rendered **above** the visible pane
bottom — especially if the command output pushed content up.

**Finding 2: `_detect_active_work` checks only the last 5 non-empty lines.**
At `monitor.py:1124`, `_ACTIVITY_TAIL_LINES = 5`. The function scans only the
last 5 non-empty lines for spinner glyphs (`✶✻✽✢⏺✳`), duration patterns, and
tool-execution patterns. But the Claude Code TUI's status area includes:
- The status bar (model name, token count, elapsed time)
- The empty `❯` prompt
- Potentially blank lines between sections

These "infrastructure" lines can consume most or all of the 5-line window,
pushing the actual `⏺ Bash(make check-gated)` line out of detection range.

**Finding 3: Activity epoch may plateau during `make check-quiet`.**
`make check-quiet` redirects all child output to a tmpfile:
```makefile
if $(MAKE) check > "$$CHECK_LOG" 2>&1; then
```
During the 30-120 seconds this runs, the only terminal output is the initial
`>>> Running full check (logs → ...)` message. The Claude Code TUI spinner
animates, but if the spinner frame rate doesn't change the `#{pane_activity}`
epoch between two monitor cycles (which run at ~60-120s intervals), the epoch
appears unchanged → stall counter increments.

**Finding 4: `check-gated` semaphore wait adds a second idle window.**
`make check-gated` polls for semaphore slots with `sleep $((RANDOM % 10 + 5))`.
During this wait, the lane produces periodic "Waiting for slot" messages, but
the Bash tool is still blocking. If the monitor captures between sleep cycles,
the pane shows minimal activity.

### Path B: Manual Orchestrator Assessment (Skills-Based)

The orchestrator's manual lane assessment via `/check-in` → `/lane-status` uses:

**Cross-reference matrix** (`lane-status/SKILL.md:77-86`):
| Pane | Worktree | PR | True State |
|------|----------|-----|------------|
| Idle | Dirty (>0/0) | None | **STALLED** |

This is the critical misdiagnosis. The matrix correctly identifies the
ambiguity ("either mid-work or stalled post-validation") but when the
orchestrator sees the pane as "idle" (based on the `❯` prompt at the bottom),
it resolves the ambiguity toward **STALLED** — even though the lane may be
mid-`make check`.

The lane-status skill's anti-pattern list even warns:
> ❌ Nudging a lane that's mid-`make check-quiet` (interrupts validation)

But there's no positive detection guidance for "how to tell make check is
running."

## Why the Active-Work Guard (#1612) Is Insufficient

The active-work guard was added to prevent false stalls when a lane is
"actively thinking" (LLM inference, long read). It works well for those cases
because Claude Code shows spinner glyphs during inference. But `make check` has
a different failure mode:

| Phase | Claude Code TUI | Active-work guard detects? |
|-------|-----------------|---------------------------|
| LLM inference | `✶ Determining…` | **Yes** — spinner glyph |
| Bash tool running | `⏺ Bash(make check-gated)…` | **Maybe** — only if `⏺` is in last 5 lines |
| Bash tool waiting for output | `(2m 15s · ↓)` | **Maybe** — duration pattern may match |
| Between Bash runs (at prompt) | `❯` | **No** — looks idle |
| `check-gated` semaphore wait | `Waiting for slot` in Bash output | **No** — no spinner glyph |

The guard's 5-line tail window is calibrated for LLM inference (where the
spinner is always at the very bottom). Long-running Bash commands render
differently.

## Failure Sequence (Reconstructed)

```
T+0:00  Lane finishes implementation, stages files
T+0:01  Lane runs `make check-gated` via Bash tool
T+0:05  make check-gated starts polling for semaphore slot
T+0:15  Slot acquired, `make check-quiet` begins
T+0:20  Monitor cycle 1: activity_epoch=A, pane shows Bash running
        → _detect_active_work might catch spinner, might not (5-line window)
T+1:30  Monitor cycle 2: activity_epoch=A (unchanged — quiet output)
        → capture_pane: no -S flag, spinner above visible area
        → _detect_active_work: last 5 lines = status bar + prompt
        → unchanged_count = 1
T+2:40  Monitor cycle 3: activity_epoch=A (still unchanged)
        → unchanged_count = 2 ≥ STALL_CONSECUTIVE_CYCLES (2)
        → _detect_active_work MISSES the Bash spinner
        → STALL DETECTED → re-nudge sent

Meanwhile: make check is still running, will finish at T+3:00
```

Or for the manual path:
```
T+0:00  Lane running make check (Bash tool active)
T+1:00  Orchestrator runs /check-in → /lane-status
        → tmux capture shows `❯` prompt (status bar)
        → git status shows dirty files
        → Matrix: Idle + Dirty + No PR = STALLED
        → Orchestrator sends nudge or redispatches
```

## Recommended Detection Methods

### Option 1: Process-Level Detection (Recommended)

**Detect `make check` processes directly** via the OS process tree.

```bash
# Check if any make/pytest/ruff process is running in the lane's pane
PANE_PID=$(tmux display-message -t steward:platform.1 -p '#{pane_pid}')
pgrep -P "$PANE_PID" -af "make|pytest|ruff" 2>/dev/null
```

If `pgrep` returns results, the lane is running validation — not stalled.

**Advantages:**
- No false positives: if pytest/ruff/make is running, validation is in progress
- Works regardless of terminal output (quiet mode, semaphore wait, etc.)
- Simple, low-cost probe
- Immune to TUI rendering differences

**Disadvantages:**
- Requires knowledge of the lane's pane PID
- Process tree traversal may be OS-dependent (works on macOS/Linux)
- Need to handle `make check-gated` → `make check-quiet` → `make check` chain

### Option 2: Message Bus Signals

Have lanes emit explicit signals around validation:

```python
# In the agent's pre-PR workflow:
message_bus.send(from=lane, to="orchestrator", type="progress",
                 summary="validation_started: make check-gated")
# ... make check runs ...
message_bus.send(from=lane, to="orchestrator", type="progress",
                 summary="validation_completed: make check-gated passed")
```

**Advantages:**
- Unambiguous signal
- Works with any validation command, not just `make check`
- Can carry structured data (start time, expected duration)

**Disadvantages:**
- Requires changes to every lane's workflow (skill updates)
- Signals could go stale if make check crashes
- Adds message bus traffic

### Option 3: Semaphore/Lock File Detection

`make check-gated` already creates slot files in `/tmp/make-check-slots/`. The
monitor can check for the existence of these files:

```bash
# Check if any make-check slot is occupied by this lane's process
ls /tmp/make-check-slots/ 2>/dev/null
```

**Advantages:**
- Already exists — no new mechanism needed
- Directly indicates validation in progress

**Disadvantages:**
- Only covers `check-gated`, not `check-quiet` or plain `check`
- Slot files use PID, so need mapping from PID → lane
- Files could go stale if process crashes

### Option 4: Enhanced Pane Capture (Incremental Fix)

Fix the two specific bugs in the automated detection:

1. **Add `-S -50` to `_capture_pane_content`** (monitor.py:1190)
2. **Increase `_ACTIVITY_TAIL_LINES` from 5 to 15** (monitor.py:1124)
3. **Add Bash-specific detection patterns** to `_ACTIVE_WORK_PATTERNS`:
   ```python
   # make check progress indicators
   re.compile(r"Running full check|Waiting for.*slot|make\[", re.IGNORECASE),
   # make check-quiet completion
   re.compile(r"All checks passed|Checks FAILED", re.IGNORECASE),
   ```

**Advantages:**
- Smallest code change
- Fixes the specific bug in `_detect_active_work`

**Disadvantages:**
- Still relies on pane capture — fragile to TUI rendering changes
- 15-line window is better but still a heuristic
- Doesn't address the manual (skill-based) assessment path

## Recommended Implementation Plan

**Phase 1 — Immediate Fix (1 PR): Enhanced Pane Capture**

Fix the automated detection to stop producing false stall findings:

| File | Change |
|------|--------|
| `src/bid_euchre/ops/monitor.py:1190` | Add `-S`, `-50` to capture args |
| `src/bid_euchre/ops/monitor.py:1124` | Increase `_ACTIVITY_TAIL_LINES` to 15 |
| `src/bid_euchre/ops/monitor.py:1112-1121` | Add `make check` patterns to `_ACTIVE_WORK_PATTERNS` |
| `tests/unit/test_ops_monitor_stall.py` | Add test: Bash spinner in line 8 is detected |
| `tests/unit/test_ops_monitor_stall.py` | Add test: "Running full check" line is detected |

**Phase 2 — Process-Level Guard (1 PR): Stall Detection Enhancement**

Add a process-tree check as a secondary guard in `check_stalled_lanes`:

| File | Change |
|------|--------|
| `src/bid_euchre/ops/monitor.py` | New `_detect_background_validation()` using pane PID + pgrep |
| `src/bid_euchre/ops/monitor.py:1008` | Add process check before stall escalation |
| `tests/unit/test_ops_monitor_stall.py` | Add test: stall suppressed when validation process detected |

Insert the check at `monitor.py:1008` (after the active-work guard):
```python
if pane_content is not None and _detect_active_work(pane_content):
    # ... existing reset ...
    continue

# Phase 2: Process-level guard — check for running validation
if _detect_background_validation(lane_id, tmux_session, runtime_dir):
    observations[lane_id]["unchanged_count"] = 0
    observations[lane_id]["recovery_count"] = 0
    continue
```

**Phase 3 — Skill Update (1 PR): Manual Assessment Path**

Update the lane-status skill to handle the "dirty + idle" ambiguity:

| File | Change |
|------|--------|
| `.claude/skills/lane-status/SKILL.md` | Add "Validation In Progress" row to cross-reference matrix |
| `.claude/skills/lane-status/SKILL.md` | Add process-check command to Signal 1 workflow |
| `.claude/skills/check-in/SKILL.md` | Add note about make-check false positives |
| `.claude/skills/capture-pane/SKILL.md` | Add "VALIDATING" activity marker |

New cross-reference matrix row:
```
| Idle (but bg process) | Dirty (>0/0) | None | **VALIDATING** — make check running | Wait 3-5 min |
```

New activity marker for capture-pane:
```
| **VALIDATING** | make/pytest/ruff process running in pane PID tree |
```

## Acceptance Criteria

1. `_detect_active_work` returns `True` for a pane showing `⏺ Bash(make check-gated)` at line 8 (outside old 5-line window)
2. `_detect_active_work` returns `True` for a pane showing `>>> Running full check`
3. `check_stalled_lanes` does NOT flag a lane as stalled when `make` or `pytest` is running in its pane's process tree
4. Lane-status skill documents the VALIDATING state
5. No regression: actual stalls (idle pane, no background processes, dirty worktree) are still detected

## Validation Commands

```bash
# Phase 1 — unit tests for enhanced detection
uv run python -m pytest tests/unit/test_ops_monitor_stall.py -v

# Phase 2 — process-level guard tests
uv run python -m pytest tests/unit/test_ops_monitor_stall.py -v -k "validation"

# Full suite (before PR)
make check-quiet
```

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Increasing `_ACTIVITY_TAIL_LINES` to 15 could cause false negatives (real stalls undetected) | LOW | Real stalls have no spinner/progress anywhere in the pane |
| Process-tree detection misidentifies unrelated `make` processes | LOW | Scope pgrep to the specific pane PID tree |
| Approval stall detection (separate system) could also be affected | NONE | Approval stall already has its own active-work guard |
| Expanding `-S -50` capture increases monitor cycle time | LOW | tmux capture is fast (~5ms); 50 lines is negligible |
| Stale slot files in `/tmp/make-check-slots/` after crashes | LOW | Phase 2 uses process tree, not slot files |

## Scope Traps

- **Do NOT** change the `STALL_THRESHOLD_MINUTES` (10 min) or
  `STALL_CONSECUTIVE_CYCLES` (2) — these are correctly tuned for real stalls;
  the bug is in _detection_, not _thresholds_.
- **Do NOT** add message bus signals in Phase 1 — that's a larger workflow
  change best evaluated separately.
- **Do NOT** modify the orchestrator's main loop or dispatch logic — the fix
  is entirely in the monitoring/detection layer.

## Outcome

_To be filled after implementation._

## References

- `src/bid_euchre/ops/monitor.py` — stall detection, active-work guard
- `.claude/skills/lane-status/SKILL.md` — manual lane assessment
- `.claude/skills/capture-pane/SKILL.md` — pane capture methodology
- `.claude/skills/check-in/SKILL.md` — orchestrator check-in flow
- `Makefile:70-104` — check-quiet and check-gated targets
- Issue #1612 — original active-work guard addition
