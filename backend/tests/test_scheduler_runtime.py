import asyncio
import subprocess
import sys
from pathlib import Path

from clothes_model.infrastructure.scheduler.coordinator import SchedulerCoordinator
from clothes_model.infrastructure.scheduler.fake import FakeScheduler


def test_disabled_scheduler_does_not_acquire_lock(tmp_path: Path) -> None:
    async def exercise() -> None:
        fake = FakeScheduler()
        lock_path = tmp_path / "disabled.lock"
        coordinator = SchedulerCoordinator(enabled=False, lock_path=lock_path, scheduler=fake)

        await coordinator.start()
        assert coordinator.status == "disabled"
        assert fake.start_count == 0
        assert not lock_path.exists()
        await coordinator.stop()

    asyncio.run(exercise())


def test_enabled_scheduler_owns_and_releases_lock(tmp_path: Path) -> None:
    async def exercise() -> None:
        fake = FakeScheduler()
        coordinator = SchedulerCoordinator(
            enabled=True,
            lock_path=tmp_path / "enabled.lock",
            scheduler=fake,
        )

        await coordinator.start()
        assert coordinator.status == "owned"
        assert fake.start_count == 1
        await coordinator.stop()
        assert coordinator.status == "stopped"
        assert fake.stop_count == 1

    asyncio.run(exercise())


def test_second_scheduler_process_fails_fast(tmp_path: Path) -> None:
    lock_path = tmp_path / "shared.lock"
    holder_code = (
        "import sys; "
        "from pathlib import Path; "
        "from clothes_model.infrastructure.locking import AdvisoryFileLock; "
        "lock=AdvisoryFileLock(Path(sys.argv[1])); lock.acquire(); "
        "print('READY', flush=True); sys.stdin.readline(); lock.release()"
    )
    contender_code = (
        "import sys; "
        "from pathlib import Path; "
        "from clothes_model.infrastructure.locking import AdvisoryFileLock, LockUnavailableError; "
        "lock=AdvisoryFileLock(Path(sys.argv[1])); "
        "\ntry: lock.acquire()\n"
        "except LockUnavailableError: raise SystemExit(23)\n"
        "else: lock.release(); raise SystemExit(0)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_code, str(lock_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "READY"
        contender = subprocess.run(
            [sys.executable, "-c", contender_code, str(lock_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert contender.returncode == 23, contender.stderr
    finally:
        if holder.stdin is not None:
            holder.stdin.write("\n")
            holder.stdin.flush()
        holder.wait(timeout=10)
