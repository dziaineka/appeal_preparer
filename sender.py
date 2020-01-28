import asyncio
from asyncio.events import AbstractEventLoop
import amqp_rabbit
from http_rabbit import Rabbit as HttpRabbit
import logging
import config
import json
from applicant import Applicant
import time
from typing import Any, Optional
from applicant.exceptions import *
from exceptions import *
from multiprocessing import shared_memory
from timer import Timer


class Sender():
    def __init__(self, email: str) -> None:
        self.queue_from_bot = email
        self.logger = self.setup_logging()
        self.applicant = Applicant(self.logger)
        self.loop = asyncio.get_event_loop()
        self.sending_in_progress = False
        self.current_appeal: dict = {}
        self.email_to_delete = ''
        self.same_email_sleep = 1
        self.stop_timer = Timer(self.stop_appeal_sending, self.loop)

    def send_to_bot(self) -> HttpRabbit:
        return HttpRabbit(self.logger)

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

    async def process_new_appeal(self,
                                 channel,
                                 body,
                                 envelope,
                                 properties) -> None:
        self.sending_in_progress = True
        appeal = json.loads(body)
        self.applicant.get_browser()
        asyncio.ensure_future(self.async_process_new_appeal(appeal))

        # в этом месте мы проверяем в цикле когда параллельный поток закончит
        # посылать обращение, чтобы отпустить этот поток и он мог принимать
        # новое обращение для отправки
        while self.sending_in_progress:
            await asyncio.sleep(2)

        self.delete_from_busy_list(self.email_to_delete)

        self.current_appeal = {}
        await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        self.applicant.quit_browser()

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

            await self.send_to_bot().reqeue(self.current_appeal)
            await asyncio.sleep(self.same_email_sleep)
            self.same_email_sleep = self.same_email_sleep * 2
            self.email_to_delete = ''
            self.sending_in_progress = False
            return

        self.same_email_sleep = 1
        self.logger.info(f"Достали имейл: {email}")

        try:
            await self.send_captcha(appeal['appeal_id'],
                                    appeal['user_id'],
                                    email)
        except BrowserError:
            self.logger.info("Фейл браузинга")
            await self.send_captcha(appeal['appeal_id'],
                                    appeal['user_id'],
                                    email)
        except ErrorWhilePutInQueue as exc:
            self.logger.error(exc.text)
            if exc.data:
                await self.send_to_bot().do_request(exc.data[0], exc.data[1])
        except Exception as exc:
            self.logger.exception('ОЙ async_process_new_appeal')
            await self.send_captcha(appeal['appeal_id'],
                                    appeal['user_id'],
                                    email)

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

    async def send_captcha(self,
                           appeal_id: int,
                           user_id: int,
                           email: str) -> None:
        self.current_captcha_url = self.applicant.get_captcha(email)
        self.stop_timer.cock_it(config.CANCEL_TIMEOUT)

        await self.send_to_bot().send_captcha_url(self.current_captcha_url,
                                                  appeal_id,
                                                  user_id,
                                                  self.queue_from_bot)

    async def process_bot_message(self,
                                  channel,
                                  body,
                                  envelope,
                                  properties) -> None:
        data = json.loads(body)
        self.logger.info(f'Сообщение от бота: {data}')
        email = self.get_value(data, 'sender_email', self.queue_from_bot)
        self.logger.info(f"Достали имейл: {email}")
        user_id = data['user_id']
        appeal_id = data['appeal_id']

        # костыльчик пока бот не научится не хранить обращения, а парсить
        if not self.current_appeal \
                or self.current_appeal['user_id'] != user_id \
                or self.current_appeal['appeal_id'] != appeal_id:
            await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
            return

        try:
            if data['type'] == config.CAPTCHA_TEXT:
                self.stop_timer.delete()

                await self.process_captcha(data['captcha_text'],
                                           data['user_id'],
                                           data['appeal_id'])

            elif data['type'] == config.CANCEL:
                await self.stop_appeal_sending(local=True)
        except CaptchaInputError:
            self.logger.info("Фейл капчи")
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        except NoMessageFromPolice:
            self.logger.info("Фейл почты. Не нашлось письмо.")
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        except AppealURLParsingFailed:
            self.logger.info("Не удалось распарсить урл из письма.")
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        except ErrorWhileSending:
            self.logger.info("Фейл во время отправки")
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        except BrowserError:
            self.logger.info("Фейл браузинга")
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        except RancidAppeal:
            self.logger.info("Взяли протухшую форму обращения")
            await self.send_appeal()
        except ErrorWhilePutInQueue as exc:
            self.logger.error(exc.text)
            if exc.data:
                await self.send_to_bot().do_request(exc.data[0], exc.data[1])
        except Exception as exc:
            self.logger.exception('ОЙ process_bot_message')
            await self.send_captcha(data['appeal_id'], data['user_id'], email)
        finally:
            await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)

    async def process_captcha(self,
                              captcha_text: str,
                              user_id: int,
                              appeal_id: int) -> None:
        if self.applicant.enter_captcha_and_submit(captcha_text) != config.OK:
            raise CaptchaInputError()

        await self.send_to_bot().send_status(user_id,
                                             config.CAPTCHA_OK,
                                             self.queue_from_bot,
                                             appeal_id)

        await self.send_appeal()

    async def send_appeal(self):
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

        await self.send_to_bot().send_status(self.current_appeal['user_id'],
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

        asyncio.ensure_future(bot.start(self.process_bot_message))
        asyncio.ensure_future(appeals.start(self.process_new_appeal))
        asyncio.ensure_future(self.stop_timer.start())

        self.logger.info(f"Воркер стартует.")

    async def stop_appeal_sending(self, local=False):
        self.logger.info(f"Останавливаем отправку обращения")
        if not local:
            await self.send_to_bot().send_sending_stopped(
                self.current_appeal['appeal_id'],
                self.current_appeal['user_id'],
                self.queue_from_bot
            )

        self.current_appeal = {}
        self.stop_timer.delete()
        self.logger.info("Отмена")
        self.sending_in_progress = False

    def start(self):
        self.loop.run_until_complete(self.start_sender(self.loop))
        self.loop.run_forever()

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
        self.applicant.quit_browser()


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
