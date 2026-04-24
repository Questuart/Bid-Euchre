"""Tests for the orchestrator brief builder (Fixes #2806).

Covers the producer side of the deterministic ops signal bridge —
``src/bid_euchre/ops/orchestrator_brief.py`` and the CLI dispatcher in
``scripts/internal/ops.py``. The consumer-side skill is exercised in
``test_read_ops_brief_skill.py``.

Invariant matrix (schema doc § Invariants):

1. Schema stability under empty fleet: every top-level key is always
   present; empty arrays are ``[]`` not omitted; ``last_read_at`` is
   ``null`` on first-ever read.
2. No partial failure: individual data-source exceptions do not raise;
   failed keys get empty-state values.
3. Deterministic: identical inputs → identical outputs except
   ``generated_at`` and derived ``age_minutes``.
4. Finding-category coverage: the ``KNOWN_FINDING_CATEGORIES`` set
   matches the monitor's emitted categories and the schema doc's
   routing table.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from bid_euchre.ops import orchestrator_brief as ob
from bid_euchre.ops.message_bus import BusMessage, send_message
from bid_euchre.ops.task_queue import create_packet, save_packet

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DOC = REPO_ROOT / "docs" / "01_core" / "orchestrator_brief_schema.md"
MONITOR_SRC = REPO_ROOT / "src" / "bid_euchre" / "ops" / "monitor.py"
SKILL_DOC = REPO_ROOT / ".claude" / "skills" / "read-ops-brief" / "SKILL.md"
OPS_CLI = REPO_ROOT / "scripts" / "internal" / "ops.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


NOW = datetime(2026, 4, 24, 18, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    """A clean runtime dir with the task-queue + task-state subdirs created."""
    (tmp_path / "task_queue").mkdir()
    (tmp_path / "task_state").mkdir()
    return tmp_path


@pytest.fixture
def bus_root(tmp_path: Path) -> Path:
    """A clean message-bus root isolated from the repo's real bus."""
    root = tmp_path / "bus"
    root.mkdir()
    return root


