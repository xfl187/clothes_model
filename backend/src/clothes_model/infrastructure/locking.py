"""Cross-platform advisory file locking for single-host V1 coordination."""

import os
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self


class LockUnavailableError(RuntimeError):
    """Raised when another process already owns an advisory lock."""


class AdvisoryFileLock:
    """Own one byte of a persistent lock file until explicitly released."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: BinaryIO | None = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> None:
        if self.acquired:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            _lock_handle(handle)
        except BaseException:
            handle.close()
            raise
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            _unlock_handle(self._handle)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


if os.name == "nt":
    import msvcrt

    def _lock_handle(handle: BinaryIO) -> None:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise LockUnavailableError("advisory lock is already owned") from error

    def _unlock_handle(handle: BinaryIO) -> None:
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_handle(handle: BinaryIO) -> None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise LockUnavailableError("advisory lock is already owned") from error

    def _unlock_handle(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
