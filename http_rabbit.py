import aiohttp
import json

import config
from exceptions import ErrorWhilePutInQueue


class Rabbit:
    def __init__(self):
        self._http_session = aiohttp.ClientSession()

    def __del__(self):
        self._http_session.close()

    async def _send(self, exchange_name, routing_key: str, body: dict) -> None:
        url = config.RABBIT_ADDRESS + \
            f'/api/exchanges/%2F/{exchange_name}/publish'

        data = {
            'properties': {},
            'routing_key': routing_key,
            'payload': json.dumps(body),
            'payload_encoding': 'string'
        }

        try:
            async with self._http_session.post(url, json=data) as response:
                if response.status != 200:
                    raise ErrorWhilePutInQueue(
                        f'Ошибка при отправке урл в очередь: {response.reason}'
                    )
        except aiohttp.client_exceptions.ServerDisconnectedError:
            raise ErrorWhilePutInQueue(
                f'Ошибка при отправке урл в очередь ServerDisconnectedError')

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
