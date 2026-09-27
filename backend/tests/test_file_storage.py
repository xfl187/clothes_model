import io
from pathlib import Path

import pytest
from PIL import Image

from clothes_model.infrastructure.storage import LocalFileStorage, StorageError


def image_bytes(format_name: str = "PNG", *, orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (4, 2), (20, 80, 160))
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    output = io.BytesIO()
    image.save(output, format=format_name, exif=exif)
    return output.getvalue()


def test_normalize_orientation_strip_metadata_deduplicate_and_round_trip(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "private")
    first = storage.normalize_and_store(image_bytes("JPEG", orientation=6))
    second = storage.normalize_and_store(image_bytes("JPEG", orientation=6))
    assert (first.width, first.height) == (2, 4)
    assert first.created and not second.created and first.sha256 == second.sha256
    with storage.open(first.relative_path) as handle, Image.open(handle) as normalized:
        assert normalized.format == "JPEG" and normalized.getexif() == {}
        assert normalized.size == (2, 4)


def test_storage_rejects_bad_paths_content_limits_and_cleans_only_known_temp(
    tmp_path: Path,
) -> None:
    storage = LocalFileStorage(tmp_path / "private", max_bytes=1000, max_dimension=8)
    with pytest.raises(StorageError):
        storage.normalize_and_store(b"not-an-image")
    with pytest.raises(StorageError):
        storage.normalize_and_store(image_bytes() * 100)
    with pytest.raises(StorageError):
        storage.open("../escape")
    abandoned = storage.temp / "abandoned.part"
    abandoned.write_bytes(b"partial")
    ambiguous = storage.temp / "keep.unknown"
    ambiguous.write_bytes(b"unknown")
    assert storage.reconcile_temporary() == ["keep.unknown"]
    assert not abandoned.exists() and ambiguous.exists()
