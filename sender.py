import asyncio
from asyncio.events import AbstractEventLoop
import amqp_rabbit
import logging
import config
import json
from applicant import Applicant
from http_rabbit import Rabbit
import time
from typing import Any, Optional
from applicant.exceptions import *
from exceptions import *
from multiprocessing import shared_memory


class Sender():
    def __init__(self, email: str) -> None:
        self.queue_from_bot = email
        self.logger = self.setup_logging()
        self.applicant = Applicant(self.logger)
        self.loop = asyncio.get_event_loop()
        self.queue_to_bot = Rabbit()
        self.sending_in_progress = False
        self.current_appeal: dict
        self.email_to_delete = ''
        self.same_email_sleep = 1

    def setup_logging(self):
        # create logger
        logger = logging.getLogger('appeal_sender')
        logger.setLevel(logging.DEBUG)

        extra = {'queue': self.queue_from_bot}

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

    async def process_new_appeal(self, raw_appeal: str) -> None:
        self.sending_in_progress = True
        appeal = json.loads(raw_appeal)
        asyncio.ensure_future(self.async_process_new_appeal(appeal))

        # в этом месте мы проверяем в цикле когда параллельный поток закончит
        # посылать обращение, чтобы отпустить этот поток и он мог принимать
        # новое обращение для отправки
        while self.sending_in_progress:
            await asyncio.sleep(2)

        self.delete_from_busy_list(self.email_to_delete)

        self.current_appeal = {}
        self.logger.info(f'Обращение обработано ' +
                         f'user_id: {appeal["user_id"]} ' +
                         f'appeal_id: {appeal["appeal_id"]}')

    async def async_process_new_appeal(self, appeal: dict) -> None:
        self.logger.info(f'Новое обращение: {appeal}')
        email = self.get_value(appeal, 'sender_email', self.queue_from_bot)
        self.current_appeal = appeal
        self.email_to_delete = email

        if not self.new_in_busy_list(email):
            self.logger.info(f'Такой email уже отправляет - ' +
                             f'в конец очереди: {email}')

            self.queue_to_bot.reqeue(self.current_appeal)
            await asyncio.sleep(self.same_email_sleep)
            self.same_email_sleep = self.same_email_sleep * 2
            self.email_to_delete = ''
            self.sending_in_progress = False
            return

        self.same_email_sleep = 1
        self.logger.info(f"Достали имейл: {email}")

        try:
            self.send_captcha(appeal['appeal_id'], appeal['user_id'], email)
        except BrowserError:
            self.logger.info("Фейл браузинга")
            self.send_captcha(appeal['appeal_id'], appeal['user_id'], email)

    def new_in_busy_list(self, email: str) -> bool:
        try:
            busy_list = shared_memory.ShareableList(name=config.BUSY_LIST)
        except FileNotFoundError:
            busy_list = shared_memory.ShareableList([], name=config.BUSY_LIST)

        if email in busy_list:
            return False
        else:
            new_list = list(busy_list)
            new_list.append(email)
            busy_list.shm.close()
            busy_list.shm.unlink()
            shared_memory.ShareableList(new_list, name=config.BUSY_LIST)
            return True

    def delete_from_busy_list(self, email: str) -> None:
        try:
            busy_list = shared_memory.ShareableList(name=config.BUSY_LIST)
        except FileNotFoundError:
            busy_list = shared_memory.ShareableList([], name=config.BUSY_LIST)

        if email in busy_list:
            new_list = list(busy_list)

            while email in new_list:
                new_list.remove(email)

            busy_list.shm.close()
            busy_list.shm.unlink()
            shared_memory.ShareableList(new_list, name=config.BUSY_LIST)

    def send_captcha(self,
                     appeal_id: int,
                     user_id: int,
                     email: str) -> None:
        self.current_captcha_url = self.applicant.get_captcha(email)

        self.queue_to_bot.send_captcha_url(self.current_captcha_url,
                                           appeal_id,
                                           user_id,
                                           self.queue_from_bot)

    async def process_bot_message(self, raw_sender_status: str) -> None:
        data = json.loads(raw_sender_status)
        self.logger.info(f'Сообщение бота: {data}')
        email = self.get_value(data, 'sender_email', self.queue_from_bot)
        self.logger.info(f"Достали имейл: {email}")

        try:
            if data['type'] == config.CAPTCHA_TEXT:
                self.process_captcha(data['captcha_text'],
                                     data['user_id'],
                                     data['appeal_id'])

            elif data['type'] == config.CANCEL:
                self.logger.info("Отмена")
                self.sending_in_progress = False
                self.applicant.cancel()
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
            self.send_appeal()

    def process_captcha(self,
                        captcha_text: str,
                        user_id: int,
                        appeal_id: int) -> None:
        if self.applicant.enter_captcha_and_submit(captcha_text) != config.OK:
            raise CaptchaInputError()

        self.queue_to_bot.send_status(user_id,
                                      config.CAPTCHA_OK,
                                      self.queue_from_bot,
                                      appeal_id)

        self.send_appeal()

    def send_appeal(self):
        email = self.get_value(self.current_appeal,
                               'sender_email',
                               self.queue_from_bot)

        password = self.get_value(self.current_appeal,
                                  'sender_email_password',
                                  config.EMAIL_PWD)

        url = self.applicant.get_appeal_url(email, password)

        status_code, message = self.applicant.send_appeal(
            self.current_appeal['appeal'], url)

        if status_code != config.OK:
            raise ErrorWhileSending(message)

        self.queue_to_bot.send_status(self.current_appeal['user_id'],
                                      config.OK,
                                      self.queue_from_bot,
                                      self.current_appeal['appeal_id'],
                                      message)

        self.sending_in_progress = False

    async def start_sender(self, loop: AbstractEventLoop) -> None:
        appeals = amqp_rabbit.Rabbit(self.logger,
                                     config.RABBIT_EXCHANGE_MANAGING,
                                     config.RABBIT_QUEUE_APPEAL,
                                     config.RABBIT_AMQP_ADDRESS)

        bot = amqp_rabbit.Rabbit(self.logger,
                                 config.RABBIT_EXCHANGE_SENDING,
                                 self.queue_from_bot,
                                 config.RABBIT_AMQP_ADDRESS)

        asyncio.ensure_future(bot.start(loop, self.process_bot_message))

        self.logger.info(f"Воркер стартует.")
        await appeals.start(loop, self.process_new_appeal)

    def start(self):
        self.loop.run_until_complete(self.start_sender(self.loop))
        self.loop.close()

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

    def stop(self):
        self.logger.info('Суецыд')
        self.applicant.cancel()


def run_consuming(sender):
    while True:
        try:
            sender.start()
        except Exception as exc:
            sender.logger.info(f'ОЙ start - {str(exc)}')
            sender.logger.exception(exc)
            sender.stop()
            time.sleep(2)


def start(email: str):
    sender = Sender(email)
    run_consuming(sender)
