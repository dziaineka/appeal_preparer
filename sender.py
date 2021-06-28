import asyncio
import json
import logging
from asyncio.events import AbstractEventLoop
from pprint import pformat
from typing import Any, Optional

import aio_pika
from imapclient.exceptions import LoginError as EmailLoginError
from selenium import webdriver

import browser as brwsr
import config
import rabbit_amqp
from applicant import Applicant
from captcha_solver import CaptchaSolver
from exceptions import *
from rabbit_http import Rabbit as HttpRabbit
from timer import Timer

logger = logging.getLogger(__name__)


class Sender():
    def __init__(self, email: str) -> None:
        self.failed_email_user_id = 0
        self.bot_email = email
        self.queue_from_bot = email
        self.applicant = Applicant()
        self.loop = asyncio.get_event_loop()
        self.current_appeal: Optional[dict] = None
        self.stop_timer = Timer(self.stop_appeal_sending, self.loop)
        self.captcha_solver = CaptchaSolver()
        self.user_captcha_text: Optional[str] = None

    def sending_in_progress(self):
        return self.current_appeal is not None

    def send_to_bot(self) -> HttpRabbit:
        return HttpRabbit()

    async def process_new_appeal(self,
                                 message: aio_pika.IncomingMessage) -> None:
        success = True
        appeal = json.loads(message.body.decode("utf-8"))
        self.convert_recipient(appeal['appeal'])

        try:
            success = await self.async_process_new_appeal(appeal)
        except Exception:
            logger.exception('Что-то пошло не так')
            success = False

        if success:
            self.current_appeal = None
            self.failed_email_user_id = 0
            await message.ack()

            logger.info(f'Обращение обработано ' +
                        f'user_id: {appeal["user_id"]} ' +
                        f'appeal_id: {appeal["appeal_id"]}')
        else:
            logger.info('Попробуем отправить еще раз')
            await self.process_new_appeal(message)

    def convert_recipient(self, appeal: dict) -> None:
        department = appeal['police_department']
        appeal['police_subdepartment'] = None

        if department in config.DEPARTMENT_NAMES:
            appeal['police_department'] = config.DEPARTMENT_NAMES[department]
        elif department in config.MINSK_DEPARTMENT_NAMES:
            appeal['police_department'] = config.DEPARTMENT_NAMES[config.MINSK]

            appeal['police_subdepartment'] = \
                config.MINSK_DEPARTMENT_NAMES[department]

    async def solve_captcha(self, browser: webdriver.Remote) -> bool:
        appeal: dict = self.current_appeal or dict()
        email: str = self.get_value(appeal, 'sender_email', self.bot_email)

        if self.failed_email_user_id == appeal['user_id']:
            email = self.bot_email
            self.current_appeal['sender_email'] = None
            self.current_appeal['sender_email_password'] = ''

        logger.info(f"Достали имейл: {email}")

        proceed, success, captcha_text = await self.get_captcha_text(appeal,
                                                                     email,
                                                                     browser)

        if not proceed:
            return success

        proceed = await self.process_captcha(captcha_text,
                                             appeal['user_id'],
                                             appeal['appeal_id'],
                                             browser,
                                             silent=True)
        return proceed

    async def async_process_new_appeal(self, appeal: dict) -> bool:
        logger.info(f'Новое обращение: {pformat(appeal)}')
        self.current_appeal = appeal

        with brwsr.get_browser() as browser:
            if not await self.solve_captcha(browser):
                return False

            proceed, url = await self.get_appeal_url()

            if not proceed:
                return False

            return await self.send_appeal(url, browser)

    async def get_captcha_text(
            self,
            appeal: dict,
            email: str,
            browser: webdriver.Remote) -> Tuple[bool, bool, str]:
        try:
            captcha_solution = await self.recognize_captcha(email, browser)

            if captcha_solution is None:
                logger.info("Капча не распозналась =(")
                await self.send_captcha(appeal['appeal_id'],
                                        appeal['user_id'],
                                        email,
                                        browser)

                cancel, captcha_solution = \
                    await self.wait_for_input_or_cancel()

                if cancel:
                    return False, True, ''
            else:
                logger.info("Капча распозналась.")

            return True, True, captcha_solution
        except BrowserError:
            logger.info("Фейл браузинга")
            return False, False, ''
        except Exception:
            logger.exception('ОЙ get_captcha_text')
            return False, False, ''

    async def wait_for_input_or_cancel(self) -> Tuple[bool, str]:
        while True:
            if not self.sending_in_progress():
                return True, ''

            if self.user_captcha_text:
                text = self.user_captcha_text
                self.user_captcha_text = None
                return False, text

            await asyncio.sleep(2)

    async def send_captcha(self,
                           appeal_id: int,
                           user_id: int,
                           email: str,
                           browser: webdriver.Remote) -> None:
        captcha = self.applicant.get_png_captcha(email, browser)

        self.stop_timer.cock_it(config.CANCEL_TIMEOUT)

        try:
            await self.send_to_bot().send_captcha_url(captcha,
                                                      appeal_id,
                                                      user_id,
                                                      self.queue_from_bot)
        except ErrorWhilePutInQueue as exc:
            logger.error(exc.text)
            if exc.data:
                await self.send_to_bot().do_request(exc.data[0], exc.data[1])

    async def recognize_captcha(self,
                                email: str,
                                browser: webdriver.Remote) -> Optional[str]:
        svg_captcha = self.applicant.get_svg_captcha(email, browser)
        return await self.captcha_solver.solve(svg_captcha)

    async def process_bot_message(self,
                                  message: aio_pika.IncomingMessage) -> None:
        data = json.loads(message.body)
        logger.info(f'Сообщение от бота: {data}')
        email = self.get_value(data, 'sender_email', self.bot_email)
        logger.info(f"Достали имейл: {email}")
        user_id = data['user_id']
        appeal_id = data['appeal_id']

        # костыльчик пока бот не научится не хранить обращения, а парсить
        # бот уже научился, но убирать страшно, такие дела
        if not self.current_appeal \
                or self.current_appeal['user_id'] != user_id \
                or self.current_appeal['appeal_id'] != appeal_id:
            return

        if data['type'] == config.CAPTCHA_TEXT:
            self.stop_timer.delete()
            self.user_captcha_text = data['captcha_text']

        elif data['type'] == config.CANCEL:
            await self.stop_appeal_sending(local=True)

    async def process_captcha(self,
                              captcha_text: str,
                              user_id: int,
                              appeal_id: int,
                              browser: webdriver.Remote,
                              silent=False) -> bool:
        if self.applicant.enter_captcha_and_submit(
                captcha_text, browser) != config.OK:
            logger.info("Капча не подошла")
            return False

        if not silent:
            await self.send_to_bot().send_status(user_id,
                                                 config.CAPTCHA_OK,
                                                 self.queue_from_bot,
                                                 appeal_id,
                                                 self.current_appeal['appeal'])
        return True

    async def send_appeal(self, url: str, browser: webdriver.Remote) -> bool:
        try:
            status_code, message = self.applicant.send_appeal(
                self.current_appeal['appeal'], url, browser)

            if status_code != config.OK:
                logger.info(f"Ошибка при отправке - {message}")
                return False
        except BrowserError:
            logger.info("Фейл браузинга")
            return False
        except ErrorWhilePutInQueue as exc:
            logger.error(exc.text)
            if exc.data:
                await self.send_to_bot().do_request(exc.data[0], exc.data[1])
        except RancidAppeal:
            logger.info("Взяли протухшую форму обращения")
            proceed, url = await self.get_appeal_url()

            if not proceed:
                return False

            return await self.send_appeal(url, browser)
        except Exception:
            logger.exception('ОЙ send_appeal')
            return False

        await self.send_to_bot().send_status(self.current_appeal['user_id'],
                                             config.OK,
                                             self.queue_from_bot,
                                             self.current_appeal['appeal_id'],
                                             self.current_appeal['appeal'])
        return True

    async def get_appeal_url(self) -> Tuple[bool, str]:
        email = self.get_value(self.current_appeal, 'sender_email', None)

        password = self.get_value(self.current_appeal,
                                  'sender_email_password',
                                  config.EMAIL_PWD)

        if not email:
            email = self.bot_email
            password = config.EMAIL_PWD

        try:
            url = self.applicant.get_appeal_url(email, password)
            return True, url
        except NoMessageFromPolice:
            logger.info("Фейл почты. Не нашлось письмо.")
            return False, ''
        except AppealURLParsingFailed:
            logger.info("Не удалось распарсить урл из письма.")
            return False, ''
        except EmailLoginError as exc:
            logger.info(f'Не могу залогиниться {exc}')
            await self.maybe_tell_user_about_broken_email(email)
            return False, ''

    async def maybe_tell_user_about_broken_email(self, email: str):
        if email == self.bot_email:
            return

        self.failed_email_user_id = self.current_appeal['user_id']

        await self.send_to_bot().send_status(self.current_appeal['user_id'],
                                             config.BAD_EMAIL,
                                             self.queue_from_bot,
                                             self.current_appeal['appeal_id'],
                                             self.current_appeal['appeal'])

    async def start_sender(self, loop: AbstractEventLoop) -> None:
        appeals = rabbit_amqp.Rabbit(config.RABBIT_EXCHANGE_MANAGING,
                                     config.RABBIT_QUEUE_APPEAL,
                                     config.RABBIT_AMQP_ADDRESS,
                                     loop,
                                     "appeals")

        bot = rabbit_amqp.Rabbit(config.RABBIT_EXCHANGE_SENDING,
                                 self.queue_from_bot,
                                 config.RABBIT_AMQP_ADDRESS,
                                 loop,
                                 "bot_messages")

        asyncio.gather(bot.start(self.process_bot_message, passive=False),
                       appeals.start(self.process_new_appeal, passive=True),
                       self.stop_timer.start())

        logger.info(f"Воркер стартует.")

    async def stop_appeal_sending(self, local=False):
        logger.info(f"Останавливаем отправку обращения")
        if not local:
            await self.send_to_bot().send_sending_stopped(
                self.current_appeal['appeal_id'],
                self.current_appeal['user_id'],
                self.queue_from_bot
            )

        self.current_appeal = None
        self.user_captcha_text = None
        self.stop_timer.delete()
        logger.info("Отмена")

    def start(self):
        self.loop.run_until_complete(self.start_sender(self.loop))
        self.loop.run_forever()

    @classmethod
    def get_value(cls,
                  data: Optional[dict],
                  key: str,
                  default: Any = None) -> Any:
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
        logger.info('Суецыд')


def run_consuming(sender: Sender):
    try:
        sender.start()
    except Exception:
        logger.exception('ОЙ start')
        sender.stop()
        raise


def start(email: str):
    sender = Sender(email)
    run_consuming(sender)
