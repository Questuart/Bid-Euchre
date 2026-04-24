#!/usr/bin/env python3
"""File a GitHub issue for a canary failure mode (Primitive H.0).

Spec: ``plans/steward_platform/8_primitive_H/shaping.md`` §6 (failure-mode
routing matrix + issue-body templates + dedup logic).

Usage:

    # Dry run (render issue body to stdout, no gh call)
    uv run python scripts/internal/file_canary_issue.py --dry-run \\
        --mode canary-fail \\
        --canary-id dogfood-v1-test \\
        --failed-assertions 3,7

    # Real run (consumed by dogfood_v1.py on a failing canary)
    uv run python scripts/internal/file_canary_issue.py \\
        --mode canary-silent \\
        --last-pass 2026-04-01T00:00:00Z \\
        --days-since-last-pass 14

The script is idempotent per shape §6.4: if an open issue exists with the
same label + canary_id, the second call posts a comment rather than
creating a duplicate issue. This honors the idempotency checklist
row #9 (GitHub API writes).

Ops alert push (shape §6.3) is best-effort — if ``ops.py alert push``
is not yet wired (Primitive E dependency), the filing still succeeds
but no alert is fired. This matches §10.4 coordination note: "If E's
filing API is not yet live, ``file_canary_issue.py`` wraps
``gh issue create`` directly as a fallback (lose priority-routing
granularity but retain auto-filing)."

Exit codes:
    0 — issue filed (or comment posted; dedup hit)
    1 — failed to create issue / comment
    2 — invocation error (bad args)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("file_canary_issue")

# --------------------------------------------------------------------------- #
# Taxonomy — mirrors dogfood_v1.py FAILURE_MODE_EXIT_CODE and shape §6.1
# --------------------------------------------------------------------------- #

FailureMode = Literal[
    "canary-slow", "canary-fail", "canary-silent", "canary-schema-drift"
]

VALID_MODES: tuple[FailureMode, ...] = (
    "canary-slow",
    "canary-fail",
    "canary-silent",
    "canary-schema-drift",
)

# shape §6.1 routing matrix
_PRIORITY: dict[FailureMode, str] = {
    "canary-slow": "normal",
    "canary-fail": "high",
    "canary-silent": "high",
    "canary-schema-drift": "normal",
}

_ALERT_PUSH: dict[FailureMode, bool] = {
    "canary-slow": False,
    "canary-fail": True,
    "canary-silent": True,
    "canary-schema-drift": False,
}

_TITLE_TEMPLATE: dict[FailureMode, str] = {
    "canary-slow": "canary-slow: {canary_id} elapsed exceeded 2× median",
    "canary-fail": "canary-fail: {canary_id} — {first_failed_assertion}",
    "canary-silent": "canary-silent: no successful canary run in {days_since_last_pass}d",
    "canary-schema-drift": "canary-schema-drift: {canary_id} event-type set drifted",
}


# --------------------------------------------------------------------------- #
# Body renderers — verbatim from shape §6.2
# --------------------------------------------------------------------------- #


@dataclass
class IssueContext:
    """Context for rendering issue bodies.

    Only the fields relevant to the selected mode must be populated;
    others default to placeholders so the rendered body is still
    human-readable.
    """

    canary_id: str = "unknown"
    elapsed_seconds: float | None = None
    threshold_2x_median: float | None = None
    median_last_4: float | None = None
    elapsed_history: list[float] | None = None
    suspected: str = "(auto-triage pending)"

    failed_assertions: list[int] | None = None
    failed_assertion_names: list[str] | None = None
    first_failed_assertion_body: str = "(details unavailable)"
    hash_match: bool | None = None

    last_pass_timestamp: str = "never"
    days_since_last_pass: int | None = None
    weekly_cron_present: bool | None = None
    conditional_hook_registered: bool | None = None

    observed_hash: str = "(unknown)"
    pinned_hash: str = "(unknown)"
    set_diff_added: list[str] | None = None
    set_diff_missing: list[str] | None = None


def render_body(mode: FailureMode, ctx: IssueContext) -> str:
    """Render an issue body matching shape §6.2."""
    if mode == "canary-slow":
        return (
            f"**Canary run:** {ctx.canary_id}\n"
            f"**Elapsed:** {ctx.elapsed_seconds}s "
            f"(threshold: {ctx.threshold_2x_median}s; "
            f"median of last 4 successful runs: {ctx.median_last_4}s)\n"
            f"**All 9 metrics:** passed\n"
            f"**Hash:** matched last-green pin\n"
            f"**Last 8 elapsed:** {ctx.elapsed_history or []}\n"
            f"**Suspected:** {ctx.suspected}\n"
        )
    if mode == "canary-fail":
        names = ctx.failed_assertion_names or []
        return (
            f"**Canary run:** {ctx.canary_id}\n"
            f"**Failed assertions:** {ctx.failed_assertions or []} — "
            f"{', '.join(names) if names else '(names unavailable)'}\n"
            f"**Elapsed:** {ctx.elapsed_seconds}s\n"
            f"**Hash match:** {'yes' if ctx.hash_match else 'no'}\n"
            f"**First failed assertion body:** {ctx.first_failed_assertion_body}\n"
            f"**Dashboard:** status=fail; streak reset to 0\n"
            f"**Next action:** debug the first failed assertion; "
            f"do NOT re-run canary until root cause identified\n"
        )
    if mode == "canary-silent":
        return (
            f"**Last successful canary run:** {ctx.last_pass_timestamp} "
            f"({ctx.days_since_last_pass} days ago)\n"
            f"**Weekly cron present:** "
            f"{'yes' if ctx.weekly_cron_present else 'no'} — from `ops /loop list`\n"
            f"**Conditional hook registered:** "
            f"{'yes' if ctx.conditional_hook_registered else 'no'} — "
            f"from `.claude/settings.json` read\n"
            f"**Suspected:** cron died / hook unregistered / ops lane stopped\n"
            f"**Next action:** operator verifies ops lane alive; "
            f"restart `/loop 7d /run-canary` if cron absent\n"
        )
    if mode == "canary-schema-drift":
        return (
            f"**Canary run:** {ctx.canary_id}\n"
            f"**All 9 metrics:** passed\n"
            f"**Hash mismatch:** observed {ctx.observed_hash} vs "
            f"pinned {ctx.pinned_hash}\n"
            f"**New event types observed:** {ctx.set_diff_added or []}\n"
            f"**Missing event types:** {ctx.set_diff_missing or []}\n"
            f"**Next action:** quarterly `/canary-review` required within "
            f"14 days to either (a) re-pin hash if change is intentional, "
            f"or (b) file follow-up H.0/H.1 issue if unintended schema drift\n"
        )
    raise ValueError(f"Unknown failure mode: {mode!r}")


def render_title(mode: FailureMode, ctx: IssueContext) -> str:
    """Render the issue title (keeps ``canary_id:`` scannable in search)."""
    first = (
        (ctx.failed_assertion_names or [None])[0]
        if ctx.failed_assertion_names
        else "failed assertion"
    )
    filled = _TITLE_TEMPLATE[mode].format(
        canary_id=ctx.canary_id,
        first_failed_assertion=first,
        days_since_last_pass=ctx.days_since_last_pass,
    )
    # Always include canary_id: prefix so §6.4 dedup search matches.
    return f"{filled} | canary_id:{ctx.canary_id}"


# --------------------------------------------------------------------------- #
# gh wrappers — idempotent per shape §6.4
# --------------------------------------------------------------------------- #


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``gh`` with captured stdout; raises on non-zero exit."""
    if shutil.which("gh") is None:
        raise RuntimeError("`gh` CLI not on PATH; cannot file canary issue")
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )


