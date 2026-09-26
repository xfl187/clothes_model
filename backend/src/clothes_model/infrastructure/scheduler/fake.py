"""Observable scheduler fake for lifecycle tests."""


class FakeScheduler:
    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self.start_count += 1
        self._running = True

    async def stop(self) -> None:
        self.stop_count += 1
        self._running = False
