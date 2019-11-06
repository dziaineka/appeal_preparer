import pyzmail
import re
import applicant.regexps as regexps
import applicant.waiter as waiter
import applicant.config as config
from imapclient import IMAPClient
from applicant.exceptions import NoMessageFromPolice
from contextlib import contextmanager


class Mailbox:
    def __init__(self, logger):
        self.re_appeal_url = re.compile(
            regexps.appeal_url,
            re.MULTILINE | re.IGNORECASE | re.VERBOSE)

        self.logger = logger

    @contextmanager
    def imap(self, *args, **kwds):
        server = IMAPClient(config.IMAP_SERVER, use_uid=True, ssl=True)
        server.login(config.EMAIL, config.PWD)
        server.select_folder('Appeals')

        try:
            yield server
        finally:
            server.logout()

    def _extract_appeal_url(self, html: str) -> str:
        urls = self.re_appeal_url.findall(html)
        try:
            return urls[0][0].replace('amp;', '')
        except IndexError as exc:
            self.logger.info(f'ОЙ _extract_appeal_url - {str(exc)}')
            self.logger.exception(exc)
            return ''

    def _get_messages(self, email: str) -> tuple:
        try:
            with self.imap() as client:
                unseen_messages = client.search(['TO', email, 'UNSEEN'])

                if not unseen_messages:
                    unseen_messages = client.search(['TEXT', email, 'UNSEEN'])

                if not unseen_messages:
                    unseen_messages = client.search(['UNSEEN'])

                raw_message = client.fetch(unseen_messages,
                                           ['BODY[]', 'FLAGS'])
        except ConnectionResetError or BrokenPipeError as exc:
            self.logger.info(f'ОЙ _get_messages - {str(exc)}')
            self.logger.exception(exc)
            self._get_messages(email)

        msg_num = unseen_messages[-1]
        return msg_num, raw_message

    def get_appeal_url(self, email: str) -> str:
        try:
            msg_num, raw_message = waiter.wait(IndexError,
                                               self._get_messages,
                                               2,
                                               email)
        except IndexError as exc:
            self.logger.info(f'ОЙ get_appeal_url - {str(exc)}')
            self.logger.exception(exc)
            raise NoMessageFromPolice('На почте не найдено письма от МВД.')

        message = pyzmail.PyzMessage.factory(raw_message[msg_num][b'BODY[]'])
        charset = message.html_part.charset
        html = message.html_part.get_payload().decode(charset)
        url = self._extract_appeal_url(html)  # fail check needed
        return url
