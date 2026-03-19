"""Tests for curated memory (ops/memory.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.memory import (
    VALID_CATEGORIES,
    MemoryEntry,
    MemoryStore,
    add_entry,
    format_memory_json,
    format_memory_text,
    get_entry,
    list_entries,
    load_memory,
    remove_entry,
    save_memory,
    search_entries,
    validate_entry,
    validate_provenance,
)


@pytest.fixture()
def memory_dir(tmp_path: Path) -> Path:
    """Provide a temporary memory directory."""
    d = tmp_path / "curated_memory"
    d.mkdir()
    return d


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    """Provide a temporary source file for provenance."""
    f = tmp_path / "source.md"
    f.write_text("# Source document\n\nSome content.\n")
    return f


class TestLoadSave:
    """Tests for load_memory() and save_memory()."""

    def test_load_empty(self, memory_dir: Path) -> None:
        store = load_memory(memory_dir)
        assert store.entries == []
        assert store.version == 1

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        store = load_memory(tmp_path / "nonexistent")
        assert store.entries == []

    def test_save_and_load(self, memory_dir: Path) -> None:
        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="abc123",
                    category="repo_fact",
                    key="branch_policy",
                    value="main is protected",
                    source_file="CLAUDE.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)

        loaded = load_memory(memory_dir)
        assert len(loaded.entries) == 1
        assert loaded.entries[0].key == "branch_policy"
        assert loaded.last_updated is not None

    def test_load_malformed(self, memory_dir: Path) -> None:
        (memory_dir / "memory.json").write_text("not valid json")
        store = load_memory(memory_dir)
        assert store.entries == []

    def test_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        store = MemoryStore()
        save_memory(store, nested)
        assert (nested / "memory.json").exists()


class TestValidation:
    """Tests for validate_entry() and validate_provenance()."""

    def test_valid_entry(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file="CLAUDE.md",
            added_by="test",
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_entry(entry)
        assert result.valid
        assert result.errors == []

    def test_invalid_category(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="bogus_category",
            key="test",
            value="test value",
            source_file="CLAUDE.md",
            added_by="test",
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_entry(entry)
        assert not result.valid
        assert any("category" in e for e in result.errors)

    def test_missing_provenance(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file="",  # Empty — provenance missing
            added_by="",  # Empty — provenance missing
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_entry(entry)
        assert not result.valid
        assert any("source_file" in e for e in result.errors)
        assert any("added_by" in e for e in result.errors)

    def test_invalid_timestamp(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file="CLAUDE.md",
            added_by="test",
            added_at="not-a-timestamp",
        )
        result = validate_entry(entry)
        assert not result.valid
        assert any("added_at" in e for e in result.errors)

    def test_provenance_source_exists(self, source_file: Path) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file=str(source_file),
            added_by="test",
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_provenance(entry, check_source_exists=True)
        assert result.valid

    def test_provenance_source_missing(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file="/nonexistent/file.md",
            added_by="test",
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_provenance(entry, check_source_exists=True)
        assert not result.valid
        assert any("does not exist" in e for e in result.errors)

    def test_provenance_skip_source_check(self) -> None:
        entry = MemoryEntry(
            entry_id="abc",
            category="repo_fact",
            key="test",
            value="test value",
            source_file="/nonexistent/file.md",
            added_by="test",
            added_at="2026-03-18T10:00:00+00:00",
        )
        result = validate_provenance(entry, check_source_exists=False)
        assert result.valid

    def test_all_categories_valid(self) -> None:
        for cat in VALID_CATEGORIES:
            entry = MemoryEntry(
                entry_id="abc",
                category=cat,
                key="test",
                value="val",
                source_file="f.md",
                added_by="test",
                added_at="2026-03-18T10:00:00+00:00",
            )
            result = validate_entry(entry)
            assert result.valid, f"Category '{cat}' should be valid"


class TestCRUD:
    """Tests for add_entry, remove_entry, get_entry, list_entries."""

    def test_add_entry(self, memory_dir: Path, source_file: Path) -> None:
        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="branch_policy",
            value="main is protected",
            source_file=str(source_file),
            added_by="test",
        )
        assert entry.key == "branch_policy"
        assert entry.category == "repo_fact"
        assert entry.source_file == str(source_file)

    def test_add_entry_invalid_provenance(self, memory_dir: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            add_entry(
                memory_dir,
                category="repo_fact",
                key="test",
                value="test",
                source_file="/nonexistent/file.md",
                added_by="test",
                check_source_exists=True,
            )

    def test_add_entry_invalid_category(
        self, memory_dir: Path, source_file: Path
    ) -> None:
        with pytest.raises(ValueError, match="category"):
            add_entry(
                memory_dir,
                category="invalid_cat",
                key="test",
                value="test",
                source_file=str(source_file),
                added_by="test",
            )

    def test_add_supersedes_existing(self, memory_dir: Path, source_file: Path) -> None:
        entry1 = add_entry(
            memory_dir,
            category="repo_fact",
            key="branch_policy",
            value="v1",
            source_file=str(source_file),
            added_by="test",
        )
        entry2 = add_entry(
            memory_dir,
            category="repo_fact",
            key="branch_policy",
            value="v2",
            source_file=str(source_file),
            added_by="test",
        )
        # New entry must have a distinct ID from the old one
        assert entry2.entry_id != entry1.entry_id
        # Supersedes must point to the prior entry's distinct ID
        assert entry2.supersedes == entry1.entry_id
        assert entry2.value == "v2"

        # Only one entry with this key should remain
        entries = list_entries(memory_dir, category="repo_fact")
        matching = [e for e in entries if e.key == "branch_policy"]
        assert len(matching) == 1
        assert matching[0].value == "v2"

    def test_remove_entry(self, memory_dir: Path, source_file: Path) -> None:
        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="test",
            value="test",
            source_file=str(source_file),
            added_by="test",
        )
        assert remove_entry(memory_dir, entry.entry_id)

        # Should be gone
        assert get_entry(memory_dir, entry.entry_id) is None

    def test_remove_nonexistent(self, memory_dir: Path) -> None:
        assert not remove_entry(memory_dir, "nonexistent_id")

    def test_get_entry(self, memory_dir: Path, source_file: Path) -> None:
        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="test",
            value="test_value",
            source_file=str(source_file),
            added_by="test",
        )
        found = get_entry(memory_dir, entry.entry_id)
        assert found is not None
        assert found.value == "test_value"

    def test_get_nonexistent(self, memory_dir: Path) -> None:
        assert get_entry(memory_dir, "nonexistent") is None

    def test_list_entries_all(self, memory_dir: Path, source_file: Path) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="fact1",
            value="v1",
            source_file=str(source_file),
            added_by="test",
        )
        add_entry(
            memory_dir,
            category="preference",
            key="pref1",
            value="v2",
            source_file=str(source_file),
            added_by="test",
        )

        entries = list_entries(memory_dir)
        assert len(entries) == 2

    def test_list_entries_by_category(
        self, memory_dir: Path, source_file: Path
    ) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="fact1",
            value="v1",
            source_file=str(source_file),
            added_by="test",
        )
        add_entry(
            memory_dir,
            category="preference",
            key="pref1",
            value="v2",
            source_file=str(source_file),
            added_by="test",
        )

        facts = list_entries(memory_dir, category="repo_fact")
        assert len(facts) == 1
        assert facts[0].key == "fact1"

    def test_list_entries_by_tag(self, memory_dir: Path, source_file: Path) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="fact1",
            value="v1",
            source_file=str(source_file),
            added_by="test",
            tags=["important"],
        )
        add_entry(
            memory_dir,
            category="repo_fact",
            key="fact2",
            value="v2",
            source_file=str(source_file),
            added_by="test",
            tags=["trivial"],
        )

        important = list_entries(memory_dir, tag="important")
        assert len(important) == 1
        assert important[0].key == "fact1"


class TestSearch:
    """Tests for search_entries()."""

    def test_search_by_key(self, memory_dir: Path, source_file: Path) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="branch_policy",
            value="main is protected",
            source_file=str(source_file),
            added_by="test",
        )
        results = search_entries(memory_dir, "branch")
        assert len(results) == 1

    def test_search_by_value(self, memory_dir: Path, source_file: Path) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="test",
            value="SQLite is the preferred database",
            source_file=str(source_file),
            added_by="test",
        )
        results = search_entries(memory_dir, "sqlite")
        assert len(results) == 1

    def test_search_case_insensitive(self, memory_dir: Path, source_file: Path) -> None:
        add_entry(
            memory_dir,
            category="repo_fact",
            key="test",
            value="FTS5 Full Text Search",
            source_file=str(source_file),
            added_by="test",
        )
        results = search_entries(memory_dir, "fts5")
        assert len(results) == 1

    def test_search_no_matches(self, memory_dir: Path) -> None:
        results = search_entries(memory_dir, "nonexistent")
        assert results == []


class TestFormatting:
    """Tests for formatting helpers."""

    def test_format_json(self) -> None:
        entries = [
            MemoryEntry(
                entry_id="abc",
                category="repo_fact",
                key="test",
                value="val",
                source_file="f.md",
                added_by="test",
                added_at="2026-03-18T10:00:00+00:00",
            )
        ]
        data = format_memory_json(entries)
        assert len(data) == 1
        assert data[0]["key"] == "test"

    def test_format_text_empty(self) -> None:
        text = format_memory_text([])
        assert "no curated memory" in text.lower()

    def test_format_text_grouped(self) -> None:
        entries = [
            MemoryEntry(
                entry_id="a",
                category="repo_fact",
                key="k1",
                value="v1",
                source_file="f.md",
                added_by="test",
                added_at="2026-03-18T10:00:00+00:00",
            ),
            MemoryEntry(
                entry_id="b",
                category="preference",
                key="k2",
                value="v2",
                source_file="f.md",
                added_by="test",
                added_at="2026-03-18T11:00:00+00:00",
            ),
        ]
        text = format_memory_text(entries)
        assert "[repo_fact]" in text
        assert "[preference]" in text
