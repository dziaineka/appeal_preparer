from typing import Any
from applicant.exceptions import *
from exceptions import *
import logging
import json
import time

import pika

from applicant import Applicant
import config
from rabbit import Rabbit


class Preparer:
    def __init__(self, email: str) -> None:
        self.queue_name = email
        self.logger = self.setup_logging()
        self.applicant = Applicant(self.logger)
        self.queue = Rabbit()

    def start(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=config.RABBIT_HOST,
                credentials=pika.credentials.PlainCredentials(
                    config.RABBIT_LOGIN,
                    config.RABBIT_PASSWORD),
                connection_attempts=10,
                retry_delay=2,
                heartbeat=0))

        self.channel = self.connection.channel()

        self.channel.queue_declare(queue=self.queue_name,
                                   durable=True,
                                   auto_delete=False)

        self.channel.queue_bind(queue=self.queue_name,
                                exchange=config.RABBIT_EXCHANGE_SENDING,
                                routing_key=self.queue_name)

        self.channel.basic_qos(prefetch_count=1)

        self.channel.basic_consume(queue=self.queue_name,
                                   consumer_tag=self.queue_name,
                                   on_message_callback=self.callback)

        self.queue.send_queue_free(self.queue_name)
        self.logger.info('Стартанули')
        self.channel.start_consuming()

    def stop(self):
        self.logger.info('Суецыд')
        self.applicant.cancel()
        self.channel.close()
        self.connection.close()

    def setup_logging(self):
        # create logger
        logger = logging.getLogger('appeal_sender')
        logger.setLevel(logging.DEBUG)

        extra = {'queue': self.queue_name}

        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # create formatter and add it to the handlers
        formatter = logging.Formatter(
            '%(asctime)s - %(queue)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        # add the handlers to the logger
        logger.addHandler(ch)
        logger = logging.LoggerAdapter(logger, extra)

        return logger

    def process_captcha(self,
                        captcha_text: str,
                        user_id: int,
                        appeal_id: int) -> None:
        if self.applicant.enter_captcha_and_submit(captcha_text) != config.OK:
            raise CaptchaInputError()

        self.queue.send_status(user_id,
                               config.CAPTCHA_OK,
                               self.queue_name,
                               appeal_id)

    def process_appeal(self, method, data: dict) -> None:
        email = self.get_value(data, 'sender_email', self.queue_name)

        password = self.get_value(data, 'sender_email_password',
                                  config.EMAIL_PWD)

        url = self.applicant.get_appeal_url(email, password)
        status_code, message = self.applicant.send_appeal(data['appeal'], url)

        if status_code != config.OK:
            raise ErrorWhileSending(message)

        self.queue.send_status(data['user_id'],
                               status_code,
                               self.queue_name,
                               data['appeal_id'],
                               message)

        self.queue.send_queue_free(self.queue_name)

    def send_captcha(self,
                     appeal_id: int,
                     user_id: int,
                     email: str) -> None:
        self.current_captcha_url = self.put_capcha_to_queue(appeal_id,
                                                            user_id,
                                                            email)

    @classmethod
    def get_value(cls, data: dict, key: str, default: Any = None) -> Any:
        try:
            value = data[key]

            if value:
                return value
            elif default:
                return default
            else:
                return value
        except KeyError:
            if default:
                return default
            else:
                return None

    def callback(self, ch, method, properties, body: str) -> None:
        self.queue.send_queue_busy(self.queue_name)
        data = json.loads(body)
        self.logger.info(" [x] Received %r" % data)
        email = self.get_value(data, 'sender_email', self.queue_name)
        self.logger.info(f"Достали имейл: {email}")

        try:
            if data['type'] == config.APPEAL:
                self.process_appeal(method, data)
            elif data['type'] == config.CAPTCHA_TEXT:
                self.process_captcha(data['captcha_text'],
                                     data['user_id'],
                                     data['appeal_id'])
            elif data['type'] == config.GET_CAPTCHA:
                self.send_captcha(data['appeal_id'], data['user_id'], email)
            elif data['type'] == config.CANCEL:
                self.logger.info("Отмена")
                self.applicant.cancel()
                self.queue.send_queue_free(self.queue_name)
        except CaptchaInputError:
            self.logger.info("Фейл капчи")
            self.send_captcha(data['appeal_id'], data['user_id'], email)
        except NoMessageFromPolice:
            self.logger.info("Фейл почты. Не нашлось письмо.")
            self.send_captcha(data['appeal_id'], data['user_id'], email)
        except AppealURLParsingFailed:
            self.logger.info("Не удалось распарсить урл из письма.")
            self.send_captcha(data['appeal_id'], data['user_id'], email)
        except ErrorWhileSending:
            self.logger.info("Фейл во время отправки")
            self.send_captcha(data['appeal_id'], data['user_id'], email)
        except BrowserError:
            self.logger.info("Фейл браузинга")
            self.send_captcha(data['appeal_id'], data['user_id'], email)
        except RancidAppeal:
            self.logger.info("Взяли протухшую форму обращения")
            self.process_appeal(method, data)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        self.logger.info('Обработали, ждем новенького')

    def put_capcha_to_queue(self,
                            appeal_id: int,
                            user_id: int,
                            email: str) -> str:
        url = self.applicant.get_captcha(email)
        self.queue.send_captcha_url(url, appeal_id, user_id, self.queue_name)
        return url


def run_consuming(preparer):
    while True:
        try:
            preparer.start()
        except Exception as exc:
            preparer.logger.info(f'ОЙ start - {str(exc)}')
            preparer.logger.exception(exc)
            preparer.stop()
            time.sleep(2)


def start(email: str):
    preparer = Preparer(email)
    run_consuming(preparer)
