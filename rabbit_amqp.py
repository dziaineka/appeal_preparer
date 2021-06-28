import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Callable, Optional

import aio_pika

logger = logging.getLogger(__name__)


class Rabbit:
    def __init__(self,
                 exhange_name: str,
                 queue_name: str,
                 amqp_address: str,
                 loop: AbstractEventLoop,
                 name: str):
        self.queue_name = queue_name
        self.exhange_name = exhange_name
        self.amqp_address = amqp_address
        self.loop = loop
        self.callback: Callable
        self.name = name
        self.connection: Optional[aio_pika.connection.Connection] = None

    async def start(self, callback: Callable, passive: bool = True) -> None:
        self.callback = callback
        connected = False
        pause = 1

        while not connected:
            try:
                await self.connect(passive)
                connected = True
                pause = 1
                logger.info(f"[{self.name}] Подключились к раббиту")
            except Exception:
                connected = False

                if self.connection:
                    await self.connection.close()

                logger.exception(
                    f'[{self.name}] Fail. Trying reconnect Rabbit.')

                await asyncio.sleep(pause)

                if pause < 30:
                    pause *= 2

    async def connect(self, passive: bool = True) -> None:
        self.connection = await aio_pika.connect_robust(
            self.amqp_address,
            loop=self.loop,
            heartbeat=0
        )

        # Creating channel
        channel = await self.connection.channel()

        # Maximum message count which will be
        # processing at the same time.
        await channel.set_qos(prefetch_count=1)

        # Declaring queue
        queue = await channel.declare_queue(self.queue_name,
                                            passive=passive,
                                            durable=True)

        await queue.consume(self.process_message)

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process(requeue=True, ignore_processed=True):
            await self.callback(message)
