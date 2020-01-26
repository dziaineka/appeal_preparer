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
        connected = False
        pause = 1

        while not connected:
            try:
                await self.connect(callback)
                connected = True
                pause = 1
                self.logger.info("Подключились к раббиту")
            except Exception:
                connected = False
                self.logger.exception('Fail. Trying reconnect Rabbit.')
                await asyncio.sleep(pause)

                if pause < 30:
                    pause *= 2

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
