from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from ensemble.safety import WorkspaceGuard


@dataclass(frozen=True)
class Checkpoint:
    source: Path
    snapshot: Path
    digest: str
    created_at: str


def create_checkpoint(
    guard: WorkspaceGuard,
    relative_path: str | Path,
    checkpoint_root: str | Path = "state/checkpoints",
) -> Checkpoint:
    source = guard.resolve_read_path(relative_path)
    if not source.is_file():
        raise ValueError(f"Cannot checkpoint non-file path: {source}")

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    created_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rel = source.relative_to(guard.root)
    safe_name = _safe_name(rel)
    snapshot_dir = Path(checkpoint_root).expanduser()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_dir / f"{created_at}__{digest[:12]}__{safe_name}"
    shutil.copy2(source, snapshot)
    return Checkpoint(source=source, snapshot=snapshot, digest=digest, created_at=created_at)


def has_checkpoint(
    guard: WorkspaceGuard,
    relative_path: str | Path,
    checkpoint_root: str | Path = "state/checkpoints",
) -> bool:
    source = guard.resolve_read_path(relative_path)
    safe_name = _safe_name(source.relative_to(guard.root))
    root = Path(checkpoint_root)
    if not root.is_dir():
        return False
    # Snapshots are named <timestamp>__<digest>__<safe_name>; compare exactly
    # rather than globbing, so names with [ ] * ? or a "__" cannot collide.
    return any(
        len(parts := path.name.split("__", 2)) == 3 and parts[2] == safe_name
        for path in root.iterdir()
    )


def _safe_name(relative: Path) -> str:
    """Reversible, collision-free flattening of a relative path ('a/b' != 'a__b')."""
    return quote(relative.as_posix(), safe="")