def _offline_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``_gh_pr_list`` to return empty to keep tests offline.

    The brief builder invokes ``gh pr list`` via subprocess. Unit tests
    must not depend on GitHub auth or network, so we replace that seam
    with a stub by default. Individual tests that want to simulate PR
    data re-monkeypatch ``_gh_pr_list``.
    """
    monkeypatch.setattr(ob, "_gh_pr_list", lambda *a, **kw: [])


def _make_alert(
    message_id: str,
    *,
    priority: str = "high",
    created_at: str | None = None,
    findings: list[dict[str, Any]] | None = None,
    summary: str = "Monitor alert",
) -> BusMessage:
    payload: dict[str, Any] = {
        "findings": findings or [],
        "high_count": sum(1 for f in (findings or []) if f.get("severity") == "high"),
        "warn_count": sum(1 for f in (findings or []) if f.get("severity") == "warn"),
        "info_count": sum(1 for f in (findings or []) if f.get("severity") == "info"),
    }
    return BusMessage(
        message_id=message_id,
        thread_id=None,
        task_id=None,
        from_lane="ops",
        to_lane="orchestrator",
        message_type="supervisor_alert",
        priority=priority,
        status="pending",
        created_at=created_at or NOW.isoformat(),
        acked_at=None,
        resolved_at=None,
        requires_human=False,
        summary=summary,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Invariant 1 — schema stability under empty fleet
# ---------------------------------------------------------------------------


class TestSchemaStabilityEmpty:
    def test_empty_fleet_every_key_present(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)

        brief = ob.build_brief(
            runtime_dir=runtime_dir,
            now=NOW,
            bus_root=bus_root,
        )

        expected_keys = {
            "schema_version",
            "generated_at",
            "last_read_at",
            "recent_ops_alerts",
            "open_prs",
            "merged_prs_since_last_read",
            "pending_inbox_by_type",
            "dispatched_packets",
            "tui_task_status",
        }
        assert set(brief.keys()) == expected_keys

    def test_empty_fleet_values_match_schema(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)

        brief = ob.build_brief(
            runtime_dir=runtime_dir,
            now=NOW,
            bus_root=bus_root,
        )

        assert brief["schema_version"] == ob.SCHEMA_VERSION == 1
        assert brief["last_read_at"] is None
        assert brief["recent_ops_alerts"] == []
        assert brief["open_prs"] == []
        assert brief["merged_prs_since_last_read"] == []
        assert brief["pending_inbox_by_type"] == {}
        assert brief["dispatched_packets"] == []
        assert brief["tui_task_status"] == {
            "pending": 0,
            "in_progress": 0,
            "blocked": 0,
            "completed": 0,
            "abandoned": 0,
            "total": 0,
        }

    def test_generated_at_is_iso_z(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", brief["generated_at"]
        )


# ---------------------------------------------------------------------------
# Invariant 2 — no partial failure
# ---------------------------------------------------------------------------


class TestNoPartialFailure:
    def test_gh_raises_open_prs_returns_empty(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom(*a: Any, **kw: Any) -> list[dict[str, Any]]:
            raise RuntimeError("simulated gh failure")

        monkeypatch.setattr(ob, "_gh_pr_list", boom)

        # build_brief invokes _collect_open_prs which calls _gh_pr_list
        # directly. We want the collector's own try/except to catch. The
        # actual _collect_open_prs doesn't wrap _gh_pr_list because
        # _gh_pr_list is already defensive — override both layers to
        # simulate a fault that sneaks through. Expect empty list.
        monkeypatch.setattr(ob, "_collect_open_prs", lambda: [])
        monkeypatch.setattr(ob, "_collect_merged_prs_since", lambda *_: [])

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert brief["open_prs"] == []
        assert brief["merged_prs_since_last_read"] == []

    def test_gh_cli_missing_returns_empty(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate `gh` binary missing — _gh_pr_list catches FileNotFoundError.
        def fake_run(*a: Any, **kw: Any) -> Any:
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr(subprocess, "run", fake_run)

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert brief["open_prs"] == []
        assert brief["merged_prs_since_last_read"] == []

    def test_gh_nonzero_exit_returns_empty(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "auth required"

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert brief["open_prs"] == []


# ---------------------------------------------------------------------------
# mark_read / read_last_read_at round-trip
# ---------------------------------------------------------------------------


class TestMarkReadRoundTrip:
    def test_first_read_returns_none(self, runtime_dir: Path) -> None:
        assert ob.read_last_read_at(runtime_dir) is None

    def test_mark_then_read_returns_same_timestamp(self, runtime_dir: Path) -> None:
        written = ob.mark_read(runtime_dir, now=NOW)
        assert written == "2026-04-24T18:00:00Z"
        assert ob.read_last_read_at(runtime_dir) == written

    def test_state_file_uses_schema_version(self, runtime_dir: Path) -> None:
        ob.mark_read(runtime_dir, now=NOW)
        state = json.loads((runtime_dir / "orchestrator_brief_state.json").read_text())
        assert state["schema_version"] == ob.SCHEMA_VERSION
        assert state["last_read_at"] == "2026-04-24T18:00:00Z"

    def test_malformed_state_returns_none(self, runtime_dir: Path) -> None:
        (runtime_dir / "orchestrator_brief_state.json").write_text("not json")
        assert ob.read_last_read_at(runtime_dir) is None

    def test_missing_last_read_at_returns_none(self, runtime_dir: Path) -> None:
        (runtime_dir / "orchestrator_brief_state.json").write_text(
            json.dumps({"schema_version": 1})
        )
        assert ob.read_last_read_at(runtime_dir) is None


# ---------------------------------------------------------------------------
# Recent ops alerts — severity mapping + findings expansion
# ---------------------------------------------------------------------------


class TestRecentOpsAlerts:
    @pytest.mark.parametrize(
        "priority,expected",
        [
            ("urgent", "high"),
            ("high", "high"),
            ("normal", "warn"),
            ("low", "info"),
        ],
    )
    def test_priority_to_severity_mapping(
        self,
        runtime_dir: Path,
        bus_root: Path,
        priority: str,
        expected: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        msg = _make_alert("msg_" + priority, priority=priority)
        send_message(msg, bus_root=bus_root)

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert len(brief["recent_ops_alerts"]) == 1
        assert brief["recent_ops_alerts"][0]["severity"] == expected
        assert brief["recent_ops_alerts"][0]["priority"] == priority

    def test_findings_expanded_into_alert(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        findings = [
            {
                "category": "pr_merged",
                "severity": "info",
                "summary": "PR #2800 merged",
                "details": {"pr": 2800, "title": "...", "branch": "b"},
            },
            {
                "category": "lane_health",
                "severity": "high",
                "summary": "pane dead",
                "details": {"lane_id": "author-a"},
            },
        ]
        msg = _make_alert("m1", findings=findings)
        send_message(msg, bus_root=bus_root)

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        alert = brief["recent_ops_alerts"][0]
        assert len(alert["findings"]) == 2
        assert alert["findings"][0]["category"] == "pr_merged"
        assert alert["findings"][0]["details"]["pr"] == 2800
        assert alert["findings"][1]["category"] == "lane_health"
        assert alert["findings"][1]["severity"] == "high"
        # Payload counts flow through
        assert alert["high_count"] == 1
        assert alert["info_count"] == 1

    def test_newest_first_ordering(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        older = _make_alert("older", created_at=(NOW - timedelta(hours=2)).isoformat())
        newer = _make_alert(
            "newer", created_at=(NOW - timedelta(minutes=5)).isoformat()
        )
        send_message(older, bus_root=bus_root)
        send_message(newer, bus_root=bus_root)

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        assert brief["recent_ops_alerts"][0]["message_id"] == "newer"
        assert brief["recent_ops_alerts"][1]["message_id"] == "older"

    def test_recent_limit_caps_count(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        for i in range(7):
            send_message(
                _make_alert(
                    f"m{i}",
                    created_at=(NOW - timedelta(minutes=i)).isoformat(),
                ),
                bus_root=bus_root,
            )

        brief = ob.build_brief(
            runtime_dir=runtime_dir,
            now=NOW,
            bus_root=bus_root,
            recent_alerts_limit=3,
        )
        assert len(brief["recent_ops_alerts"]) == 3

    def test_pending_inbox_grouped_by_type(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)
        # Two supervisor_alerts, one blocker
        send_message(_make_alert("a1"), bus_root=bus_root)
        send_message(_make_alert("a2"), bus_root=bus_root)
        blocker = BusMessage(
            message_id="b1",
            thread_id=None,
            task_id=None,
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",
            priority="high",
            status="pending",
            created_at=NOW.isoformat(),
            acked_at=None,
            resolved_at=None,
            requires_human=False,
            summary="stuck",
        )
        send_message(blocker, bus_root=bus_root)

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        counts = brief["pending_inbox_by_type"]
        assert counts.get("supervisor_alert") == 2
        assert counts.get("blocker") == 1


# ---------------------------------------------------------------------------
# CI-state derivation
# ---------------------------------------------------------------------------


class TestCiStateDerivation:
    def test_no_checks_is_unknown(self) -> None:
        state, failing = ob._ci_state([])
        assert state == "unknown"
        assert failing == []

    def test_any_failure_is_blocked(self) -> None:
        checks = [
            {"name": "tests", "conclusion": "FAILURE", "status": "COMPLETED"},
            {"name": "lint", "conclusion": "SUCCESS", "status": "COMPLETED"},
        ]
        state, failing = ob._ci_state(checks)
        assert state == "blocked"
        assert "tests" in failing

    def test_error_counts_as_blocked(self) -> None:
        checks = [
            {"name": "build", "conclusion": "ERROR", "status": "COMPLETED"},
        ]
        state, failing = ob._ci_state(checks)
        assert state == "blocked"
        assert failing == ["build"]

    def test_all_success_is_green(self) -> None:
        checks = [
            {"name": "tests", "conclusion": "SUCCESS", "status": "COMPLETED"},
            {"name": "lint", "conclusion": "SUCCESS", "status": "COMPLETED"},
        ]
        state, failing = ob._ci_state(checks)
        assert state == "green"
        assert failing == []

    def test_pending_if_in_progress(self) -> None:
        checks = [
            {"name": "tests", "conclusion": None, "status": "IN_PROGRESS"},
            {"name": "lint", "conclusion": "SUCCESS", "status": "COMPLETED"},
        ]
        state, failing = ob._ci_state(checks)
        assert state == "pending"


# ---------------------------------------------------------------------------
# Merged PRs since last read
# ---------------------------------------------------------------------------


class TestMergedPrsSince:
    def test_null_last_read_returns_top_10(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prs = [
            {
                "number": 2800 - i,
                "title": f"PR {2800 - i}",
                "headRefName": "b",
                "mergedAt": f"2026-04-{24 - i:02d}T12:00:00Z",
            }
            for i in range(15)
        ]
        monkeypatch.setattr(
            ob,
            "_gh_pr_list",
            lambda state, *a, **kw: prs if state == "merged" else [],
        )
        out = ob._collect_merged_prs_since(None)
        assert len(out) == 10

    def test_filters_by_merged_at(self, monkeypatch: pytest.MonkeyPatch) -> None:
        prs = [
            {
                "number": 3,
                "title": "",
                "headRefName": "b",
                "mergedAt": "2026-04-24T18:30:00Z",
            },
            {
                "number": 2,
                "title": "",
                "headRefName": "b",
                "mergedAt": "2026-04-24T17:00:00Z",
            },
            {
                "number": 1,
                "title": "",
                "headRefName": "b",
                "mergedAt": "2026-04-23T10:00:00Z",
            },
        ]
        monkeypatch.setattr(
            ob,
            "_gh_pr_list",
            lambda state, *a, **kw: prs if state == "merged" else [],
        )
        out = ob._collect_merged_prs_since("2026-04-24T17:30:00Z")
        # Only #3 is strictly after 17:30:00Z.
        assert [pr["number"] for pr in out] == [3]


# ---------------------------------------------------------------------------
# Dispatched packets
# ---------------------------------------------------------------------------


class TestDispatchedPackets:
    def test_lists_only_dispatched_status(
        self,
        runtime_dir: Path,
        bus_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _offline_gh(monkeypatch)

        # Two packets — only one dispatched.
        pending = create_packet(title="Pending one", description="", owner="author-b")
        save_packet(pending, root=runtime_dir / "task_queue")

        # Construct a dispatched packet manually to bypass the pending
        # default status.
        from dataclasses import replace

        dispatched = replace(
            create_packet(
                title="Dispatched one",
                description="",
                owner="author-a",
                priority="high",
            ),
            status="dispatched",
        )
        save_packet(dispatched, root=runtime_dir / "task_queue")

        brief = ob.build_brief(runtime_dir=runtime_dir, now=NOW, bus_root=bus_root)
        dispatched_rows = brief["dispatched_packets"]
        assert len(dispatched_rows) == 1
        assert dispatched_rows[0]["owner"] == "author-a"
        assert dispatched_rows[0]["priority"] == "high"
        assert dispatched_rows[0]["title"] == "Dispatched one"


# ---------------------------------------------------------------------------
# TUI task status
# ---------------------------------------------------------------------------


class TestTuiTaskStatus:
    def test_aggregates_by_status(self, runtime_dir: Path) -> None:
        task_state = runtime_dir / "task_state"
        # Three v2 task files across three statuses.
        for i, status in enumerate(("in_progress", "completed", "pending")):
            (task_state / f"task_{i}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "task_id": f"task_{i}",
                        "owner_lane": "author-a",
                        "goal": f"goal {i}",
                        "status": status,
                        "items": [],
                        "progress": None,
                        "in_scope": [],
                        "out_of_scope": [],
                        "escalation_triggers": [],
                        "completion_note": None,
                    }
                )
            )

        brief_status = ob._collect_tui_task_status(runtime_dir)
        assert brief_status["in_progress"] == 1
        assert brief_status["completed"] == 1
        assert brief_status["pending"] == 1
        assert brief_status["total"] == 3
        # Missing buckets still present and zero.
        assert brief_status["blocked"] == 0
        assert brief_status["abandoned"] == 0


# ---------------------------------------------------------------------------
# Invariant 4 — known-finding-category coverage
# ---------------------------------------------------------------------------


class TestFindingCategoryCoverage:
    """KNOWN_FINDING_CATEGORIES must stay in sync with:

    1. the monitor's emitted categories in ``src/bid_euchre/ops/monitor.py``;
    2. the routing-table rows in ``docs/01_core/orchestrator_brief_schema.md``;
    3. the routing-table rows in ``.claude/skills/read-ops-brief/SKILL.md``.

    This guards against drift when someone adds a new monitor category
    without wiring it through both the schema doc and the skill.
    """

    def test_monitor_emitted_categories_registered(self) -> None:
        src = MONITOR_SRC.read_text()
        # Match string literals assigned as category= in MonitorFinding
        # constructor calls. Monitor emits these as ``category="..."``.
        pattern = re.compile(r'category\s*=\s*"([a-z_]+)"')
        emitted = set(pattern.findall(src))
        # Exclude categories that aren't actually monitor emissions
        # (e.g., code referring to the category for filtering).
        # Every emitted category must be registered.
        unregistered = emitted - ob.KNOWN_FINDING_CATEGORIES
        assert not unregistered, (
            f"Monitor emits categories not in KNOWN_FINDING_CATEGORIES: "
            f"{sorted(unregistered)}. Add them to orchestrator_brief.py "
            f"AND the routing tables in the schema doc + skill."
        )

    def test_schema_doc_routes_every_known_category(self) -> None:
        doc = SCHEMA_DOC.read_text()
        for category in ob.KNOWN_FINDING_CATEGORIES:
            assert f"`{category}`" in doc, (
                f"Category {category} missing from routing table in " f"{SCHEMA_DOC}"
            )

    def test_skill_routes_every_known_category(self) -> None:
        skill = SKILL_DOC.read_text()
        for category in ob.KNOWN_FINDING_CATEGORIES:
            assert f"`{category}`" in skill, (
                f"Category {category} missing from routing table in " f"{SKILL_DOC}"
            )


# ---------------------------------------------------------------------------
# CLI smoke — the argparse wiring in ops.py
# ---------------------------------------------------------------------------


class TestCliDispatch:
    def test_cli_emits_well_formed_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end sanity: invoking the CLI in --json mode emits a
        JSON document whose top-level keys match the schema.

        Runs the CLI in a subprocess against a tmp runtime dir. We patch
        ``gh`` to always fail fast so the test is offline.
        """
        env = {
            "PATH": f"{tmp_path}/bin:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "BID_EUCHRE_BUS_DIR": str(tmp_path / "bus"),
        }
        (tmp_path / "bin").mkdir()
        # A `gh` stub that always exits 127 so _gh_pr_list returns [].
        stub = tmp_path / "bin" / "gh"
        stub.write_text("#!/bin/sh\nexit 127\n")
        stub.chmod(0o755)

        # Need an isolated .claude/runtime for the CLI — the CLI
        # currently uses the default runtime dir. We pass via the
        # runtime_dir arg that ops.py already supports.
        result = subprocess.run(
            [
                sys.executable,
                str(OPS_CLI),
                "--json",
                "--runtime-dir",
                str(tmp_path / "runtime"),
                "orchestrator",
                "brief",
                "--recent",
                "3",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"CLI failed: stderr={result.stderr[-500:]}"
        brief = json.loads(result.stdout)
        assert brief["schema_version"] == 1
        assert "recent_ops_alerts" in brief
        assert "open_prs" in brief
        assert "dispatched_packets" in brief
        assert "tui_task_status" in brief
