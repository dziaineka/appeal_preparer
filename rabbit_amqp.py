import aioamqp
import asyncio
import config
import logging

logger = logging.getLogger(__name__)


class Rabbit:
    def __init__(self,
                 exhange_name: str,
                 queue_name: str,
                 amqp_address: str):
        self.queue_name = queue_name
        self.exhange_name = exhange_name
        self.amqp_address = amqp_address

    async def start(self, callback, passive=False) -> None:
        connected = False
        pause = 1

        while not connected:
            try:
                await self.connect(callback, passive)
                connected = True
                pause = 1
                logger.info("Подключились к раббиту")
            except Exception:
                connected = False
                logger.info('Fail. Trying reconnect Rabbit.')
                await asyncio.sleep(pause)

                if pause < 30:
                    pause *= 2

    async def connect(self, callback, passive=False) -> None:
        _, protocol = await aioamqp.connect(
            host=config.RABBIT_HOST,
            port=config.RABBIT_AMQP_PORT,
            login=config.RABBIT_LOGIN,
            password=config.RABBIT_PASSWORD,
            login_method='AMQPLAIN',
            heartbeat=0
        )

        channel = await protocol.channel()

        await channel.basic_qos(prefetch_count=1)

        await channel.queue_declare(queue_name=self.queue_name,
                                    durable=True,
                                    passive=passive)

        await channel.queue_bind(self.queue_name,
                                 self.exhange_name,
                                 routing_key=self.queue_name)

        await channel.basic_consume(callback,
                                    queue_name=self.queue_name,
                                    no_ack=False)
