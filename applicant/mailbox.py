import pyzmail
import re
import applicant.regexps as regexps
import applicant.waiter as waiter
import applicant.config as config
from imapclient import IMAPClient
from applicant.exceptions import NoMessageFromPolice


class Mailbox:
    def __init__(self):
        self.re_appeal_url = re.compile(
            regexps.appeal_url,
            re.MULTILINE | re.IGNORECASE | re.VERBOSE)

        self.server = IMAPClient(config.IMAP_SERVER, use_uid=True, ssl=True)
        self.server.login(config.EMAIL, config.PWD)
        self.server.select_folder('Appeals')

    def _extract_appeal_url(self, html: str) -> str:
        urls = self.re_appeal_url.findall(html)
        try:
            return urls[0][0].replace('amp;', '')
        except IndexError:
            return ''

    def _get_messages(self, email: str) -> tuple:
        unseen_messages = self.server.search([u'UNSEEN', u'TEXT', email])
        raw_message = self.server.fetch(unseen_messages, ['BODY[]', 'FLAGS'])
        msg_num = unseen_messages[0]
        return msg_num, raw_message

    def get_appeal_url(self, email: str) -> str:
        try:
            msg_num, raw_message = waiter.wait(IndexError,
                                               self._get_messages,
                                               2,
                                               email)
        except IndexError:
            raise NoMessageFromPolice('На почте не найдено письма от МВД.')
        except ConnectionResetError or BrokenPipeError:
            raise NoMessageFromPolice('Ошибка при подключении к ящику.')

        message = pyzmail.PyzMessage.factory(raw_message[msg_num][b'BODY[]'])
        charset = message.html_part.charset
        html = message.html_part.get_payload().decode(charset)
        url = self._extract_appeal_url(html)  # fail check needed
        return url
