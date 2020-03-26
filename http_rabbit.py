import logging
import aiohttp
import json

import config
from exceptions import ErrorWhilePutInQueue

logger = logging.getLogger(__name__)


class Rabbit:
    async def _send(self, exchange_name, routing_key: str, body: dict) -> None:
        url = config.RABBIT_ADDRESS + \
            f'/api/exchanges/%2F/{exchange_name}/publish'

        data = {
            'properties': {},
            'persistent': True,
            'routing_key': routing_key,
            'payload': json.dumps(body),
            'payload_encoding': 'string'
        }

        await self.do_request(url, data)

    async def do_request(self, url: str, data: dict):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        raise ErrorWhilePutInQueue(
                            f'Ошибка при отправке урл в очередь: ' +
                            f'{response.reason}'
                        )
                    else:
                        logger.info("Ответили боту")
        except Exception as exc:
            raise ErrorWhilePutInQueue(
                f'Ошибка при отправке урл в очередь хз {str(exc)}',
                (url, data))

    async def send_sending_stopped(self,
                                   appeal_id: int,
                                   user_id: int,
                                   answer_queue: str,
                                   message=config.TIMEOUT_MESSAGE):
        data = {
            'type': config.SENDING_CANCELLED,
            'appeal_id': appeal_id,
            'user_id': user_id,
            'answer_queue': answer_queue,
            'message': message
        }

        await self._send(config.RABBIT_EXCHANGE_SENDING,
                         config.RABBIT_ROUTING_STATUS,
                         data)

    async def send_captcha_url(self,
                               url: str,
                               appeal_id: int,
                               user_id: int,
                               answer_queue: str) -> None:
        data = {
            'type': config.CAPTCHA_URL,
            'captcha': url,
            'appeal_id': appeal_id,
            'user_id': user_id,
            'answer_queue': answer_queue,
        }

        await self._send(config.RABBIT_EXCHANGE_SENDING,
                         config.RABBIT_ROUTING_STATUS,
                         data)

    async def send_status(self,
                          user_id: int,
                          status_code: str,
                          answer_queue: str,
                          appeal_id: int,
                          text: str = '') -> None:
        status = {
            'type': status_code,
            'user_id': user_id,
            'text': text,
            'answer_queue': answer_queue,
            'appeal_id': appeal_id,
        }

        await self._send(config.RABBIT_EXCHANGE_SENDING,
                         config.RABBIT_ROUTING_STATUS,
                         status)

    async def reqeue(self, body):
        await self._send(config.RABBIT_EXCHANGE_MANAGING,
                         config.RABBIT_ROUTING_APPEAL,
                         body)
