"""Tests for the skill-promotion workflow.

Covers: propose, review, promote, disable, list, validation,
context-safety integration, malformed candidates, and edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.skill_promotion import (
    SkillCandidate,
    disable_skill,
    format_candidates_json,
    format_candidates_text,
    get_candidate,
    list_candidates,
    promote_skill,
    propose_skill,
    review_skill,
    validate_skill_name,
)

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def candidates_dir(tmp_path: Path) -> Path:
    d = tmp_path / "candidates"
    d.mkdir()
    return d


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir()
    return d


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    d = tmp_path / "events"
    d.mkdir()
    return d


def _propose(
    candidates_dir: Path,
    *,
    name: str = "my-skill",
    description: str = "A useful skill",
    content: str = "# My Skill\n\nDo the thing.\n",
    source_workflow: str = "repeated PR review workflow",
    proposed_by: str = "author-b",
) -> SkillCandidate:
    """Helper to propose a skill with sensible defaults."""
    return propose_skill(
        name=name,
        description=description,
        content=content,
        source_workflow=source_workflow,
        proposed_by=proposed_by,
        provenance={"prs": ["#100", "#101"], "sessions": ["2026-03-20"]},
        candidates_dir=candidates_dir,
    )


# ── Skill name validation ──────────────────────────────────────


class TestValidateSkillName:
    def test_valid_names(self) -> None:
        assert validate_skill_name("my-skill") == []
        assert validate_skill_name("ab") == []
        assert validate_skill_name("adding-strategies") == []
        assert validate_skill_name("review-plan") == []
        assert validate_skill_name("a1-b2-c3") == []

    def test_empty(self) -> None:
        errors = validate_skill_name("")
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_too_short(self) -> None:
        errors = validate_skill_name("a")
        assert any("at least" in e for e in errors)

    def test_too_long(self) -> None:
        errors = validate_skill_name("a" * 61)
        assert any("at most" in e for e in errors)

    def test_uppercase_rejected(self) -> None:
        errors = validate_skill_name("My-Skill")
        assert any("kebab-case" in e for e in errors)

    def test_underscores_rejected(self) -> None:
        errors = validate_skill_name("my_skill")
        assert any("kebab-case" in e for e in errors)

    def test_leading_digit_rejected(self) -> None:
        errors = validate_skill_name("1-skill")
        assert any("kebab-case" in e for e in errors)

    def test_trailing_hyphen_rejected(self) -> None:
        errors = validate_skill_name("my-skill-")
        assert any("kebab-case" in e for e in errors)

    def test_spaces_rejected(self) -> None:
        errors = validate_skill_name("my skill")
        assert any("kebab-case" in e for e in errors)


# ── Propose ─────────────────────────────────────────────────────


class TestPropose:
    def test_happy_path(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        assert c.status == "pending"
        assert c.name == "my-skill"
        assert c.proposed_by == "author-b"
        assert c.safety_scan_outcome in ("allow", "warn")
        assert c.safety_scan_hash  # non-empty
        assert c.candidate_id  # non-empty UUID

        # Persisted to disk
        path = candidates_dir / f"{c.candidate_id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["name"] == "my-skill"

    def test_propose_with_provenance(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        assert c.provenance == {
            "prs": ["#100", "#101"],
            "sessions": ["2026-03-20"],
        }

    def test_proposal_scan_reject_persists(self, candidates_dir: Path) -> None:
        """Even rejected-by-scan candidates are persisted for operator review."""
        # Content with a secret pattern
        c = propose_skill(
            name="bad-skill",
            description="Has secrets",
            content="API key: sk_live_abc123def456ghi789jkl0\n",
            source_workflow="test",
            proposed_by="author-b",
            candidates_dir=candidates_dir,
        )
        assert c.safety_scan_outcome == "reject"
        assert c.status == "pending"
        # Still persisted
        path = candidates_dir / f"{c.candidate_id}.json"
        assert path.exists()

    def test_invalid_name_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(ValueError, match="Invalid skill name"):
            propose_skill(
                name="Bad Name!",
                description="desc",
                content="content",
                source_workflow="test",
                proposed_by="author-b",
                candidates_dir=candidates_dir,
            )

    def test_empty_description_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(ValueError, match="description"):
            propose_skill(
                name="my-skill",
                description="",
                content="content",
                source_workflow="test",
                proposed_by="author-b",
                candidates_dir=candidates_dir,
            )

    def test_empty_content_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(ValueError, match="content"):
            propose_skill(
                name="my-skill",
                description="desc",
                content="  ",
                source_workflow="test",
                proposed_by="author-b",
                candidates_dir=candidates_dir,
            )

    def test_empty_source_workflow_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(ValueError, match="Source workflow"):
            propose_skill(
                name="my-skill",
                description="desc",
                content="content",
                source_workflow="",
                proposed_by="author-b",
                candidates_dir=candidates_dir,
            )

    def test_empty_proposed_by_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(ValueError, match="proposed_by"):
            propose_skill(
                name="my-skill",
                description="desc",
                content="content",
                source_workflow="test",
                proposed_by="  ",
                candidates_dir=candidates_dir,
            )


# ── Review ──────────────────────────────────────────────────────


class TestReview:
    def test_approve(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        reviewed = review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            review_notes="Looks good",
            candidates_dir=candidates_dir,
        )
        assert reviewed.status == "approved"
        assert reviewed.reviewed_by == "operator"
        assert reviewed.review_notes == "Looks good"
        assert reviewed.reviewed_at is not None

    def test_reject(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        reviewed = review_skill(
            c.candidate_id,
            approve=False,
            reviewed_by="operator",
            review_notes="Not useful enough",
            candidates_dir=candidates_dir,
        )
        assert reviewed.status == "rejected"

    def test_review_nonexistent_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            review_skill(
                "nonexistent-id",
                approve=True,
                reviewed_by="operator",
                candidates_dir=candidates_dir,
            )

    def test_review_already_approved_raises(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        with pytest.raises(ValueError, match="not 'pending'"):
            review_skill(
                c.candidate_id,
                approve=False,
                reviewed_by="operator",
                candidates_dir=candidates_dir,
            )

    def test_review_already_rejected_raises(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=False,
            reviewed_by="reviewer",
            candidates_dir=candidates_dir,
        )
        with pytest.raises(ValueError, match="not 'pending'"):
            review_skill(
                c.candidate_id,
                approve=True,
                reviewed_by="reviewer",
                candidates_dir=candidates_dir,
            )

    def test_review_empty_reviewer_raises(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        with pytest.raises(ValueError, match="reviewed_by"):
            review_skill(
                c.candidate_id,
                approve=True,
                reviewed_by="  ",
                candidates_dir=candidates_dir,
            )


# ── Promote ─────────────────────────────────────────────────────


class TestPromote:
    def test_happy_path(
        self, candidates_dir: Path, skills_dir: Path, events_dir: Path
    ) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        promoted, skill_path = promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        assert promoted.status == "promoted"
        assert skill_path.exists()
        assert skill_path.name == "SKILL.md"
        assert skill_path.parent.name == "my-skill"

        # Verify SKILL.md content
        content = skill_path.read_text()
        assert "name: my-skill" in content
        assert "description: A useful skill" in content
        assert "candidate_id:" in content
        assert "proposed_by: author-b" in content
        assert "# My Skill" in content

    def test_promote_without_approval_raises(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        c = _propose(candidates_dir)
        with pytest.raises(ValueError, match="not 'approved'"):
            promote_skill(
                c.candidate_id,
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )

    def test_promote_rejected_candidate_raises(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=False,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        with pytest.raises(ValueError, match="not 'approved'"):
            promote_skill(
                c.candidate_id,
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )

    def test_promote_nonexistent_raises(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            promote_skill(
                "nonexistent-id",
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )

    def test_promote_name_collision_raises(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        # Pre-create a skill directory
        (skills_dir / "my-skill").mkdir()
        (skills_dir / "my-skill" / "SKILL.md").write_text("existing")

        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        with pytest.raises(ValueError, match="already exists"):
            promote_skill(
                c.candidate_id,
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )

    def test_promote_safety_reject_blocks(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        """If content fails safety scan at promotion time, promotion is blocked."""
        # Propose with safe content, then tamper it to be unsafe before promote
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )

        # Tamper the candidate content to include a secret
        path = candidates_dir / f"{c.candidate_id}.json"
        data = json.loads(path.read_text())
        data["content"] = "Secret: sk_live_abc123def456ghi789jkl0\n"
        path.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="Context-safety scan rejected"):
            promote_skill(
                c.candidate_id,
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )

        # Skill directory should NOT have been created
        assert not (skills_dir / "my-skill").exists()

    def test_promote_safety_warn_allowed(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        """Content with warnings is still promoted (warnings are non-blocking)."""
        # Use very long content (> 10KB) to trigger oversized_content warning
        long_content = "# Big Skill\n\n" + "x" * 11_000 + "\n"
        c = propose_skill(
            name="big-skill",
            description="A large skill",
            content=long_content,
            source_workflow="test",
            proposed_by="author-b",
            candidates_dir=candidates_dir,
        )
        assert c.safety_scan_outcome == "warn"

        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        promoted, skill_path = promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
        )
        assert promoted.status == "promoted"
        assert skill_path.exists()

    def test_promote_provenance_in_skill_md(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        _, skill_path = promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
        )
        content = skill_path.read_text()
        assert "prs:" in content
        assert "#100" in content
        assert "source_workflow:" in content


# ── Disable ─────────────────────────────────────────────────────


class TestDisable:
    def test_disable_promoted_skill(
        self, candidates_dir: Path, skills_dir: Path, events_dir: Path
    ) -> None:
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        _, skill_path = promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        assert skill_path.exists()

        disabled_path = disable_skill(
            "my-skill",
            reason="Discovered issue",
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        assert disabled_path.exists()
        assert disabled_path.name == "SKILL.md.disabled"
        assert not skill_path.exists()

    def test_disable_nonexistent_raises(self, skills_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            disable_skill("nonexistent-skill", skills_dir=skills_dir)

    def test_candidate_record_retained_after_disable(
        self, candidates_dir: Path, skills_dir: Path, events_dir: Path
    ) -> None:
        """Provenance is retained even after disabling a skill."""
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        disable_skill("my-skill", skills_dir=skills_dir, events_dir=events_dir)

        # Candidate record still exists
        record = get_candidate(c.candidate_id, candidates_dir=candidates_dir)
        assert record.status == "promoted"  # Record shows promotion history
        assert record.candidate_id == c.candidate_id


# ── List and get ────────────────────────────────────────────────


class TestListAndGet:
    def test_list_empty(self, candidates_dir: Path) -> None:
        result = list_candidates(candidates_dir=candidates_dir)
        assert result == []

    def test_list_nonexistent_dir(self, tmp_path: Path) -> None:
        result = list_candidates(candidates_dir=tmp_path / "nonexistent")
        assert result == []

    def test_list_all(self, candidates_dir: Path) -> None:
        _propose(candidates_dir, name="skill-one")
        _propose(candidates_dir, name="skill-two")
        result = list_candidates(candidates_dir=candidates_dir)
        assert len(result) == 2

    def test_list_filter_by_status(self, candidates_dir: Path) -> None:
        c1 = _propose(candidates_dir, name="skill-one")
        _propose(candidates_dir, name="skill-two")
        review_skill(
            c1.candidate_id,
            approve=True,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        pending = list_candidates(
            status_filter="pending", candidates_dir=candidates_dir
        )
        assert len(pending) == 1
        assert pending[0].name == "skill-two"

        approved = list_candidates(
            status_filter="approved", candidates_dir=candidates_dir
        )
        assert len(approved) == 1
        assert approved[0].name == "skill-one"

    def test_list_sorted_newest_first(self, candidates_dir: Path) -> None:
        _propose(candidates_dir, name="skill-one")
        c2 = _propose(candidates_dir, name="skill-two")
        result = list_candidates(candidates_dir=candidates_dir)
        # c2 was proposed after c1, so c2 is first
        assert result[0].name == c2.name

    def test_list_skips_malformed(self, candidates_dir: Path) -> None:
        _propose(candidates_dir, name="good-skill")
        # Write a malformed JSON file
        (candidates_dir / "bad.json").write_text("not json at all")
        result = list_candidates(candidates_dir=candidates_dir)
        assert len(result) == 1

    def test_get_candidate(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        loaded = get_candidate(c.candidate_id, candidates_dir=candidates_dir)
        assert loaded.name == c.name
        assert loaded.candidate_id == c.candidate_id

    def test_get_nonexistent_raises(self, candidates_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            get_candidate("nonexistent", candidates_dir=candidates_dir)


# ── SkillCandidate serialization ────────────────────────────────


class TestSkillCandidateContract:
    def test_round_trip(self) -> None:
        c = SkillCandidate(
            candidate_id="abc-123",
            name="test-skill",
            description="A test",
            content="# Test\n",
            source_workflow="test workflow",
            proposed_by="author-b",
            proposed_at="2026-03-20T00:00:00Z",
            provenance={"prs": ["#1"]},
        )
        d = c.to_dict()
        restored = SkillCandidate.from_dict(d)
        assert restored.name == c.name
        assert restored.candidate_id == c.candidate_id
        assert restored.provenance == c.provenance

    def test_from_dict_strips_unknown_keys(self) -> None:
        data = {
            "candidate_id": "abc-123",
            "name": "test-skill",
            "description": "A test",
            "content": "# Test\n",
            "source_workflow": "test workflow",
            "proposed_by": "author-b",
            "proposed_at": "2026-03-20T00:00:00Z",
            "provenance": {},
            "unknown_future_field": "should be ignored",
        }
        c = SkillCandidate.from_dict(data)
        assert c.name == "test-skill"
        assert not hasattr(c, "unknown_future_field")


# ── Full lifecycle ──────────────────────────────────────────────


class TestFullLifecycle:
    def test_propose_review_promote_disable(
        self, candidates_dir: Path, skills_dir: Path, events_dir: Path
    ) -> None:
        """End-to-end happy path: propose → approve → promote → disable."""
        # 1. Propose
        c = _propose(candidates_dir)
        assert c.status == "pending"

        # 2. Approve
        reviewed = review_skill(
            c.candidate_id,
            approve=True,
            reviewed_by="operator",
            review_notes="Ship it",
            candidates_dir=candidates_dir,
        )
        assert reviewed.status == "approved"

        # 3. Promote
        promoted, skill_path = promote_skill(
            c.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        assert promoted.status == "promoted"
        assert skill_path.exists()
        assert (skills_dir / "my-skill" / "SKILL.md").exists()

        # 4. Disable
        disabled = disable_skill(
            "my-skill",
            reason="Testing rollback",
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
        assert disabled.exists()
        assert not (skills_dir / "my-skill" / "SKILL.md").exists()

    def test_reject_prevents_promotion(
        self, candidates_dir: Path, skills_dir: Path
    ) -> None:
        """Rejected candidates cannot be promoted."""
        c = _propose(candidates_dir)
        review_skill(
            c.candidate_id,
            approve=False,
            reviewed_by="operator",
            candidates_dir=candidates_dir,
        )
        with pytest.raises(ValueError, match="not 'approved'"):
            promote_skill(
                c.candidate_id,
                candidates_dir=candidates_dir,
                skills_dir=skills_dir,
            )


# ── Formatting ──────────────────────────────────────────────────


class TestFormatting:
    def test_text_empty(self) -> None:
        assert "No skill candidates" in format_candidates_text([])

    def test_text_with_candidates(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        text = format_candidates_text([c])
        assert "PENDING" in text
        assert "my-skill" in text
        assert "author-b" in text

    def test_json_output(self, candidates_dir: Path) -> None:
        c = _propose(candidates_dir)
        result = format_candidates_json([c])
        assert len(result) == 1
        assert result[0]["name"] == "my-skill"
        assert result[0]["status"] == "pending"
