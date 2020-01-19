import aio_pika
import asyncio


class Rabbit:
    def __init__(self,
                 logger,
                 exhange_name: str,
                 queue_name: str,
                 amqp_address: str):
        self.logger = logger
        self.queue_name = queue_name
        self.exhange_name = exhange_name
        self.amqp_address = amqp_address

    async def start(self, loop, callback) -> None:
        try:
            await self.connect(loop, callback)
        except Exception as exc:
            self.logger.info(f'Fail. Trying reconnect Rabbit. {exc}')
            self.logger.exception(exc)
            await asyncio.sleep(2)
            await self.start(loop, callback)

    async def connect(self, loop, callback) -> None:
        self.connection = await aio_pika.connect_robust(
            self.amqp_address,
            loop=loop
        )

        async with self.connection:
            # Creating channel
            channel = await self.connection.channel()

            # Declaring queue
            queue = await channel.declare_queue(
                self.queue_name,
                auto_delete=False,
                durable=True
            )

            await queue.bind(self.exhange_name, self.queue_name)

            while True:
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        print("aaaaaaaaaaaaaaaaaaaa")
                        async with message.process():
                            await callback(message.body.decode())
