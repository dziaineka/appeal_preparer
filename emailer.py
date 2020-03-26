import pyzmail
import re
import regexps
from waiter import wait_decorator, wait
import config
from imapclient import IMAPClient
from exceptions import NoMessageFromPolice, AppealURLParsingFailed
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class Emailer:
    def __init__(self):
        self.re_appeal_url = re.compile(
            regexps.appeal_url,
            re.MULTILINE | re.IGNORECASE | re.VERBOSE)

    @contextmanager
    def imap(self, email: str, password: str):
        server = IMAPClient(config.IMAP_SERVER, use_uid=True, ssl=True)
        server.login(email, password)

        try:
            yield server
        finally:
            server.logout()

    def _extract_appeal_url(self, html: str) -> str:
        urls = self.re_appeal_url.findall(html)
        try:
            return urls[0][0].replace('amp;', '')
        except IndexError:
            logger.exception('ОЙ _extract_appeal_url')
            return ''

    def _search_mail_item(self, client, email) -> tuple:
        for folder in client.list_folders():
            client.select_folder(folder[2])
            unseen_messages = client.search(['TO', email, 'UNSEEN'])

            if not unseen_messages:
                unseen_messages = client.search(['TEXT', email, 'UNSEEN'])

            if not unseen_messages:
                unseen_messages = client.search(['UNSEEN'])

            raw_message = client.fetch(unseen_messages, ['BODY[]', 'FLAGS'])

            if unseen_messages:
                msg_num = unseen_messages[-1]
                return msg_num, raw_message

        raise IndexError("Can't find letter.")

    @wait_decorator(Exception, pause=1)
    def _get_messages(self, email: str, password: str) -> tuple:
        with self.imap(email, password) as client:
            return self._search_mail_item(client, email)

    def get_appeal_url(self, email: str, password: str) -> str:
        try:
            msg_num, raw_message = wait(IndexError,
                                        self._get_messages,
                                        2,
                                        None,
                                        email,
                                        password)
        except IndexError as exc:
            logger.info(f'ОЙ get_appeal_url - {str(exc)}')
            logger.exception(exc)
            raise NoMessageFromPolice('На почте не найдено письма от МВД.')

        message = pyzmail.PyzMessage.factory(raw_message[msg_num][b'BODY[]'])
        charset = message.html_part.charset
        html = message.html_part.get_payload().decode(charset)
        url = self._extract_appeal_url(html)

        if not url:
            raise AppealURLParsingFailed

        return url
