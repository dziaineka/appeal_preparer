from applicant.exceptions import *
from exceptions import *
import logging
import random
import json

import pika

from applicant import Applicant
import config
from rabbit import Rabbit


class Preparer:
    def __init__(self, email: str) -> None:
        self.current_captcha_url = ''
        self.logger = self.setup_logging()
        self.applicant = Applicant(address=email)
        self.queue = Rabbit()
        self.saved_appeal = {}

    def start(self):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=config.RABBIT_HOST,
                credentials=pika.credentials.PlainCredentials(
                    config.RABBIT_LOGIN,
                    config.RABBIT_PASSWORD),
                connection_attempts=10,
                retry_delay=2))

        channel = connection.channel()

        self.queue_name = \
            f'captcha_text_{str(random.randint(1000000, 9999999))}'

        channel.queue_declare(queue=self.queue_name,
                              durable=True,
                              auto_delete=True)

        channel.queue_bind(queue=self.queue_name,
                           exchange=config.RABBIT_EXCHANGE_APPEAL,
                           routing_key=self.queue_name)

        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(queue=self.queue_name,
                              on_message_callback=self.callback)

        self.current_captcha_url = self.put_capcha_to_queue()
        self.logger.info(' [*] Waiting for messages. To exit press CTRL+C')
        channel.start_consuming()

    def setup_logging(self):
        # create logger
        my_logger = logging.getLogger('appeal_preparer')
        my_logger.setLevel(logging.DEBUG)

        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # create formatter and add it to the handlers
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        # add the handlers to the logger
        my_logger.addHandler(ch)

        return my_logger

    def process_data(self, method, data: dict) -> None:
        captcha_text = data['captcha_text']
        captcha_url = data['captcha_url']

        if captcha_url != self.current_captcha_url:
            raise CaptchaInputError()

        if self.applicant.enter_captcha_and_submit(captcha_text) != config.OK:
            raise CaptchaInputError()

        appeal_url = self.applicant.get_appeal_url()
        self.process_appeal(method, data, appeal_url)

    def process_appeal(self, method, data: dict, url: str) -> None:
        status_code, message = self.applicant.send_appeal(data, url)

        if status_code != config.OK:
            raise ErrorWhileSending(message)

        self.queue.send_status(
            data['user_id'], status_code, self.queue_name, message)
        self.current_captcha_url = self.put_capcha_to_queue()

    def callback(self, ch, method, properties, body: str) -> None:
        data = json.loads(body)
        self.logger.info(" [x] Received %r" % data)

        try:
            if data['type'] == config.APPEAL:
                self.process_data(method, data)
            elif data['type'] == config.CAPTCHA:
                self.saved_appeal['captcha_text'] = data['captcha_text']
                self.saved_appeal['captcha_url'] = data['captcha_url']
                self.process_data(method, self.saved_appeal)
        except CaptchaInputError:
            self.logger.info("Фейл капчи")
            self.current_captcha_url = self.put_capcha_to_queue()
            self.queue.send_status(
                data['user_id'], config.CAPTCHA, self.queue_name)
            self.saved_appeal = data
        except NoMessageFromPolice:
            self.logger.info("Фейл почты")
            self.current_captcha_url = self.put_capcha_to_queue()
            self.queue.send_status(
                data['user_id'], config.CAPTCHA, self.queue_name)
            self.saved_appeal = data
        except ErrorWhileSending:
            self.logger.info("Фейл почты")
            self.current_captcha_url = self.put_capcha_to_queue()
            self.queue.send_status(
                data['user_id'], config.CAPTCHA, self.queue_name)
            self.saved_appeal = data

        ch.basic_ack(delivery_tag=method.delivery_tag)
        self.logger.info(' [*] Waiting for messages. To exit press CTRL+C')

    def put_capcha_to_queue(self) -> str:
        url = self.applicant.get_captcha()
        self.queue.send_captcha_url(url, self.queue_name)
        return url


def start(email: str):
    preparer = Preparer(email)
    preparer.start()
