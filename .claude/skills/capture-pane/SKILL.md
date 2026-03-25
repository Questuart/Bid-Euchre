---
name: capture-pane
description: Captures tmux pane content for lane inspection — supports single-lane, batch, and stuck-only modes with structured output (tokens, stuck status, activity markers, idle flag). Use from orchestrator or ops to inspect lane state without switching windows.
---

# /capture-pane — Lane Content Inspection

Capture and parse tmux pane content for one or all lanes. Returns structured
status for each inspected lane: tokens, stuck status, last activity marker,
and idle flag.

## Arguments

- `[lane-id]` — Inspect a single lane (e.g., `author-a`, `flex-a`, `ops`)
- `--all` — Scan all lanes in one pass
- `--stuck` — Show only lanes that appear stuck (permission prompts, stalled)

If no argument is given, default to `--all`.

## When to Use

- During fleet orchestration to quickly scan lane health
- Before dispatch decisions — verify a lane is truly idle
- When ops alerts report a potential stall
- To inspect a specific lane without switching tmux windows
- As a building block for `/check-in` and `/lane-status`

## Pane Map

Each lane maps to a tmux pane in the `steward` session:

| Lane ID | Tmux Target | Window |
|---------|-------------|--------|
| orchestrator | steward:central-ops.1 | central-ops |
| analyst | steward:central-ops.2 | central-ops |
| ops | steward:central-ops.3 | central-ops |
| review | steward:central-ops.4 | central-ops |
| author-a | steward:platform.1 | platform |
| author-b | steward:platform.2 | platform |
| author-c | steward:platform.3 | platform |
| author-d | steward:platform.4 | platform |
| brws-author-a | steward:browser.1 | browser |
| brws-author-b | steward:browser.2 | browser |
| brws-author-c | steward:browser.3 | browser |
| brws-author-d | steward:browser.4 | browser |
| author-scratch | steward:scratch.1 | scratch |
| flex-a | steward:scratch.2 | scratch |
| flex-b | steward:scratch.3 | scratch |
| flex-c | steward:scratch.4 | scratch |

## Workflow

### Step 1 — Capture Pane Content

For each lane to inspect, capture at least 50 lines of scrollback (30+
content lines above the status bar):

```bash
tmux capture-pane -t steward:<window>.<pane> -p -S -50 2>/dev/null
```

The `-S -50` flag requests 50 lines of history (above current cursor),
ensuring at least 30 lines of usable content above the status bar. If a lane
needs deeper inspection, increase to `-S -100` or `-S -200`.

**Important:** Without `-S`, `tmux capture-pane` returns only the visible
portion of the pane, which is often just 15-20 lines — insufficient for
detecting stuck states or reading multi-step output.

### Step 2 — Parse Structured Signals

For each captured pane, extract these fields:

#### Token Count

Look for the token counter in the status bar area (typically last 2-3 lines):

```
Pattern: /(\d+[\d,]*k?\s*tokens?|\d+[\d,]*k?\s*↓)/i
Example: "125k tokens" or "45,231 ↓"
```

If no token count is visible, report `tokens: unknown`.

#### Stuck Status

A lane is **stuck** if ANY of these patterns appear in the captured content:

| Pattern | Stuck Reason |
|---------|-------------|
| `Allow ` followed by a tool name | Permission prompt |
| `[A]llow once` / `[Y]es, always` | Permission prompt |
| `Permission required` | Permission prompt |
| `Do you want to` | Edit approval |
| `Do you want to make this edit` | Settings edit approval |
| `1. Yes, allow` / `2. No, skip` | Numbered menu prompt |
| `waiting for input` | Input prompt |

Report: `stuck: true` with the detected reason, or `stuck: false`.

#### Activity Marker

Classify the lane's current activity state:

| Marker | Indicators |
|--------|-----------|
| **WORKING** | Spinner glyphs (`✶ ✻ ✽ ✢ ⏺ ✳`), status text with `…` (`Running…`, `Determining…`, `Imagining…`, `Whirring…`, `Moonwalking…`, `Osmosing…`), active duration `(Nm Ns ·`, tool execution `Bash(`, `Edit(`, `Read(`, `Write(` |
| **IDLE** | Only a blank `❯` prompt with no spinner or tool call above it |
| **COMPLETED** | Summary line like `✻ Sautéed for Xm Ys` with no subsequent tool call |
| **STUCK** | Any stuck-status pattern from above |
| **EMPTY** | Pane capture returned no content or tmux target not found |

#### Idle Flag

- `idle: true` — activity is IDLE or COMPLETED and no stuck patterns
- `idle: false` — activity is WORKING or STUCK

