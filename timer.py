import asyncio
from datetime import datetime, timedelta
from typing import Awaitable


class Timer:
    def __init__(self, stop_callback, loop):
        self.stop_callback = stop_callback
        self.loop = loop

        # infinitely distant timestamp (now + 50 years)
        self.far_far_future = datetime.utcnow() + timedelta(weeks=50*4*12)

        self.stop_time = self.far_far_future

    async def start(self) -> Awaitable[None]:
        while True:
            await self._check_for_overdue()
            await asyncio.sleep(60)

    async def _check_for_overdue(self):
        if datetime.utcnow() >= self.stop_time:
            asyncio.run_coroutine_threadsafe(self.stop_callback(), self.loop)
            self.delete()

    def cock_it(self, timeout: float) -> None:
        self.stop_time = datetime.utcnow() + timedelta(minutes=timeout)

    def delete(self) -> None:
        self.stop_time = self.far_far_future
