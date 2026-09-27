"""Private content-addressed image storage."""

import hashlib
import io
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    sha256: str
    relative_path: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created: bool


class LocalFileStorage:
    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int = 20_000_000,
        max_pixels: int = 24_000_000,
        max_dimension: int = 8192,
    ) -> None:
        self.root = root.resolve()
        self.objects = self.root / "objects"
        self.temp = self.root / "temp"
        self.max_bytes, self.max_pixels, self.max_dimension = max_bytes, max_pixels, max_dimension
        self.objects.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)

    def normalize_and_store(self, source: bytes) -> NormalizedImage:
        if not source or len(source) > self.max_bytes:
            raise StorageError("image size is invalid")
        try:
            with Image.open(io.BytesIO(source)) as opened:
                if opened.format not in {"JPEG", "PNG"}:
                    raise StorageError("unsupported image format")
                if (
                    opened.width <= 0
                    or opened.height <= 0
                    or opened.width > self.max_dimension
                    or opened.height > self.max_dimension
                    or opened.width * opened.height > self.max_pixels
                ):
                    raise StorageError("image dimensions are invalid")
                opened.verify()
            with Image.open(io.BytesIO(source)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=92, optimize=True, exif=b"")
                normalized = output.getvalue()
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise StorageError("image could not be decoded") from error
        digest = hashlib.sha256(normalized).hexdigest()
        relative = Path("objects") / digest[:2] / f"{digest}.jpg"
        target = self._confined(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return NormalizedImage(
                digest, relative.as_posix(), "image/jpeg", len(normalized), width, height, False
            )
        temporary = self.temp / f"{uuid4()}.part"
        try:
            with temporary.open("xb") as handle:
                handle.write(normalized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return NormalizedImage(
            digest, relative.as_posix(), "image/jpeg", len(normalized), width, height, True
        )

    def open(self, relative_path: str):
        path = self._confined(Path(relative_path))
        if path.is_symlink() or not path.is_file():
            raise StorageError("stored object is unavailable")
        return path.open("rb")

    def delete(self, relative_path: str) -> None:
        path = self._confined(Path(relative_path))
        if path.is_symlink():
            raise StorageError("stored object is unavailable")
        path.unlink(missing_ok=True)

    def reconcile_temporary(self) -> list[str]:
        ambiguous: list[str] = []
        for item in self.temp.iterdir():
            if item.is_file() and not item.is_symlink() and item.suffix == ".part":
                item.unlink()
            else:
                ambiguous.append(item.name)
        return ambiguous

    def _confined(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise StorageError("invalid storage path")
        resolved = (self.root / relative).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise StorageError("invalid storage path")
        return resolved
