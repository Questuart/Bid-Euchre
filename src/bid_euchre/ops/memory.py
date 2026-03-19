"""Curated memory for stable operator facts.

Provides a small, explicit, provenance-backed memory store for:
- Stable repo facts (branch policies, tool versions, key paths)
- User preferences and workflow invariants
- Role instructions and approved operational shortcuts
- Lessons learned from past operational incidents

This is intentionally separate from:
- MEMORY.md (auto-memory, conversation-scoped)
- The audit index (large, searchable operational history)

Every entry has provenance fields: source_file, added_by, added_at.
No anonymous entries. Updates are explicit, not automatic.

Storage: ``.claude/runtime/curated_memory/memory.json`` (gitignored)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.memory")

DEFAULT_MEMORY_DIR = Path(".claude/runtime/curated_memory")
MEMORY_FILE = "memory.json"

# Categories for organizing memory entries
VALID_CATEGORIES = frozenset(
    {
        "repo_fact",
        "preference",
        "workflow",
        "role_instruction",
        "lesson_learned",
        "operational_shortcut",
        "tool_config",
    }
)


@dataclass
class MemoryEntry:
    """A single curated memory entry with provenance."""

    entry_id: str
    category: str
    key: str
    value: str
    source_file: str  # Where this fact comes from
    added_by: str  # Who/what added this entry
    added_at: str  # ISO 8601 timestamp
    tags: list[str] = field(default_factory=list)
    supersedes: str | None = None  # entry_id this replaces

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Create from a dict."""
        return cls(
            entry_id=data["entry_id"],
            category=data["category"],
            key=data["key"],
            value=data["value"],
            source_file=data["source_file"],
            added_by=data["added_by"],
            added_at=data["added_at"],
            tags=data.get("tags", []),
            supersedes=data.get("supersedes"),
        )


@dataclass
class MemoryStore:
    """The full curated memory store."""

    entries: list[MemoryEntry] = field(default_factory=list)
    version: int = 1
    last_updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryStore:
        """Create from a dict.

        Malformed entries are skipped with a warning rather than failing
        the entire load (see #950).
        """
        entries: list[MemoryEntry] = []
        for raw in data.get("entries", []):
            try:
                entries.append(MemoryEntry.from_dict(raw))
            except (KeyError, TypeError) as e:
                logger.warning("Skipping malformed memory entry: %s", e)
        return cls(
            version=data.get("version", 1),
            last_updated=data.get("last_updated"),
            entries=entries,
        )


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id(key: str, category: str) -> str:
    """Generate a unique entry ID from key, category, and current time.

    Each call produces a distinct ID even for the same key+category,
    so that supersession chains have distinct IDs per version.

    A random nonce is included to prevent collisions when two calls
    occur within the same microsecond (e.g. concurrent agents).
    """
    import hashlib
    import os

    now = datetime.now(timezone.utc).isoformat()
    nonce = os.urandom(8).hex()
    raw = f"{category}:{key}:{now}:{nonce}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_memory_path(memory_dir: Path) -> Path:
    """Get the path to the memory JSON file."""
    return memory_dir / MEMORY_FILE


# ── Load / Save ──────────────────────────────────────────────────


def load_memory(memory_dir: Path) -> MemoryStore:
    """Load curated memory from disk.

    Returns empty MemoryStore if file doesn't exist or is malformed.
    """
    memory_path = _get_memory_path(memory_dir)
    if not memory_path.exists():
        return MemoryStore()

    try:
        data = json.loads(memory_path.read_text())
        return MemoryStore.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to load curated memory: %s", e)
        return MemoryStore()