### Step 3 — Format Output

#### Single Lane

```
CAPTURE: author-a (steward:platform.1)
─────────────────────────────────────────
  tokens:   125k
  stuck:    false
  activity: WORKING (Running… 2m 15s)
  idle:     false

  Content (last 30 lines):
  ─────────────────────────
  [captured pane content here]
```

#### Batch Mode (--all or --stuck)

```
LANE SCAN @ 2026-03-25T04:30:00Z
════════════════════════════════════
Lane              Tokens   Stuck  Activity    Idle
────────────────  ───────  ─────  ──────────  ────
orchestrator      45k      no     WORKING     no
ops               12k      no     IDLE        yes
review            8k       no     COMPLETED   yes
author-a          125k     no     WORKING     no
author-b          0        no     EMPTY       yes
author-c          67k      YES    STUCK       no
author-d          34k      no     IDLE        yes
brws-author-a     0        no     EMPTY       yes
brws-author-b     0        no     EMPTY       yes
brws-author-c     0        no     EMPTY       yes
brws-author-d     0        no     EMPTY       yes
author-scratch    0        no     EMPTY       yes
flex-a            22k      no     WORKING     no
flex-b            0        no     EMPTY       yes
flex-c            0        no     EMPTY       yes

Summary: 3 working, 2 idle, 1 stuck, 9 empty
Stuck lanes: author-c (permission prompt)
```

For `--stuck` mode, only show lanes where `stuck: true`.

### Step 4 — Batch Capture Script

For efficiency, run all pane captures in one pass using this script:

```bash
SESSION="steward"
LANES=(
  "orchestrator:central-ops.1"
  "analyst:central-ops.2"
  "ops:central-ops.3"
  "review:central-ops.4"
  "author-a:platform.1"
  "author-b:platform.2"
  "author-c:platform.3"
  "author-d:platform.4"
  "brws-author-a:browser.1"
  "brws-author-b:browser.2"
  "brws-author-c:browser.3"
  "brws-author-d:browser.4"
  "author-scratch:scratch.1"
  "flex-a:scratch.2"
  "flex-b:scratch.3"
  "flex-c:scratch.4"
)

for entry in "${LANES[@]}"; do
  lane="${entry%%:*}"
  pane="${entry##*:}"
  echo "=== ${lane} (${SESSION}:${pane}) ==="
  tmux capture-pane -t "${SESSION}:${pane}" -p -S -50 2>/dev/null || echo "(not found)"
  echo ""
done
```

For a single lane, extract just the relevant entry:

```bash
tmux capture-pane -t steward:<window>.<pane> -p -S -50 2>/dev/null
```

## Gotchas

- **Status bar pollution:** The last 2-3 lines of pane capture are the tmux
  status bar / Claude prompt line — do not classify these as working content.
  The status bar always shows `❯` even when the session is actively working.
  Look at the lines *above* the status bar for actual activity signals.

- **Spinner detection requires full capture:** Spinners appear mid-pane, not
  at the bottom. Capturing only 10-15 lines will miss them. Always use
  `-S -50` or deeper.

- **Empty panes:** If `tmux capture-pane` returns empty output or errors, the
  pane either doesn't exist or hasn't been used. Report as EMPTY, not STUCK.

- **Token count format varies:** Some sessions show `45k tokens`, others show
  `45,231 ↓`. Both are valid token indicators. The counter can also appear as
  part of a model string like `claude-3-5-sonnet · 45k`.

- **Completed vs Idle:** A lane showing `✻ Sautéed for 5m 23s` is COMPLETED,
  not IDLE. It finished its last task. An IDLE lane shows only the bare prompt
  with no completion summary above it.

- **Don't capture your own pane** during a batch scan — the capture will show
  the capture command itself, creating confusion. Skip the pane where this
  skill is running.

## Relationship to Other Skills

| Skill | Scope | Overlap |
|-------|-------|---------|
| `/capture-pane` | Raw pane capture + structured parsing | Pane signals only |
| `/lane-status` | Cross-references pane + worktree + PR signals | Uses this as input |
| `/check-in` | Full orchestrator status (inbox + lanes + PRs + issues) | Calls lane-status |

`/capture-pane` is the lowest-level building block — it reads tmux panes and
produces structured output. `/lane-status` adds worktree and PR context on top.
`/check-in` is the highest-level orchestrator routine.

## References

- `.claude/skills/lane-status/SKILL.md` — cross-reference with worktree + PR status
- `.claude/skills/check-in/SKILL.md` — periodic orchestrator status check
- `.claude/tmux/steward-session.sh` — canonical tmux layout and pane assignments
- Issue #1748 — motivation and requirements
