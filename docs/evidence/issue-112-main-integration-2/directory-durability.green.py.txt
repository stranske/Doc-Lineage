"""Private local artifact writes and exclusive durable publication."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path


def sync_directory(directory: Path) -> None:
    """Persist directory entry changes before reporting successful publication."""
    if not hasattr(os, "O_DIRECTORY"):
        warnings.warn(
            "O_DIRECTORY unavailable: directory durability is unsupported on this platform",
            RuntimeWarning,
            stacklevel=2,
        )
        return
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_exclusive(path: Path, payload: bytes, *, prefix: str) -> None:
    """Link fully written, synced bytes into place without overwriting a winner.

    A directory-sync failure is reported even though the complete final file may
    already exist. Callers must not interpret the exception as a successful commit.
    """
    descriptor, temporary = tempfile.mkstemp(prefix=prefix, dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            if hasattr(os, "fchmod"):
                os.fchmod(output.fileno(), 0o600)
            else:
                _chmod_fallback(Path(temporary))
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink()
    sync_directory(path.parent)


def write_private(path: Path, payload: bytes) -> None:
    """Restrict new and existing artifacts before writing sensitive bytes."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        if hasattr(os, "fchmod"):
            os.fchmod(output.fileno(), 0o600)
        else:
            _chmod_fallback(path)
        output.truncate(0)
        output.write(payload)


def _chmod_fallback(path: Path) -> None:
    """Use the available path API without promising unverified platform ACLs."""
    warnings.warn(
        "fchmod unavailable: using path chmod; owner-only privacy is unverified on this platform",
        RuntimeWarning,
        stacklevel=3,
    )
    os.chmod(path, 0o600)
