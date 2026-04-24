"""Tests for the ``/read-ops-brief`` skill content (Fixes #2806).

This is a content/structure test — the skill is a prompt file consumed
by the orchestrator lane, not executable code. We assert the
invariants the skill depends on:

1. The routing table covers every known finding category.
2. The ack-after-routing ordering contract is stated explicitly.
3. The skill points the operator at the CLI command, not ad-hoc shell
   fallbacks (``gh pr list``, ``ops.py inbox``, ``ops.py task list``).
4. The schema version the skill tolerates matches the builder's
   ``SCHEMA_VERSION``.
5. The orchestrator prompt-policy clause mandates cron fires begin
   with ``/read-ops-brief``.
"""

from __future__ import annotations

import re
from pathlib import Path

from bid_euchre.ops import orchestrator_brief as ob

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DOC = REPO_ROOT / ".claude" / "skills" / "read-ops-brief" / "SKILL.md"
POLICY_DOC = REPO_ROOT / ".claude" / "rules" / "prompt_policy" / "orchestrator.md"
SCHEMA_DOC = REPO_ROOT / "docs" / "01_core" / "orchestrator_brief_schema.md"


# ---------------------------------------------------------------------------
# Routing-table coverage
# ---------------------------------------------------------------------------


class TestSkillRoutingTable:
    def test_skill_file_exists(self) -> None:
        assert SKILL_DOC.is_file()

    def test_skill_has_frontmatter_with_description(self) -> None:
        body = SKILL_DOC.read_text()
        assert body.startswith("---\n")
        # name: and description: both present in frontmatter.
        frontmatter_end = body.find("\n---\n", 4)
        assert frontmatter_end > 0
        fm = body[4:frontmatter_end]
        assert re.search(r"^name:\s*read-ops-brief\s*$", fm, re.MULTILINE)
        assert re.search(r"^description:\s*.+$", fm, re.MULTILINE)

    def test_skill_routes_every_known_category(self) -> None:
        body = SKILL_DOC.read_text()
        for category in ob.KNOWN_FINDING_CATEGORIES:
            assert (
                f"`{category}`" in body
            ), f"Skill routing table missing category {category!r}"

    def test_skill_documents_unknown_category_fallback(self) -> None:
        body = SKILL_DOC.read_text()
        # The "(other)" row routes unknown categories to the JSONL sink.
        assert "(other)" in body
        assert "orchestrator_brief_unknown_categories.jsonl" in body


# ---------------------------------------------------------------------------
# Ack-after-routing ordering contract
# ---------------------------------------------------------------------------


class TestAckAfterRoutingContract:
    def test_skill_states_ack_after_routing(self) -> None:
        body = SKILL_DOC.read_text().lower()
        # The ordering contract: all findings routed BEFORE any alert
        # is acked. Accept any phrasing that signals both ordering and
        # the word "ack".
        assert "ack" in body
        assert (
            "after routing" in body
            or "ack-after-routing" in body
            or "after all findings" in body.replace("\n", " ")
        ), "Skill must state ack-after-routing ordering contract."

    def test_skill_warns_against_bulk_ack_of_unrouted_alerts(
        self,
    ) -> None:
        body = SKILL_DOC.read_text()
        # Bulk-acking a batch that contains unrouted alerts reintroduces
        # the #2806 bug.
        assert "--bulk" in body or "bulk" in body.lower()


# ---------------------------------------------------------------------------
# Single-bridge invariant: no fallback to ad-hoc shell
# ---------------------------------------------------------------------------


class TestSingleBridgeInvariant:
    def test_skill_invokes_canonical_cli(self) -> None:
        body = SKILL_DOC.read_text()
        assert "ops.py" in body
        assert "orchestrator brief" in body
        # The --json flag is a top-level flag that must precede the
        # subcommand. Verify the skill uses the correct ordering.
        assert re.search(r"ops\.py\s+--json\s+orchestrator\s+brief", body)

    def test_skill_instructs_no_shell_fallback(self) -> None:
        body = SKILL_DOC.read_text()
        # The whole point of #2806 is to replace ad-hoc shell scans. The
        # skill must call that out explicitly so future revisions don't
        # re-add the fallback.
        low = body.lower()
        assert "do not" in low or "do **not**" in low
        # At least one of the forbidden fallbacks must be named.
        forbidden_mentions = sum(
            phrase in body
            for phrase in ("gh pr list", "ops.py inbox", "ops.py task list")
        )
        assert forbidden_mentions >= 1, (
            "Skill should name at least one forbidden shell fallback to "
            "prevent future regressions."
        )


# ---------------------------------------------------------------------------
# Schema version pin
# ---------------------------------------------------------------------------


class TestSchemaVersionPin:
    def test_skill_mentions_schema_version(self) -> None:
        body = SKILL_DOC.read_text()
        # The skill must assert on schema_version to detect breaking
        # changes.
        assert "schema_version" in body
        # And should reference the current version value.
        assert str(ob.SCHEMA_VERSION) in body


# ---------------------------------------------------------------------------
# Orchestrator prompt-policy clause
# ---------------------------------------------------------------------------


class TestOrchestratorPolicyClause:
    def test_policy_file_bumped_version(self) -> None:
        body = POLICY_DOC.read_text()
        # v1.1 bump for the deterministic ops-signal-bridge clause.
        assert re.search(r"`orchestrator-v1\.1`", body)

    def test_policy_references_read_ops_brief(self) -> None:
        body = POLICY_DOC.read_text()
        assert "/read-ops-brief" in body

    def test_policy_mentions_2806(self) -> None:
        body = POLICY_DOC.read_text()
        assert "#2806" in body

    def test_policy_retains_registry_schema_sections(self) -> None:
        body = POLICY_DOC.read_text()
        # The B.3 registry lint expects these four header sections.
        for section in (
            "## Version",
            "## Trigger",
            "## Expected effect",
            "## Rollback",
        ):
            assert section in body, f"Policy file missing required section: {section}"


# ---------------------------------------------------------------------------
# Schema doc cross-reference
# ---------------------------------------------------------------------------


class TestSchemaDocCrossReferences:
    def test_schema_doc_exists_and_versions(self) -> None:
        assert SCHEMA_DOC.is_file()
        body = SCHEMA_DOC.read_text()
        # Schema version field visible.
        assert '"schema_version": 1' in body
        # Routing table header.
        assert "Finding category → action handler" in body

    def test_schema_doc_lists_every_known_category(self) -> None:
        body = SCHEMA_DOC.read_text()
        for category in ob.KNOWN_FINDING_CATEGORIES:
            assert f"`{category}`" in body

    def test_schema_doc_documents_invariants(self) -> None:
        body = SCHEMA_DOC.read_text()
        # Empty-state stability, no partial failure, determinism,
        # single-shell-call — all four invariants must be documented.
        for phrase in (
            "Schema stability",
            "No partial failure",
            "Deterministic",
            "Single shell call",
        ):
            assert phrase in body, f"Schema doc missing invariant: {phrase}"
