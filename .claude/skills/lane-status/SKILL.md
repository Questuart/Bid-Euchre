---
name: lane-status
description: Correctly assess the working state of all steward lanes by reading tmux pane content, worktree state, and PR status together. Use before making dispatch or nudge decisions.
---

# /lane-status — Lane State Assessment

Accurately determine what each lane is doing before making orchestration
decisions (dispatch, nudge, recovery, or reporting).

## Why This Exists

The tmux status bar at the bottom of each pane ALWAYS shows the idle `❯`
prompt, token count, and model info — even when the session is actively
working. Reading only the last few lines of a pane capture will
systematically misclassify active lanes as idle. This skill prevents that.

## Assessment Procedure

For each lane, gather THREE signals and cross-reference them:

### Signal 1: Pane Content (full scan)

Capture enough of the pane to see the working area, not just the status bar:

```bash
tmux capture-pane -t steward:<window>.<pane> -p -S -40 2>/dev/null
```

The `-S -40` flag captures the last 40 lines (above the status bar).

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

**Approval-blocked indicators:**
- `Allow ` followed by a tool name
- `[A]llow once` / `[Y]es, always` / `[N]o`
- `Permission required`
- `Do you want to`

### Signal 2: Worktree State

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

### Signal 3: PR Status

```bash
# Check if the lane's branch has an open PR
git -C <worktree_path> branch --show-current
gh pr list --state open --head <branch_name> --json number,title
```

### Cross-Reference Matrix

| Pane | Worktree | PR | True State | Action |
|------|----------|-----|------------|--------|
| Active spinner | Any | Any | **WORKING** | Do nothing |
| Idle | Clean (0/0) | None | **IDLE** — ready for dispatch | Safe to dispatch |
| Idle | Dirty (>0/0) | None | **STALLED** — finished but didn't commit | Nudge to commit |
| Idle | Ahead (0/>0) | None | **STALLED** — committed but didn't PR | Nudge to push+PR |
| Idle | Ahead (0/>0) | Open | **DONE** — PR is open | Complete the packet |
| Idle | Clean (0/0) | Merged | **DONE** — PR merged | Complete packet, lane is free |
| Approval prompt | Any | Any | **BLOCKED** — needs user | Alert user immediately |

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

Run this to get a fast overview of all dispatched lanes:

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
- ❌ Checking worktree state without checking pane state (dirty could mean mid-work)

## When to Use

- Before every dispatch decision
- Before nudging any lane
- During `/check-in` status reports
- Before declaring a lane stalled or idle
