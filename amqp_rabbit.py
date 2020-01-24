import aioamqp
import asyncio
import config


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

    async def start(self, callback) -> None:
        try:
            await self.connect(callback)
        except Exception as exc:
            self.logger.info(f'Fail. Trying reconnect Rabbit. {exc}')
            self.logger.exception(exc)
            await asyncio.sleep(2)
            await self.start(callback)

    async def connect(self, callback) -> None:
        transport, protocol = await aioamqp.connect(
            host=config.RABBIT_HOST,
            port=config.RABBIT_AMQP_PORT,
            login=config.RABBIT_LOGIN,
            password=config.RABBIT_PASSWORD,
            login_method='AMQPLAIN',
            heartbeat=65535
        )

        channel = await protocol.channel()

        await channel.basic_qos(prefetch_count=1)

        await channel.queue_declare(queue_name=self.queue_name,
                                    durable=True)

        await channel.queue_bind(self.queue_name,
                                 self.exhange_name,
                                 routing_key=self.queue_name)

        await channel.basic_consume(callback,
                                    queue_name=self.queue_name,
                                    no_ack=False)
