"""Unit tests for ``scripts/internal/file_canary_issue.py`` (Primitive H.0).

Shape reference: ``plans/steward_platform/8_primitive_H/shaping.md`` §6.

Covered behaviors:

- Body renderers match §6.2 templates verbatim (field appearance +
  human-readable phrasing).
- Title always carries ``canary_id:`` so §6.4 dedup search matches.
- Routing matrix (§6.1) maps each of the 4 failure modes to the
  right priority + alert-push behavior.
- Dedup logic (§6.4): existing open issue with (label, canary_id)
  triggers ``issue comment`` rather than a second ``issue create``.
- ``--dry-run`` exits 0 and emits body to stdout without any ``gh``
  subprocess.
- Ops alert push (§6.3) is best-effort — a failed push does not
  propagate to the caller's exit status.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import scripts.internal.file_canary_issue as fci

# --------------------------------------------------------------------------- #
# Body templates — §6.2 verbatim field presence
# --------------------------------------------------------------------------- #


class TestRenderBody:
    def test_canary_slow_has_required_fields(self) -> None:
        ctx = fci.IssueContext(
            canary_id="dogfood-v1-2026-04-24-0645-cron",
            elapsed_seconds=12.5,
            threshold_2x_median=8.0,
            median_last_4=4.0,
            elapsed_history=[3.0, 4.0, 4.5, 5.0],
            suspected="review_driver.py CI wait long",
        )
        body = fci.render_body("canary-slow", ctx)
        assert "**Canary run:** dogfood-v1-2026-04-24-0645-cron" in body
        assert "**Elapsed:** 12.5s" in body
        assert "threshold: 8.0s" in body
        assert "median of last 4 successful runs: 4.0s" in body
        assert "**All 9 metrics:** passed" in body
        assert "**Suspected:** review_driver.py CI wait long" in body

    def test_canary_fail_has_required_fields(self) -> None:
        ctx = fci.IssueContext(
            canary_id="dogfood-v1-test",
            elapsed_seconds=100.0,
            failed_assertions=[3, 7],
            failed_assertion_names=["PR merged", "dashboard renders"],
            hash_match=True,
            first_failed_assertion_body="CI red on commit abc123",
        )
        body = fci.render_body("canary-fail", ctx)
        assert "**Failed assertions:** [3, 7]" in body
        assert "PR merged" in body
        assert "dashboard renders" in body
        assert "**Hash match:** yes" in body
        assert "streak reset to 0" in body
        assert "do NOT re-run canary" in body

    def test_canary_silent_has_required_fields(self) -> None:
        ctx = fci.IssueContext(
            last_pass_timestamp="2026-04-01T00:00:00Z",
            days_since_last_pass=14,
            weekly_cron_present=False,
            conditional_hook_registered=True,
        )
        body = fci.render_body("canary-silent", ctx)
        assert "2026-04-01T00:00:00Z" in body
        assert "(14 days ago)" in body
        assert "**Weekly cron present:** no" in body
        assert "**Conditional hook registered:** yes" in body
        assert "restart `/loop 7d /run-canary`" in body

    def test_canary_schema_drift_has_required_fields(self) -> None:
        ctx = fci.IssueContext(
            canary_id="dogfood-v1-test",
            observed_hash="sha256:aaa",
            pinned_hash="sha256:bbb",
            set_diff_added=["new_event"],
            set_diff_missing=[],
        )
        body = fci.render_body("canary-schema-drift", ctx)
        assert "**All 9 metrics:** passed" in body
        assert "sha256:aaa" in body
        assert "sha256:bbb" in body
        assert "['new_event']" in body
        assert "quarterly `/canary-review`" in body
        assert "within 14 days" in body

    def test_unknown_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            fci.render_body("bogus", fci.IssueContext())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Title — dedup search anchor
# --------------------------------------------------------------------------- #


class TestRenderTitle:
    def test_title_carries_canary_id_suffix(self) -> None:
        ctx = fci.IssueContext(canary_id="dogfood-v1-2026-04-24-0645-cron")
        title = fci.render_title("canary-slow", ctx)
        assert "canary_id:dogfood-v1-2026-04-24-0645-cron" in title

    def test_title_format_per_mode(self) -> None:
        for mode in fci.VALID_MODES:
            ctx = fci.IssueContext(
                canary_id="cid",
                days_since_last_pass=7,
                failed_assertion_names=["metric-3 failed"],
            )
            title = fci.render_title(mode, ctx)
            assert title.startswith(mode + ":")


# --------------------------------------------------------------------------- #
# Routing matrix — §6.1
# --------------------------------------------------------------------------- #


class TestRoutingMatrix:
    def test_priority_mapping_is_spec_exact(self) -> None:
        assert fci._PRIORITY == {
            "canary-slow": "normal",
            "canary-fail": "high",
            "canary-silent": "high",
            "canary-schema-drift": "normal",
        }

    def test_alert_push_mapping_is_spec_exact(self) -> None:
        assert fci._ALERT_PUSH == {
            "canary-slow": False,
            "canary-fail": True,
            "canary-silent": True,
            "canary-schema-drift": False,
        }


# --------------------------------------------------------------------------- #
# Dry-run — no gh subprocess
# --------------------------------------------------------------------------- #


class TestDryRun:
    def test_dry_run_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = fci.main(
            [
                "--dry-run",
                "--mode",
                "canary-fail",
                "--canary-id",
                "dogfood-v1-test",
                "--failed-assertions",
                "3,7",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "DRY RUN" in captured.out
        assert "canary-fail" in captured.out
        assert "dogfood-v1-test" in captured.out

    def test_dry_run_does_not_invoke_gh(self) -> None:
        """Confirms gh is not called under --dry-run."""
        with patch.object(fci, "_run_gh") as mock_gh:
            fci.main(
                [
                    "--dry-run",
                    "--mode",
                    "canary-silent",
                    "--last-pass",
                    "2026-04-01T00:00:00Z",
                    "--days-since-last-pass",
                    "14",
                ]
            )
            mock_gh.assert_not_called()


# --------------------------------------------------------------------------- #
# Dedup — §6.4
# --------------------------------------------------------------------------- #


class TestDedup:
    def test_no_existing_issue_creates_new(self) -> None:
        with patch.object(fci, "_run_gh") as mock_gh:
            # First call (list) returns empty; second (create) returns URL.
            mock_gh.side_effect = [
                MagicMock(stdout="[]"),
                MagicMock(stdout="https://github.com/org/repo/issues/99\n"),
            ]
            action, ref = fci.create_or_comment(
                mode="canary-fail",
                title="canary-fail: foo | canary_id:cid-42",
                body="body",
                canary_id="cid-42",
            )
        assert action == "created"
        assert "99" in str(ref)
        # 2 gh calls: list + create
        assert mock_gh.call_count == 2
        create_args = mock_gh.call_args_list[1].args[0]
        assert create_args[0] == "issue"
        assert create_args[1] == "create"
        assert "--label" in create_args
        assert "canary-fail" in create_args

    def test_existing_issue_posts_comment(self) -> None:
        with patch.object(fci, "_run_gh") as mock_gh:
            mock_gh.side_effect = [
                MagicMock(stdout=json.dumps([{"number": 42}])),
                MagicMock(stdout=""),
            ]
            action, ref = fci.create_or_comment(
                mode="canary-silent",
                title="canary-silent: foo",
                body="body",
                canary_id="cid-42",
            )
        assert action == "commented"
        assert ref == 42
        comment_args = mock_gh.call_args_list[1].args[0]
        assert comment_args[0] == "issue"
        assert comment_args[1] == "comment"
        assert "42" in comment_args

    def test_gh_list_failure_treats_as_no_existing(self) -> None:
        """Best-effort: if gh list fails, proceed to create (no silent spam)."""
        import subprocess

        with patch.object(fci, "_run_gh") as mock_gh:
            mock_gh.side_effect = [
                subprocess.CalledProcessError(1, "gh", stderr="network"),
                MagicMock(stdout="https://github.com/org/repo/issues/1\n"),
            ]
            action, _ = fci.create_or_comment(
                mode="canary-fail",
                title="t",
                body="b",
                canary_id="cid",
            )
        assert action == "created"


# --------------------------------------------------------------------------- #
# Ops alert push — best-effort per §10.4 coordination note
# --------------------------------------------------------------------------- #


class TestOpsAlertPush:
    def test_canary_slow_skips_alert(self) -> None:
        """canary-slow has alert=False; push_ops_alert returns True without subprocess."""
        with patch("subprocess.run") as mock_run:
            ok = fci.push_ops_alert(mode="canary-slow", title="t", issue_ref="http://x")
        assert ok is True
        mock_run.assert_not_called()

    def test_canary_fail_pushes_alert(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok = fci.push_ops_alert(mode="canary-fail", title="t", issue_ref="http://x")
        assert ok is True
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "alert" in args and "push" in args
        assert "--priority" in args
        assert "high" in args

    def test_alert_push_failure_does_not_raise(self) -> None:
        """Primitive E coordination note: alert failure is best-effort."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ops.py", stderr="no alert primitive yet"
            )
            ok = fci.push_ops_alert(mode="canary-fail", title="t", issue_ref="http://x")
        assert ok is False  # returned, not raised
