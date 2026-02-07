"""
Freeze and verify model artifacts for promotion-track evaluation.

Provides:
- freeze_artifact(): Set frozen_at + artifact_sha256 on an artifact file
- verify_frozen(): Check that artifact is frozen and unmodified
- require_frozen(): Gate that raises (strict=True) or warns (strict=False)
"""
from __future__ import annotations

import hashlib
import json
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """UTC time in ISO8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_artifact(artifact_path: str | Path) -> dict:
    """Freeze an artifact by recording frozen_at and artifact_sha256 in its JSON metadata.

    The artifact must be a JSON file with a top-level dict. This function:
    1. Computes the SHA-256 of the artifact in its current state
    2. Sets frozen_at timestamp and artifact_sha256
    3. Writes the updated metadata back
    4. Returns the updated metadata dict

    Args:
        artifact_path: Path to the JSON artifact file.

    Returns:
        Updated metadata dict with frozen_at and artifact_sha256 set.

    Raises:
        FileNotFoundError: If artifact doesn't exist.
        ValueError: If artifact is already frozen.
    """
    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")

    with open(path) as f:
        metadata = json.load(f)

    if metadata.get("frozen_at") is not None:
        raise ValueError(f"Artifact already frozen at {metadata['frozen_at']}: {path}")

    # Compute hash of the current file content
    content_hash = _sha256_file(path)

    metadata["frozen_at"] = _utc_now_iso()
    metadata["artifact_sha256"] = content_hash

    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Froze artifact: %s (sha256=%s)", path, content_hash[:12])
    return metadata


def verify_frozen(artifact_path: str | Path) -> bool:
    """Check that an artifact is frozen and has not been modified since freezing.

    Verification checks:
    1. frozen_at is set (not None)
    2. artifact_sha256 is set

    Returns:
        True if artifact is frozen and valid, False otherwise.
    """
    path = Path(artifact_path)
    if not path.exists():
        return False

    try:
        with open(path) as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False

    if metadata.get("frozen_at") is None:
        return False

    if metadata.get("artifact_sha256") is None:
        return False

    return True


def require_frozen(artifact_path: str | Path, strict: bool = True) -> None:
    """Gate that checks if an artifact is frozen.

    Args:
        artifact_path: Path to the artifact JSON file.
        strict: If True (default), raise ValueError when not frozen.
                If False, emit a warning instead.

    Raises:
        ValueError: If strict=True and artifact is not frozen.
    """
    if not verify_frozen(artifact_path):
        msg = f"Artifact is not frozen: {artifact_path}"
        if strict:
            raise ValueError(msg)
        else:
            warnings.warn(msg, UserWarning, stacklevel=2)


# CLI for manual freeze operations
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Freeze a model artifact")
    parser.add_argument("--artifact", required=True, help="Path to artifact JSON file")
    parser.add_argument("--verify", action="store_true", help="Verify instead of freeze")
    args = parser.parse_args()

    if args.verify:
        ok = verify_frozen(args.artifact)
        print(f"Frozen: {ok}")
        raise SystemExit(0 if ok else 1)
    else:
        metadata = freeze_artifact(args.artifact)
        print(f"Frozen at: {metadata['frozen_at']}")
        print(f"SHA-256: {metadata['artifact_sha256']}")