def save_memory(store: MemoryStore, memory_dir: Path) -> None:
    """Save curated memory to disk atomically.

    Writes to a same-directory tempfile, fsyncs, then atomically replaces
    the target via ``os.replace()`` so a crash mid-write cannot leave a
    truncated file (see #951).
    """
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = _get_memory_path(memory_dir)
    store.last_updated = _now_iso()
    content = json.dumps(store.to_dict(), indent=2) + "\n"

    fd, tmp = tempfile.mkstemp(dir=str(memory_dir), suffix=".tmp")
    fd_open = True
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd_open = False
        os.replace(tmp, str(memory_path))
    except BaseException:
        if fd_open:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Validation ───────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of validating a memory entry."""

    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_entry(entry: MemoryEntry) -> ValidationResult:
    """Validate a memory entry for completeness and provenance.

    Required:
    - entry_id must be non-empty
    - category must be in VALID_CATEGORIES
    - key must be non-empty
    - value must be non-empty
    - source_file must be non-empty
    - added_by must be non-empty
    - added_at must be a valid ISO 8601 timestamp
    """
    errors: list[str] = []

    if not entry.entry_id:
        errors.append("entry_id is required")
    if entry.category not in VALID_CATEGORIES:
        errors.append(
            f"invalid category '{entry.category}', "
            f"must be one of: {sorted(VALID_CATEGORIES)}"
        )
    if not entry.key:
        errors.append("key is required")
    if not entry.value:
        errors.append("value is required")
    if not entry.source_file:
        errors.append("source_file is required (provenance)")
    if not entry.added_by:
        errors.append("added_by is required (provenance)")
    if not entry.added_at:
        errors.append("added_at is required")
    else:
        try:
            datetime.fromisoformat(entry.added_at)
        except ValueError:
            errors.append(f"added_at '{entry.added_at}' is not valid ISO 8601")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_provenance(
    entry: MemoryEntry, *, check_source_exists: bool = True
) -> ValidationResult:
    """Validate that an entry's source file exists and is traceable.

    Args:
        entry: The memory entry to validate.
        check_source_exists: If True, verify source_file exists on disk.
    """
    result = validate_entry(entry)
    if not result.valid:
        return result

    if check_source_exists and entry.source_file:
        source_path = Path(entry.source_file)
        if not source_path.exists():
            result.errors.append(f"source_file '{entry.source_file}' does not exist")
            result.valid = False

    return result


# ── CRUD Operations ──────────────────────────────────────────────


def add_entry(
    memory_dir: Path,
    category: str,
    key: str,
    value: str,
    source_file: str,
    added_by: str,
    *,
    tags: list[str] | None = None,
    check_source_exists: bool = True,
) -> MemoryEntry:
    """Add a new entry to curated memory.

    If an entry with the same key+category exists, it is superseded.

    Args:
        memory_dir: Directory for the memory store.
        category: Entry category (must be in VALID_CATEGORIES).
        key: Short identifier for the fact.
        value: The fact/preference/instruction text.
        source_file: File path that backs this entry.
        added_by: Who/what is adding this (e.g., "author-a", "user").
        tags: Optional tags for filtering.
        check_source_exists: If True, verify source_file exists.

    Returns:
        The created MemoryEntry.

    Raises:
        ValueError: If validation fails.
    """
    entry_id = _generate_id(key, category)
    entry = MemoryEntry(
        entry_id=entry_id,
        category=category,
        key=key,
        value=value,
        source_file=source_file,
        added_by=added_by,
        added_at=_now_iso(),
        tags=tags or [],
    )

    # Validate
    result = validate_provenance(entry, check_source_exists=check_source_exists)
    if not result.valid:
        raise ValueError(f"Invalid memory entry: {'; '.join(result.errors)}")

    # Load existing store
    store = load_memory(memory_dir)

    # Check for existing entry with same key+category
    existing = [e for e in store.entries if e.key == key and e.category == category]
    if existing:
        entry.supersedes = existing[0].entry_id
        store.entries = [
            e for e in store.entries if not (e.key == key and e.category == category)
        ]

    store.entries.append(entry)
    save_memory(store, memory_dir)

    return entry


def remove_entry(memory_dir: Path, entry_id: str) -> bool:
    """Remove an entry from curated memory by ID.

    Returns True if the entry was found and removed.
    """
    store = load_memory(memory_dir)
    original_len = len(store.entries)
    store.entries = [e for e in store.entries if e.entry_id != entry_id]

    if len(store.entries) < original_len:
        save_memory(store, memory_dir)
        return True
    return False


def get_entry(memory_dir: Path, entry_id: str) -> MemoryEntry | None:
    """Get a specific entry by ID."""
    store = load_memory(memory_dir)
    for entry in store.entries:
        if entry.entry_id == entry_id:
            return entry
    return None


def list_entries(
    memory_dir: Path,
    *,
    category: str | None = None,
    tag: str | None = None,
) -> list[MemoryEntry]:
    """List entries, optionally filtered by category or tag.

    Returns entries sorted by added_at (newest first).
    """
    store = load_memory(memory_dir)
    entries = store.entries

    if category:
        entries = [e for e in entries if e.category == category]
    if tag:
        entries = [e for e in entries if tag in e.tags]

    return sorted(entries, key=lambda e: e.added_at, reverse=True)


def search_entries(
    memory_dir: Path,
    search_text: str,
) -> list[MemoryEntry]:
    """Search entries by text (case-insensitive substring match).

    Searches key and value fields.
    """
    store = load_memory(memory_dir)
    lower = search_text.lower()
    return [
        e for e in store.entries if lower in e.key.lower() or lower in e.value.lower()
    ]


# ── Formatting ────────────────────────────────────────────────────


def format_memory_json(entries: list[MemoryEntry]) -> list[dict[str, Any]]:
    """Format memory entries as JSON-serializable list."""
    return [e.to_dict() for e in entries]


def format_memory_text(entries: list[MemoryEntry]) -> str:
    """Format memory entries as human-readable text."""
    if not entries:
        return "No curated memory entries."

    lines = [f"=== Curated Memory ({len(entries)} entries) ===", ""]

    # Group by category
    by_cat: dict[str, list[MemoryEntry]] = {}
    for e in entries:
        by_cat.setdefault(e.category, []).append(e)

    for cat in sorted(by_cat.keys()):
        lines.append(f"[{cat}]")
        for e in by_cat[cat]:
            tags_str = f" tags={e.tags}" if e.tags else ""
            lines.append(f"  {e.key}: {e.value}{tags_str}")
            lines.append(f"    source: {e.source_file} (by {e.added_by})")
        lines.append("")

    return "\n".join(lines)
