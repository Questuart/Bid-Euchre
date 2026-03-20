"""Tests for curated memory (ops/memory.py)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from bid_euchre.ops.memory import (
    LOCK_FILE,
    VALID_CATEGORIES,
    MemoryEntry,
    MemoryStore,
    _locked_update,
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

    def test_load_skips_malformed_entries(
        self, memory_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A single bad entry must not discard the entire store (#950)."""
        import json as _json

        good_entry = {
            "entry_id": "aaa",
            "category": "repo_fact",
            "key": "k1",
            "value": "v1",
            "source_file": "f.md",
            "added_by": "test",
            "added_at": "2026-03-18T10:00:00+00:00",
        }
        bad_entry = {
            # missing entry_id -- will raise KeyError
            "category": "repo_fact",
            "key": "k2",
            "value": "v2",
            "source_file": "f.md",
            "added_by": "test",
            "added_at": "2026-03-18T11:00:00+00:00",
        }
        good_entry_2 = {
            "entry_id": "ccc",
            "category": "preference",
            "key": "k3",
            "value": "v3",
            "source_file": "f.md",
            "added_by": "test",
            "added_at": "2026-03-18T12:00:00+00:00",
        }
        data = {
            "version": 1,
            "last_updated": "2026-03-18T12:00:00+00:00",
            "entries": [good_entry, bad_entry, good_entry_2],
        }
        (memory_dir / "memory.json").write_text(_json.dumps(data))

        with caplog.at_level(logging.WARNING, logger="ops.memory"):
            store = load_memory(memory_dir)

        # Two good entries survive; the bad one is skipped
        assert len(store.entries) == 2
        assert store.entries[0].entry_id == "aaa"
        assert store.entries[1].entry_id == "ccc"
        # Top-level metadata preserved
        assert store.version == 1
        assert store.last_updated == "2026-03-18T12:00:00+00:00"
        # Warning was logged
        assert any(
            "malformed memory entry" in r.message.lower() for r in caplog.records
        )

    def test_save_atomic_no_temp_files(self, memory_dir: Path) -> None:
        """After save_memory(), no .tmp files should remain (#951)."""
        store = MemoryStore(
            entries=[
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
        )
        save_memory(store, memory_dir)

        # No leftover temp files
        tmp_files = list(memory_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"

        # The written file is valid JSON
        import json as _json

        data = _json.loads((memory_dir / "memory.json").read_text())
        assert data["version"] == 1
        assert len(data["entries"]) == 1

    def test_save_no_double_close_on_replace_failure(self, memory_dir: Path) -> None:
        """os.close(fd) must not be called twice when os.replace() fails (#971)."""
        import os
        from unittest.mock import patch

        store = MemoryStore(
            entries=[
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
        )

        close_calls: list[int] = []
        original_close = os.close

        def tracking_close(fd: int) -> None:
            close_calls.append(fd)
            original_close(fd)

        with (
            patch("bid_euchre.ops.memory.os.replace", side_effect=OSError("disk full")),
            patch("bid_euchre.ops.memory.os.close", side_effect=tracking_close),
        ):
            with pytest.raises(OSError, match="disk full"):
                save_memory(store, memory_dir)

        # The fd should be closed exactly once, not twice
        assert (
            len(close_calls) == 1
        ), f"os.close() called {len(close_calls)} times, expected 1"

    def test_save_replace_failure_cleans_up(self, memory_dir: Path) -> None:
        """If os.replace() fails, the temp file must be cleaned up and the original error preserved (#951)."""
        from unittest.mock import patch

        store = MemoryStore(
            entries=[
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
        )

        with patch(
            "bid_euchre.ops.memory.os.replace", side_effect=OSError("cross-device link")
        ):
            with pytest.raises(OSError, match="cross-device link"):
                save_memory(store, memory_dir)

        # No .tmp files should remain
        tmp_files = list(memory_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leaked temp files: {tmp_files}"


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


class TestCorruptFileBackup:
    """Tests for corrupt file backup on JSONDecodeError (#950 residual)."""

    def test_load_backs_up_corrupt_file(self, memory_dir: Path) -> None:
        """Corrupt JSON is renamed to .corrupt.* and empty store returned."""
        corrupt_content = "not valid json {{{"
        (memory_dir / "memory.json").write_text(corrupt_content)

        store = load_memory(memory_dir)

        # Returns empty store
        assert store.entries == []

        # Original file removed
        assert not (memory_dir / "memory.json").exists()

        # Backup file exists with original content
        backups = list(memory_dir.glob("memory.corrupt.*"))
        assert len(backups) == 1
        assert backups[0].read_text() == corrupt_content

    def test_load_corrupt_backup_logs_warning(
        self, memory_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Corrupt file backup logs a warning with the backup filename."""
        (memory_dir / "memory.json").write_text("{invalid")

        with caplog.at_level(logging.WARNING, logger="ops.memory"):
            load_memory(memory_dir)

        assert any("backed up to" in r.message.lower() for r in caplog.records)

    def test_load_corrupt_backup_failure_still_returns_empty(
        self, memory_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If backup rename fails, still return empty store (don't crash)."""
        (memory_dir / "memory.json").write_text("corrupt!")

        # Make the directory read-only so rename fails
        memory_dir.chmod(0o555)
        try:
            with caplog.at_level(logging.WARNING, logger="ops.memory"):
                store = load_memory(memory_dir)
            assert store.entries == []
            assert any("failed to backup" in r.message.lower() for r in caplog.records)
        finally:
            memory_dir.chmod(0o755)

    def test_load_structural_error_no_backup(self, memory_dir: Path) -> None:
        """KeyError/TypeError from bad structure does NOT trigger backup."""
        import json as _json

        # Valid JSON but totally wrong structure (list instead of dict)
        # This will hit the TypeError/AttributeError path
        (memory_dir / "memory.json").write_text(_json.dumps({"entries": "not-a-list"}))

        store = load_memory(memory_dir)

        # Returns empty store (from_dict handles this gracefully)
        assert isinstance(store, MemoryStore)

        # Original file is NOT backed up (still exists)
        assert (memory_dir / "memory.json").exists()
        assert list(memory_dir.glob("memory.corrupt.*")) == []


class TestLockedUpdate:
    """Tests for _locked_update context manager (#1002)."""

    def test_locked_update_basic(self, memory_dir: Path) -> None:
        """_locked_update loads, allows mutation, and saves."""
        # Pre-populate
        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="v1",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)

        # Mutate inside lock
        with _locked_update(memory_dir) as s:
            s.entries.append(
                MemoryEntry(
                    entry_id="bbb",
                    category="preference",
                    key="k2",
                    value="v2",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T11:00:00+00:00",
                )
            )

        # Verify persisted
        reloaded = load_memory(memory_dir)
        assert len(reloaded.entries) == 2
        assert {e.entry_id for e in reloaded.entries} == {"aaa", "bbb"}

    def test_locked_update_creates_lock_file(self, memory_dir: Path) -> None:
        """Lock file is created in memory_dir."""
        with _locked_update(memory_dir) as _s:
            assert (memory_dir / LOCK_FILE).exists()

    def test_locked_update_exception_does_not_save(self, memory_dir: Path) -> None:
        """If caller raises inside the context, changes are NOT persisted."""
        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="original",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)

        with pytest.raises(RuntimeError, match="abort"):
            with _locked_update(memory_dir) as s:
                s.entries[0] = MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="MODIFIED",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
                raise RuntimeError("abort")

        # Original value preserved
        reloaded = load_memory(memory_dir)
        assert reloaded.entries[0].value == "original"

    def test_concurrent_add_entry_no_lost_writes(
        self, memory_dir: Path, source_file: Path
    ) -> None:
        """Two threads calling add_entry concurrently must not lose writes."""
        import threading

        barrier = threading.Barrier(2, timeout=5)
        errors: list[Exception] = []

        def _add(key: str) -> None:
            try:
                barrier.wait()  # Force both threads to contend on the lock
                add_entry(
                    memory_dir,
                    category="repo_fact",
                    key=key,
                    value=f"value-{key}",
                    source_file=str(source_file),
                    added_by="test",
                )
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=_add, args=("concurrent_a",))
        t2 = threading.Thread(target=_add, args=("concurrent_b",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

        # Both entries must be present — no lost writes
        entries = list_entries(memory_dir)
        keys = {e.key for e in entries}
        assert "concurrent_a" in keys, f"Lost write for concurrent_a. Keys: {keys}"
        assert "concurrent_b" in keys, f"Lost write for concurrent_b. Keys: {keys}"

    def test_locked_update_no_op_skips_save(self, memory_dir: Path) -> None:
        """_locked_update must skip save_memory when store is unmodified."""
        from unittest.mock import patch as _patch

        # Pre-populate with an entry
        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="v1",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)
        original_updated = load_memory(memory_dir).last_updated

        # Open _locked_update but make no changes
        with _patch("bid_euchre.ops.memory.save_memory") as mock_save:
            with _locked_update(memory_dir) as _s:
                pass  # No mutations

            mock_save.assert_not_called()

        # last_updated should be unchanged
        reloaded = load_memory(memory_dir)
        assert reloaded.last_updated == original_updated

    def test_locked_update_mutation_saves(self, memory_dir: Path) -> None:
        """_locked_update must call save_memory when store is modified."""
        from unittest.mock import patch as _patch

        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="v1",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)

        # Mutate inside the context
        with _patch("bid_euchre.ops.memory.save_memory") as mock_save:
            with _locked_update(memory_dir) as s:
                s.entries.append(
                    MemoryEntry(
                        entry_id="bbb",
                        category="preference",
                        key="k2",
                        value="v2",
                        source_file="f.md",
                        added_by="test",
                        added_at="2026-03-18T11:00:00+00:00",
                    )
                )

            mock_save.assert_called_once()

    def test_remove_nonexistent_no_timestamp_change(self, memory_dir: Path) -> None:
        """Removing a nonexistent entry must not update last_updated."""
        store = MemoryStore(
            entries=[
                MemoryEntry(
                    entry_id="aaa",
                    category="repo_fact",
                    key="k1",
                    value="v1",
                    source_file="f.md",
                    added_by="test",
                    added_at="2026-03-18T10:00:00+00:00",
                )
            ]
        )
        save_memory(store, memory_dir)
        original_updated = load_memory(memory_dir).last_updated

        # Remove nonexistent — should be a no-op
        removed = remove_entry(memory_dir, "nonexistent_id")
        assert not removed

        # last_updated must be unchanged (no save occurred)
        reloaded = load_memory(memory_dir)
        assert reloaded.last_updated == original_updated


class TestSafetyScanIntegration:
    """Tests for context-safety scan integration in add_entry()."""

    def test_safe_content_persists(self, memory_dir: Path, source_file: Path) -> None:
        """Safe content is accepted when safety_scan=True (default)."""
        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="safe_fact",
            value="Main branch is protected",
            source_file=str(source_file),
            added_by="test",
        )
        assert entry.key == "safe_fact"
        assert "_safety_warnings" not in entry.tags

    def test_unsafe_content_rejected(self, memory_dir: Path, source_file: Path) -> None:
        """Unsafe content (secret) is rejected by default."""
        with pytest.raises(ValueError, match="safety scan"):
            add_entry(
                memory_dir,
                category="repo_fact",
                key="bad_secret",
                value="password = 'super_secret_password_123'",
                source_file=str(source_file),
                added_by="test",
            )

        # Entry should NOT be persisted
        entries = list_entries(memory_dir)
        assert not any(e.key == "bad_secret" for e in entries)

    def test_unsafe_content_bypass(self, memory_dir: Path, source_file: Path) -> None:
        """Unsafe content is accepted when safety_scan=False."""
        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="bypass_test",
            value="password = 'super_secret_password_123'",
            source_file=str(source_file),
            added_by="test",
            safety_scan=False,
        )
        assert entry.key == "bypass_test"

    def test_warned_content_persists_with_tag(
        self, memory_dir: Path, source_file: Path
    ) -> None:
        """Warned content (oversized) is persisted with _safety_warnings tag."""
        from bid_euchre.ops.context_safety import DEFAULT_MAX_CONTENT_BYTES

        entry = add_entry(
            memory_dir,
            category="repo_fact",
            key="big_fact",
            value="x" * (DEFAULT_MAX_CONTENT_BYTES + 1),
            source_file=str(source_file),
            added_by="test",
        )
        assert "_safety_warnings" in entry.tags

    def test_warned_content_logs_warning(
        self,
        memory_dir: Path,
        source_file: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warned content logs a warning message."""
        from bid_euchre.ops.context_safety import DEFAULT_MAX_CONTENT_BYTES

        with caplog.at_level(logging.WARNING, logger="ops.memory"):
            add_entry(
                memory_dir,
                category="repo_fact",
                key="big_fact_log",
                value="x" * (DEFAULT_MAX_CONTENT_BYTES + 1),
                source_file=str(source_file),
                added_by="test",
            )

        assert any("safety scan warnings" in r.message.lower() for r in caplog.records)