def find_existing_issue(label: str, canary_id: str) -> int | None:
    """Return issue number if an open issue with (label, canary_id) exists."""
    try:
        result = _run_gh(
            [
                "issue",
                "list",
                "--label",
                label,
                "--state",
                "open",
                "--search",
                f"canary_id:{canary_id}",
                "--json",
                "number",
            ]
        )
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        logger.warning("gh issue list failed; assuming no existing issue: %s", exc)
        return None
    try:
        rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not rows:
        return None
    return rows[0].get("number")


def create_or_comment(
    *,
    mode: FailureMode,
    title: str,
    body: str,
    canary_id: str,
) -> tuple[str, int | str]:
    """Create a new issue or comment on the existing dedup hit.

    Returns ``(action, identifier)`` where action is ``"created"`` or
    ``"commented"`` and identifier is the issue URL or number.
    """
    existing = find_existing_issue(mode, canary_id)
    if existing is not None:
        _run_gh(["issue", "comment", str(existing), "--body", body])
        return "commented", existing

    result = _run_gh(
        [
            "issue",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--label",
            mode,
        ]
    )
    url = result.stdout.strip().splitlines()[-1] if result.stdout else ""
    return "created", url


def push_ops_alert(*, mode: FailureMode, title: str, issue_ref: str) -> bool:
    """Best-effort ops-alert push (shape §6.3).

    Returns True if push succeeded; False if the ops alert primitive
    (Primitive E) is not yet wired or the push failed. False does NOT
    fail the parent call — the shape treats alert push as complementary
    to issue filing, not a prerequisite.
    """
    if not _ALERT_PUSH[mode]:
        return True  # no push required for this mode
    try:
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "alert",
                "push",
                "--priority",
                _PRIORITY[mode],
                "--title",
                title,
                "--body",
                issue_ref,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning(
            "ops alert push failed (Primitive E may not be wired yet): %s", exc
        )
        return False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="file_canary_issue",
        description="File a GitHub issue for a canary failure mode.",
    )
    p.add_argument(
        "--mode",
        choices=VALID_MODES,
        required=True,
        help="Failure mode (drives label, priority, body template).",
    )
    p.add_argument("--canary-id", default="unknown")
    p.add_argument("--elapsed-seconds", type=float)
    p.add_argument("--threshold-2x-median", type=float)
    p.add_argument("--median-last-4", type=float)
    p.add_argument("--elapsed-history", help="Comma-separated floats.")
    p.add_argument("--suspected", default="(auto-triage pending)")
    p.add_argument(
        "--failed-assertions",
        help="Comma-separated 1-based assertion indices (canary-fail).",
    )
    p.add_argument(
        "--failed-assertion-names",
        help="Pipe-separated human names matching --failed-assertions.",
    )
    p.add_argument("--first-failed-assertion-body", default="(details unavailable)")
    p.add_argument(
        "--hash-match",
        choices=("yes", "no"),
        help="Whether hash matched last-green pin (canary-fail).",
    )
    p.add_argument("--last-pass", default="never")
    p.add_argument("--days-since-last-pass", type=int)
    p.add_argument("--weekly-cron-present", choices=("yes", "no"))
    p.add_argument("--conditional-hook-registered", choices=("yes", "no"))
    p.add_argument("--observed-hash", default="(unknown)")
    p.add_argument("--pinned-hash", default="(unknown)")
    p.add_argument("--set-diff-added", help="Comma-separated event types.")
    p.add_argument("--set-diff-missing", help="Comma-separated event types.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Render body + title to stdout; do not call gh.",
    )
    return p


