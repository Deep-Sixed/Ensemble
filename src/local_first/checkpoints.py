from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from local_first.safety import WorkspaceGuard


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
    safe_name = "__".join(rel.parts)
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
    rel = source.relative_to(guard.root)
    safe_name = "__".join(rel.parts)
    return any(Path(checkpoint_root).glob(f"*__{safe_name}"))
