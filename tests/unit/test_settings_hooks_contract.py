"""Settings.json hooks contract test — Primitive E Phase 0 Packet E1.

Asserts contract invariants over `.claude/settings.json` hook registrations:

1. Every hook script path referenced by a `command` field in any hook entry
   exists on disk.
2. No hook script is registered more than once under the same
   (event, matcher) pair — double registrations usually indicate stale
   authoring and waste tool-call latency.
3. Every `matcher: "*"` on `PostToolUse` or `PreToolUse` has a justified-retention
   row in the Disposition Table (Rationale ends with the
   `retained-universal-justified` sentinel).

Rationale: the settings file is the operational surface the Claude runtime
reads; the README.md Disposition Table is the review surface. Drift between
them manifests as (a) dangling hook paths that silently fail at runtime,
(b) duplicate registrations that double-fire without being reflected in the
review surface, or (c) universal matchers slipping in without the retention
rationale the review surface demands.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
README_PATH = HOOKS_DIR / "README.md"

DISPOSITION_HEADER_RE = re.compile(r"^###\s+Disposition\s+Table\s*$", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##?#?\s+\S", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|\s*`([^`]+?)`(?:\s*\([^)]*\))?\s*\|")


def _split_markdown_row(line: str) -> list[str]:
    """Split a markdown table row on `|` while respecting backtick-quoted
    cells (which may contain a literal `|` inside `` `...` ``).
    """
    cells: list[str] = []
    buf: list[str] = []
    in_backtick = False
    for ch in line:
        if ch == "`":
            in_backtick = not in_backtick
            buf.append(ch)
            continue
        if ch == "|" and not in_backtick:
            cells.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    cells.append("".join(buf).strip())
    return [c for c in cells if c != ""]


RETENTION_SENTINEL = "retained-universal-justified"

# Events where a `*` matcher fires on every tool call and therefore requires
# a justified-retention row. Other events (SessionStart, UserPromptSubmit,
# PermissionDenied) are low-volume discriminating events where `*` is
# implicitly event-scoped.
HIGH_VOLUME_EVENTS = {"PreToolUse", "PostToolUse"}


def _load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def _expand_command(command: str) -> Path:
    """Resolve $CLAUDE_PROJECT_DIR placeholders to actual repo paths.

    Returns the hook script path (absolute) that would be invoked.

    Handles two forms observed in settings.json:
    - Bare: `$CLAUDE_PROJECT_DIR/.claude/hooks/foo.sh`
    - Wrapped: `bash -lc '"$CLAUDE_PROJECT_DIR"/.claude/hooks/foo.sh'`
    """
    cleaned = command.replace("$CLAUDE_PROJECT_DIR", str(REPO_ROOT))
    cleaned = cleaned.replace("${CLAUDE_PROJECT_DIR}", str(REPO_ROOT))
    # Strip all shell quoting characters — we only want the script path.
    cleaned = cleaned.replace('"', "").replace("'", "")
    # Grab the first token ending in .sh or .py
    m = re.search(r"(\S+\.(?:sh|py))", cleaned)
    if m:
        return Path(m.group(1))
    return Path(cleaned)


def _iter_hook_entries(settings: dict):
    """Yield (event, matcher, command) for every hook entry."""
    hooks_block = settings.get("hooks", {})
    for event, entries in hooks_block.items():
        for entry in entries:
            matcher = entry.get("matcher")  # may be None for no-matcher events
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                yield event, matcher, cmd


def _parse_disposition_rows() -> list[dict[str, str]]:
    """Parse the Disposition Table from README.md into dicts."""
    text = README_PATH.read_text(encoding="utf-8")
    header_match = DISPOSITION_HEADER_RE.search(text)
    assert header_match, "Disposition Table missing from README.md"

    body_start = header_match.end()
    next_section = NEXT_SECTION_RE.search(text, body_start)
    body_end = next_section.start() if next_section else len(text)
    body = text[body_start:body_end]

    rows: list[dict[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        if "---" in line:
            continue
        if "| Hook " in line and "| Current Matcher " in line:
            continue
        cells = _split_markdown_row(line)
        if len(cells) < 5:
            continue
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        rows.append(
            {
                "hook": match.group(1),
                "current_matcher": cells[1],
                "proposed_matcher": cells[2],
                "disposition": cells[3],
                "rationale": cells[4],
            }
        )
    return rows


def test_every_hook_command_path_exists() -> None:
    """Every registered hook command MUST point to an existing script."""
    settings = _load_settings()
    missing: list[tuple[str, str | None, Path]] = []
    for event, matcher, cmd in _iter_hook_entries(settings):
        hook_path = _expand_command(cmd)
        if not hook_path.exists():
            missing.append((event, matcher, hook_path))
    assert not missing, (
        "Settings.json references hook scripts that do not exist on disk: "
        f"{[(e, m, str(p)) for e, m, p in missing]}"
    )


def test_no_duplicate_registrations() -> None:
    """No hook script is registered twice under the same (event, matcher)."""
    settings = _load_settings()
    key_counter: Counter[tuple[str, str | None, str]] = Counter()
    for event, matcher, cmd in _iter_hook_entries(settings):
        hook_path = _expand_command(cmd)
        key_counter[(event, matcher, hook_path.name)] += 1
    duplicates = [(k, v) for k, v in key_counter.items() if v > 1]
    assert not duplicates, (
        "Duplicate hook registrations (same script under same event+matcher): "
        f"{duplicates}"
    )


def test_no_split_registrations_under_related_matchers() -> None:
    """A script registered separately under `Write` and `Edit` should be
    consolidated to a single `Edit|Write` matcher — PostToolUse only.

    This is the specific migration applied in Primitive E Phase 0 Packet E1
    for `post-write-check.sh`. The test locks it in to prevent regression.
    """
    settings = _load_settings()
    per_script_matchers: dict[str, set[str | None]] = {}
    for event, matcher, cmd in _iter_hook_entries(settings):
        if event != "PostToolUse":
            continue
        hook_path = _expand_command(cmd)
        per_script_matchers.setdefault(hook_path.name, set()).add(matcher)

    regressions: list[tuple[str, set[str | None]]] = []
    for script, matchers in per_script_matchers.items():
        # If a script is registered under both "Write" and "Edit" as distinct
        # entries, that is the unconsolidated form.
        if {"Write", "Edit"}.issubset(matchers):
            regressions.append((script, matchers))
    assert not regressions, (
        "PostToolUse scripts registered separately under both `Write` and `Edit` "
        "must be consolidated to a single `Edit|Write` matcher entry: "
        f"{regressions}"
    )


def test_universal_matchers_on_high_volume_events_are_justified() -> None:
    """Every `*` matcher on PreToolUse/PostToolUse MUST map to a
    Disposition Table row whose Rationale ends with the sentinel
    `retained-universal-justified`.
    """
    settings = _load_settings()
    rows_by_hook = {row["hook"]: row for row in _parse_disposition_rows()}

    unjustified: list[tuple[str, str, str]] = []
    for event, matcher, cmd in _iter_hook_entries(settings):
        if event not in HIGH_VOLUME_EVENTS:
            continue
        if matcher != "*":
            continue
        hook_path = _expand_command(cmd)
        row = rows_by_hook.get(hook_path.name)
        if row is None:
            unjustified.append((event, hook_path.name, "no row in Disposition Table"))
            continue
        if row["disposition"] != "retained-universal-justified":
            unjustified.append(
                (
                    event,
                    hook_path.name,
                    f"disposition={row['disposition']} (expected retained-universal-justified)",
                )
            )
            continue
        if RETENTION_SENTINEL not in row["rationale"]:
            unjustified.append(
                (event, hook_path.name, "rationale missing retention sentinel")
            )

    assert not unjustified, (
        "Universal matchers on PreToolUse/PostToolUse without a "
        "retained-universal-justified Disposition Table row: "
        f"{unjustified}"
    )


def test_settings_json_parses_and_has_hooks_block() -> None:
    """Sanity: settings.json is valid JSON and has a hooks block."""
    settings = _load_settings()
    assert "hooks" in settings, "settings.json missing top-level `hooks` block"
    assert isinstance(settings["hooks"], dict), "`hooks` must be an object"


def test_expand_command_resolves_project_dir() -> None:
    """Regression test: _expand_command correctly resolves $CLAUDE_PROJECT_DIR.

    Runs without a real environment lookup so the test is hermetic.
    """
    # Unset any ambient env to ensure the resolver uses REPO_ROOT, not env
    saved = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    try:
        p = _expand_command("$CLAUDE_PROJECT_DIR/.claude/hooks/post-write-check.sh")
        assert p == REPO_ROOT / ".claude/hooks/post-write-check.sh"
        # Wrapped form used for lane-heartbeat-post-tool.sh
        p2 = _expand_command(
            "bash -lc '\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lane-heartbeat-post-tool.sh'"
        )
        assert p2 == REPO_ROOT / ".claude/hooks/lane-heartbeat-post-tool.sh"
    finally:
        if saved is not None:
            os.environ["CLAUDE_PROJECT_DIR"] = saved
