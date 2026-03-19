# Daemon Failure Notification Hook

**Date:** 2026-03-17
**Scope:** Small (3-4 files, one concept)
**Branch:** `daemon-failure-notifications`

## Problem

Background daemons (`ci_poller.sh`, `review_driver.py`) launched by PostToolUse
hooks run autonomously after `git push` / `gh pr create`. When they fail (CI
failure, timeout, merge error, crash), the failure is written to log files that
nobody reads. The agent that created the PR is never notified.

## Solution

Add a lightweight feedback loop:

1. **Sentinel files** — Each daemon writes a `FAILED` sentinel on non-success exit
2. **Notification hook** — A PostToolUse hook checks for unacknowledged sentinels
   and injects failure context into the agent's next tool response
3. **One-shot delivery** — Sentinel is renamed `NOTIFIED` after injection to
   avoid repeated alerts

## Design

### Sentinel format

File: `.claude/runtime/{ci_polls,review_loops}/pr_<N>/FAILED`

```
CI_FAILED: Failed checks: tests (build)
```

One line, plain text. The hook reads it and injects verbatim.

### Daemon changes

**`ci_poller.sh`** — Write sentinel on exit codes 1 (CI/merge failed) and 2 (timeout):
- Before `exit 1` on CI failure: `echo "CI_FAILED: $detail" > "$STATE_DIR/FAILED"`
- Before `exit 1` on merge failure: `echo "MERGE_FAILED: $detail" > "$STATE_DIR/FAILED"`
- Before `exit 2` on timeout: `echo "CI_TIMEOUT: $detail" > "$STATE_DIR/FAILED"`

**`review_driver.py`** — Write sentinel on terminal failure states:
- `STOPPED_CI_FAILURE` → write FAILED
- `STOPPED_CODEX_FAILURE` → write FAILED
- `STOPPED_PRECHECK_FAILURE` → write FAILED
- Unhandled exception → write FAILED (in the except block)

### Notification hook

**`post-tool-daemon-notify.sh`** — New PostToolUse hook on Bash:

```
1. Glob .claude/runtime/*/pr_*/FAILED
2. For each FAILED file:
   a. Read daemon type (ci_polls vs review_loops) and PR number from path
   b. Read one-line summary from file contents
   c. Rename FAILED → NOTIFIED
   d. Append to output message
3. Emit hookSpecificOutput with additionalContext listing all failures
```

Timeout: 5s (only reads local files, no network).

### Hook registration

Add to `.claude/settings.json` PostToolUse Bash hooks array:

```json
{
  "type": "command",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post-tool-daemon-notify.sh",
  "timeout": 5
}
```

## Files Changed

| File | Change |
|------|--------|
| `scripts/internal/ci_poller.sh` | Add FAILED sentinel writes at 3 exit points |
| `scripts/internal/review_driver.py` | Add FAILED sentinel writes at terminal failure states |
| `.claude/hooks/post-tool-daemon-notify.sh` | New hook (reads sentinels, injects context) |
| `.claude/settings.json` | Register new hook |

## Testing

- Manual: simulate a FAILED sentinel, run a Bash command, verify hook output
- Unit: add test for sentinel write paths in ci_poller (shell) and review_driver

## Outcome

Implemented in PR #810 (merged 2026-03-18). Daemon failure notifications wired via
PostToolUse hook — sentinels written on CI/review daemon failures, hook injects
failure context into agent's next tool response.
