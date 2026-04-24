# Incident example_fingerprint

> **This is a worked example** for the `incidents/` directory schema.
> Real incident files are named `<incident_fingerprint>.md` where the
> fingerprint is emitted by `src/bid_euchre/ops/event_taxonomy.py` at
> incident-event emission time. The fingerprint here (`example_fingerprint`)
> is a placeholder; a real fingerprint is a short hash (~8 hex chars) and
> matches the `incident_fingerprint` field of the emitted event.

### Incident example_fingerprint

**First seen:** 2026-04-20 (illustrative)

**Symptoms:** Review lane respawned in `bypassPermissions` mode despite
`defaultMode: "auto"` being set in `.claude/settings.json`. Tool calls
routed without classifier gating; `PermissionDenied` events never
emitted.

**Root cause:** The `tmux respawn-pane` command launched `claude`
without the `--permission-mode auto` flag. `defaultMode` in settings
acts as a routing default, not an activation flag — the CLI only
activates auto mode when the launch command includes the flag
explicitly.

**Fix:** Added `--permission-mode auto` to every `$CLAUDE_BIN` launch
line in `.claude/tmux/steward-session.sh` and to the headless
`subprocess.run` call in `scripts/internal/review_lane_runner.py::invoke_review`.
Locked in with structural tests:
`tests/unit/test_steward_session.py::TestPermissionModeAuto` and
`tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionMode`.

**Event trace:** `trace_id` list populated from `ops/events.jsonl` at
incident-write time — format: `[trace_id_1, trace_id_2, ...]`. For this
worked example, no real trace is listed.

**References:**
- Issue #2685 — discovery context
- `.claude/rules/80_permission_model.md` § Activation — codified the
  launch-flag requirement
- `plans/steward_platform/adrs/006-auto-mode.md` — ADR for auto-mode
  adoption