def _csv_ints(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _csv_floats(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _csv_strs(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def _build_ctx(args: argparse.Namespace) -> IssueContext:
    names_raw = args.failed_assertion_names
    names = [n.strip() for n in names_raw.split("|")] if names_raw else None
    return IssueContext(
        canary_id=args.canary_id,
        elapsed_seconds=args.elapsed_seconds,
        threshold_2x_median=args.threshold_2x_median,
        median_last_4=args.median_last_4,
        elapsed_history=_csv_floats(args.elapsed_history),
        suspected=args.suspected,
        failed_assertions=_csv_ints(args.failed_assertions),
        failed_assertion_names=names,
        first_failed_assertion_body=args.first_failed_assertion_body,
        hash_match=(args.hash_match == "yes") if args.hash_match else None,
        last_pass_timestamp=args.last_pass,
        days_since_last_pass=args.days_since_last_pass,
        weekly_cron_present=(args.weekly_cron_present == "yes")
        if args.weekly_cron_present
        else None,
        conditional_hook_registered=(args.conditional_hook_registered == "yes")
        if args.conditional_hook_registered
        else None,
        observed_hash=args.observed_hash,
        pinned_hash=args.pinned_hash,
        set_diff_added=_csv_strs(args.set_diff_added),
        set_diff_missing=_csv_strs(args.set_diff_missing),
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _build_arg_parser().parse_args(argv)

    ctx = _build_ctx(args)
    try:
        body = render_body(args.mode, ctx)
        title = render_title(args.mode, ctx)
    except (KeyError, ValueError) as exc:
        logger.error("Failed to render issue body: %s", exc)
        return 2

    if args.dry_run:
        print(
            f"# DRY RUN — mode={args.mode} label={args.mode} priority={_PRIORITY[args.mode]}"
        )
        print(f"# TITLE: {title}")
        print("# BODY:")
        print(body)
        return 0

    try:
        action, ref = create_or_comment(
            mode=args.mode,
            title=title,
            body=body,
            canary_id=args.canary_id,
        )
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        logger.error("Failed to file/comment canary issue: %s", exc)
        return 1

    logger.info("Canary issue %s: %s", action, ref)
    push_ops_alert(mode=args.mode, title=title, issue_ref=str(ref))
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI entrypoint
    sys.exit(main())
