"""Confined atomic storage for immutable Workflow artifacts."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from clothes_model.infrastructure.storage.local import StorageError


@dataclass(frozen=True, slots=True)
class StoredWorkflowArtifacts:
    workflow_path: str
    manifest_path: str
    workflow_size_bytes: int
    manifest_size_bytes: int


class WorkflowArtifactStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.workflows = self.root / "workflows"
        self.temporary = self.workflows / ".temporary"
        self.workflows.mkdir(parents=True, exist_ok=True)
        self.temporary.mkdir(parents=True, exist_ok=True)

    def publish(
        self, version_id: str, workflow: bytes, manifest: bytes
    ) -> StoredWorkflowArtifacts:
        allowed = "0123456789abcdefghijklmnopqrstuvwxyz-"
        if not version_id or any(character not in allowed for character in version_id.lower()):
            raise StorageError("invalid workflow version id")
        target = self._confined(Path("workflows") / version_id)
        if target.exists():
            raise StorageError("workflow artifacts already exist")
        temporary = self._confined(Path("workflows") / ".temporary" / str(uuid4()))
        temporary.mkdir(parents=False, exist_ok=False)
        try:
            self._write(temporary / "workflow.json", workflow)
            self._write(temporary / "manifest.json", manifest)
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return StoredWorkflowArtifacts(
            workflow_path=(Path("workflows") / version_id / "workflow.json").as_posix(),
            manifest_path=(Path("workflows") / version_id / "manifest.json").as_posix(),
            workflow_size_bytes=len(workflow),
            manifest_size_bytes=len(manifest),
        )

    def read(self, relative_path: str) -> bytes:
        path = self._confined(Path(relative_path))
        if path.is_symlink() or not path.is_file():
            raise StorageError("workflow artifact is unavailable")
        return path.read_bytes()

    def delete_version(self, version_id: str) -> None:
        target = self._confined(Path("workflows") / version_id)
        if target.exists() and (target.is_symlink() or not target.is_dir()):
            raise StorageError("workflow artifact directory is invalid")
        shutil.rmtree(target, ignore_errors=True)

    def reconcile(self, known_version_ids: set[str]) -> list[str]:
        for item in self.temporary.iterdir():
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            elif item.is_file() and not item.is_symlink():
                item.unlink()
        orphans: list[str] = []
        for item in self.workflows.iterdir():
            if item.name == ".temporary":
                continue
            if item.is_dir() and not item.is_symlink() and item.name not in known_version_ids:
                orphans.append(item.name)
        return sorted(orphans)

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    def _confined(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise StorageError("invalid workflow artifact path")
        resolved = (self.root / relative).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise StorageError("invalid workflow artifact path")
        return resolved

