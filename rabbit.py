import requests
import json

import config
from exceptions import ErrorWhilePutInQueue


class Rabbit:
    def _send(self, exchange_name, routing_key: str, body: dict) -> None:
        url = config.RABBIT_ADDRESS + \
            f'/api/exchanges/%2F/{exchange_name}/publish'

        data = {
            'properties': {},
            'routing_key': routing_key,
            'payload': json.dumps(body),
            'payload_encoding': 'string'
        }

        response = requests.post(url, json=data)

        if response.status_code != 200:
            raise ErrorWhilePutInQueue(
                f'Ошибка при отправке урл в очередь: {response.reason}')

    def send_captcha_url(self, url: str,
                         appeal_id, user_id: int,
                         answer_queue: str) -> None:
        data = {
            'type': config.CAPTCHA_URL,
            'captcha': url,
            'appeal_id': appeal_id,
            'user_id': user_id,
            'answer_queue': answer_queue,
        }

        self._send(config.RABBIT_EXCHANGE_APPEAL,
                   config.RABBIT_ROUTING_STATUS,
                   data)

    def send_queue_name(self, answer_queue: str) -> None:
        data = {
            'type': config.FREE_WORKER,
            'answer_queue': answer_queue,
        }

        self._send(config.RABBIT_EXCHANGE_APPEAL,
                   config.RABBIT_ROUTING_STATUS,
                   data)

    def send_status(self,
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

        self._send(config.RABBIT_EXCHANGE_APPEAL,
                   config.RABBIT_ROUTING_STATUS,
                   status)
