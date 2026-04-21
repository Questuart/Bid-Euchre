---
name: lane-status
description: Correctly assess the working state of all steward lanes by reading the heartbeat signal, process tree, pane content, worktree state, and PR status together. Use before making dispatch or nudge decisions.
---

# /lane-status — Lane State Assessment

Accurately determine what each lane is doing before making orchestration
decisions (dispatch, nudge, recovery, or reporting).

## Why This Exists

The tmux status bar at the bottom of each pane ALWAYS shows the idle `❯`
prompt, token count, and model info — even when the session is actively
working. Reading only the last few lines of a pane capture will
systematically misclassify active lanes as idle.

The heartbeat hook (PR #2686) and `lane status` CLI (PR #2695) now give a
more reliable first read than the pane-capture heuristic. This skill
documents both the quickest CLI path and the manual multi-signal fallback
that remains load-bearing for approval-prompt detection and the rare
edge cases the CLI cannot resolve on its own.

## Quickest path — heartbeat-aware CLI

For the common case of "is lane X working or idle right now?", prefer the
shipped CLI consumer from PR #2695:

```bash
# Single lane
uv run python scripts/internal/ops.py lane status <lane-id>

# All registered lanes, fixed-width table
uv run python scripts/internal/ops.py lane status --all

# All lanes, JSON (for scripting / filtering)
uv run python scripts/internal/ops.py --json lane status --all

# Hook / cron context — skip the subprocess-spawning process-tree reconciler
uv run python scripts/internal/ops.py lane status --all --no-process-tree
```

The CLI renders a fixed-width table with columns `LANE`, `PHASE`, `FRESH`,
`LAST_TOOL`, `SUMMARY`, where `PHASE` ∈ `{active, likely_active, stale,
blocked, idle, unknown}`. It is powered by Signal 1 (the heartbeat file at
`<worktree>/.claude/runtime/lane_status/<lane>.json` written by the PR
#2686 PostToolUse hook) plus a process-tree reconciler (Signal 2) that
upgrades `stale`/`idle` to `likely_active` when a live tmux pane or
`claude` child process is detected.

The `ops.py dashboard` surface (PR 3/3 #2415) renders the heartbeat age
inline for each lane. Use it for a single-screen fleet overview; use
`lane status` for the authoritative per-lane determination.

The manual multi-signal procedure below is still correct for edge cases:
classifying approval-blocked lanes, deciding whether a dirty worktree
represents active work or a stall, or cross-checking when a lane reports
`stale` but you suspect the pre-#2686 heartbeat blind spot (sessions that
launched before 2026-04-21).

## Assessment Procedure (manual, 5-signal)

Gather the signals below in priority order and cross-reference them.
Signals 1 and 2 are the primary determinants; Signals 3–5 remain
load-bearing for approval detection, stall disambiguation, and
completion verification.

### Signal 1: Heartbeat (PR #2686)

```bash
# Read the heartbeat file for a lane
cat <worktree>/.claude/runtime/lane_status/<lane>.json 2>/dev/null
```

The JSON records `updated_at`, `last_tool`, and `phase`. A heartbeat
within the freshness threshold (default 120s) is the strongest signal
that a lane is actively executing tool calls.

| Age | Interpretation |
|-----|---------------|
| ≤120s | **WORKING** — PostToolUse hook fired recently |
| 120s–30m | **STALE** — lane may have crashed or is blocked on a long subprocess |
| >30m or missing | **LEGACY / IDLE** — no heartbeat signal; fall through to Signals 2–5 |

Missing heartbeat does not imply idle: lanes launched before 2026-04-21
may not have the hook registered. Always cross-reference with Signal 2.

### Signal 2: Process tree

```bash
# Check for active validation processes in the lane's worktree
pgrep -f "pytest|make|ruff" 2>/dev/null
# Or consult the ops CLI, which does this with proper pane targeting:
uv run python scripts/internal/ops.py lane status <lane-id>
```

A live `pytest`, `make`, or `ruff` process under the lane's tmux pane
shell is definitive evidence the lane is working even when the
heartbeat is stale (heartbeat cadence is bounded by Claude's tool-call
loop, which pauses during long subprocess waits).

### Signal 3: Pane content (full scan)

Capture enough of the pane to see the working area, not just the status bar:

```bash
tmux capture-pane -t steward:<window>.<pane> -p -S -40 2>/dev/null
```

The `-S -40` flag captures the last 40 lines (above the status bar).

Pane scanning remains the **only** reliable signal for approval-blocked
lanes — permission prompts appear on the pane but do not emit heartbeat
ticks or process-tree evidence.

**Active-work indicators** (if ANY of these are present, the lane is WORKING):
- Spinner glyphs: `✶` `✻` `✽` `✢` `⏺` `✳`
- Status text: `Running…`, `Determining…`, `Imagining…`, `Whirring…`,
  `Moonwalking…`, `Undulating…`, `Osmosing…`, `Sautéed`, `Cooked`,
  `Worked`, `Drizzling…` or any similar participle with `…`
- Timeout indicators: `timeout 5m`, `timeout 2m`
- Active duration: `(Nm Ns · ↓` or `(Ns ·`
- Tool execution: `Bash(`, `Edit(`, `Read(`, `Write(`

**Idle indicators** (lane is at prompt, NOT working):
- The ONLY content above the status bar is a blank `❯` prompt with no
  spinner, no tool call, no duration counter
- Or the pane shows a completed summary like `✻ Sautéed for Xm Ys` with
  NO subsequent tool call or spinner

**Approval-blocked indicators** (primary use of Signal 3):
- `Allow ` followed by a tool name
- `[A]llow once` / `[Y]es, always` / `[N]o`
- `Permission required`
- `Do you want to`

### Signal 4: Worktree state

```bash
git -C <worktree_path> status --short | wc -l    # dirty file count
git -C <worktree_path> log --oneline origin/main..HEAD | wc -l  # commits ahead
```

| Dirty | Ahead | Interpretation |
|-------|-------|---------------|
| 0 | 0 | Clean — either hasn't started or work was committed+pushed |
| >0 | 0 | Has uncommitted changes — either mid-work or stalled post-validation |
| >0 | >0 | Has commits + more uncommitted changes — actively working |
| 0 | >0 | Committed but not pushed — may be about to push/PR |

### Signal 5: PR status

```bash
# Check if the lane's branch has an open PR
git -C <worktree_path> branch --show-current
gh pr list --state open --head <branch_name> --json number,title
```

### Cross-Reference Matrix

Signals are listed in priority order; the leftmost non-empty column
determines the classification.

| Heartbeat | Process tree | Pane | Worktree | PR | True State | Action |
|-----------|-------------|------|----------|-----|------------|--------|
| Fresh (≤120s) | — | — | — | — | **WORKING** | Do nothing |
| Stale / missing | `pytest\|make\|ruff` match | — | — | — | **VALIDATING** | Do nothing — let validation finish |
| Stale / missing | — | Active spinner | — | — | **WORKING** | Do nothing |
| Stale / missing | — | Idle | Clean (0/0) | None | **IDLE** — ready for dispatch | Safe to dispatch |
| Stale / missing | — | Idle | Dirty (>0/0) | None | **STALLED** — finished but didn't commit | Nudge to commit |
| Stale / missing | — | Idle | Ahead (0/>0) | None | **STALLED** — committed but didn't PR | Nudge to push+PR |
| — | — | Idle | Ahead (0/>0) | Open | **DONE** — PR is open | Complete the packet |
| — | — | Idle | Clean (0/0) | Merged | **DONE** — PR merged | Complete packet, lane is free |
| — | — | Approval prompt | Any | Any | **BLOCKED** — needs user | Alert user immediately |

## Pane Map

| Window | Pane | Lane | Check? |
|--------|------|------|--------|
| central-ops | .1 | orchestrator | No (that's us) |
| central-ops | .2 | ops | No (monitoring) |
| central-ops | .3 | review | No (review) |
| platform | .1 | author-a | Yes |
| platform | .2 | author-b | Yes |
| platform | .3 | author-c | Yes |
| platform | .4 | author-d | Yes |
| browser | .1 | brws-author-a | Yes |
| browser | .2 | brws-author-b | Yes |
| browser | .3 | brws-author-c | Yes |
| browser | .4 | brws-author-d | Yes |
| scratch | .1 | author-scratch | Yes |
| scratch | .2 | flex-a | Yes |
| scratch | .3 | flex-b | Yes |
| scratch | .4 | flex-c | Yes |

## Quick All-Lanes Check

The CLI replaces the pane-capture loop for the common case:

```bash
uv run python scripts/internal/ops.py lane status --all
```

If you need the legacy pane+worktree dump (e.g., approval-prompt sweep),
the loop below is still supported:

```bash
# For each dispatched lane, check pane + worktree in one pass
for entry in "platform.1:/path/to/author" "platform.2:/path/to/author-b" ...; do
  pane="${entry%%:*}"
  dir="${entry##*:}"

  # Pane: look for spinners (active work)
  has_spinner=$(tmux capture-pane -t "steward:${pane}" -p -S -30 2>/dev/null \
    | grep -cE '✶|✻|✽|✢|⏺|✳|Running…|timeout|Imagining|Determining|Whirring')

  # Worktree: dirty + ahead counts
  dirty=$(git -C "$dir" status --short 2>/dev/null | wc -l | tr -d ' ')
  ahead=$(git -C "$dir" log --oneline origin/main..HEAD 2>/dev/null | wc -l | tr -d ' ')

  echo "${pane}: spinner=${has_spinner} dirty=${dirty} ahead=${ahead}"
done
```

## Anti-Patterns

- ❌ Reading only `tail -8` or `tail -12` of pane capture (hits status bar)
- ❌ Assuming idle prompt = lane is idle (status bar always shows `❯`)
- ❌ Nudging a lane that's mid-`make check-gated` (interrupts validation)
- ❌ Treating "Sautéed for Xm" as idle without checking if a new tool call follows
- ❌ Checking worktree state without checking Signals 1–3 (dirty could mean mid-work)
- ❌ Treating a stale heartbeat as idle without checking the process tree — a long
  `make check-quiet` run will pause tool calls and let the heartbeat age past the
  default 120s threshold without the lane actually stalling

## When to Use

- Before every dispatch decision
- Before nudging any lane
- During `/check-in` status reports
- Before declaring a lane stalled or idle
