from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementClickInterceptedException
from applicant.mailbox import Mailbox
from applicant.waiter import wait_decorator
import requests
import applicant.config as config
from applicant.exceptions import *
import time


class Applicant:
    def __init__(self, logger):
        self.mailbox = Mailbox(logger)
        self.browser = None
        self.logger = logger

    def cancel(self):
        self.logger.info("Убиваем браузер")

        try:
            if self.browser:
                self.browser.quit()
        except Exception as exc:
            self.logger.info(f'ОЙ cancel - {str(exc)}')
            self.logger.exception(exc)
            pass

    def _get_browser(self):
        chrome_options = Options()

        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1080,1920")
        self.browser = webdriver.Chrome(options=chrome_options)
        # self.browser = webdriver.Chrome()
        self.browser.implicitly_wait(10)  # seconds

    def make_visible(self, element) -> None:
        # returns dict of X, Y coordinates
        coordinates = element.location_once_scrolled_into_view

        self.browser.execute_script(
            f'window.scrollTo({coordinates["x"]}, {coordinates["y"]});')

    def _extract_status_captcha(self, element) -> str:
        text = element.text.lower()

        self.logger.info(text)

        if text == 'неверно введена капча':
            return config.WRONG_INPUT
        elif 'выслано письмо со ссылкой' in text:
            return config.OK
        else:
            return config.FAIL

    def _extract_status_appeal(self, element) -> (str, str):
        text = element.text.lower().strip()

        self.logger.info(f'_extract_status_appeal - {text}')

        if 'ваше обращение отправлено' in text:
            return config.OK, text
        else:
            self.browser.save_screenshot('extract_status_appeal.png')
            return config.FAIL, text

    def _upload_captcha(self) -> str:
        captcha = self._get_element_by_xpath(
            '//div[@class="col-sm-6"]/div[2]/*[name()="svg"]')

        upload_url = 'https://telegra.ph/upload'
        files = {'file': ('file', captcha.screenshot_as_png, 'image/png')}
        result = requests.post(upload_url, files=files).json()
        self.logger.info("Нашли урл капчи")
        return f'https://telegra.ph{result[0]["src"]}'

    def enter_captcha_and_submit(self, captcha_text: str) -> str:
        if not self.browser:
            return config.FAIL

        captcha_field = self._get_element_by_id("captcha")
        self.make_visible(captcha_field)
        self._fill_field(captcha_field, captcha_text)

        submit_button = self._get_element_by_xpath(
            '//div[@class="col-sm-6"]/button[contains(@class, "md-primary")]')

        self.make_visible(submit_button)
        submit_button.click()

        self.logger.info("Нажали сабмит капчи")

        time.sleep(1)

        submit_status = self._extract_status_captcha(
            self._get_element_by_xpath('//div[@id="info-message"]/p'))

        self.logger.info(f'Достали статус {submit_status}')

        if submit_status == config.WRONG_INPUT:
            self.browser.save_screenshot('WRONG_INPUT.png')
            status = config.WRONG_INPUT
        elif submit_status != config.OK:
            self.browser.save_screenshot('FAIL.png')
            status = config.FAIL
        else:
            status = config.OK

        self.browser.quit()
        return status

    def _get_captcha_site(self, email: str) -> None:
        self.browser.get('https://minsk.mvd.gov.by/ru/electronicAppealLogin')

        email_field = self._get_element_by_id("email")
        self.make_visible(email_field)
        self._fill_field(email_field, email)
        self.logger.info("Заполнили емаил")

        rules_acception = self._get_element_by_class("md-container")
        self.make_visible(rules_acception)
        rules_acception.click()
        self.logger.info("Кликнули на галку")

    def get_appeal_url(self, email: str, password: str) -> str:
        return self.mailbox.get_appeal_url(email, password)

    def _fill_field(self, field, text):
        self.logger.info('Заполняем поле')
        try:
            field.send_keys(text)
        except Exception as exc:
            self.logger.info(f'ОЙ _fill_field - {str(exc)}')
            self.logger.exception(exc)
            field.send_keys(text)

    def _get_element_by_class(self, element_class: str):
        try:
            return self.browser.find_element_by_class_name(element_class)
        except Exception as exc:
            self.logger.info(f'ОЙ _get_element_by_class - {str(exc)}')
            self.logger.exception(exc)
            self.browser.save_screenshot('get_element_by_class.png')
            raise BrowserError()

    def _get_element_by_id(self, element_id: str):
        try:
            return self.browser.find_element_by_id(element_id)
        except Exception as exc:
            self.logger.info(f'ОЙ _get_element_by_id - {str(exc)}')
            self.logger.exception(exc)
            self.browser.save_screenshot('get_element_by_id.png')
            raise BrowserError()

    def _get_element_by_xpath(self, xpath: str):
        try:
            return self.browser.find_element_by_xpath(xpath)
        except Exception as exc:
            self.logger.info(f'ОЙ _get_element_by_xpath - {str(exc)}')
            self.logger.exception(exc)
            self.browser.save_screenshot('get_element_by_xpath.png')
            raise BrowserError()

    @wait_decorator(ElementClickInterceptedException)
    def get_captcha(self, email: str) -> str:
        self.cancel()
        self._get_browser()
        self.logger.info("Загрузили браузер")
        self._get_captcha_site(email)
        self.logger.info("Загрузили сайт")
        return self._upload_captcha()

    @wait_decorator(ElementClickInterceptedException)
    def request_appeal_url(self, email: str, password: str) -> str:
        self._get_captcha_site(email)

        captcha = input("Captcha: ")

        if self.enter_captcha_and_submit(captcha) != config.OK:
            self.request_appeal_url(email, password)

        return self.mailbox.get_appeal_url(email, password)

    @wait_decorator(ElementClickInterceptedException)
    def send_appeal(self, data: dict, url: str) -> tuple:
        try:
            self._get_browser()
            self.browser.get(url)

            self.logger.info("Получили браузер")

            last_name_field = self._get_element_by_xpath(
                '//input[@data-ng-model="appeal.last_name"]')

            self.make_visible(last_name_field)
            self._fill_field(last_name_field, data['sender_last_name'])

            self.logger.info("Ввели фамилию")

            first_name_field = self._get_element_by_xpath(
                '//input[@data-ng-model="appeal.first_name"]')
            self.make_visible(first_name_field)
            self._fill_field(first_name_field, data['sender_first_name'])

            self.logger.info("Ввели имя")

            patronymic_name_field = self._get_element_by_xpath(
                '//input[@ng-model="appeal.middle_name"]')
            self.make_visible(patronymic_name_field)
            self._fill_field(patronymic_name_field, data['sender_patronymic'])

            self.logger.info("Ввели отчество")

            recipient_select_field = self._get_element_by_xpath(
                '//md-select[@ng-model="appeal.division"]')
            self.make_visible(recipient_select_field)
            recipient_select_field.click()

            time.sleep(1)

            division = self._get_element_by_xpath(
                '//div[@id="select_container_10"]/' +
                'md-select-menu/md-content/' +
                'md-option[starts-with(@id,"select_option_")]/' +
                f'div[@class="md-text"]/span[.="{data["police_department"]}"]')

            self.make_visible(division)
            division.click()

            time.sleep(1)

            self.logger.info("Выбрали отдел ГУВД")

            zipcode = self._get_element_by_xpath(
                '//input[@ng-model="appeal.postal_code"]')
            self.make_visible(zipcode)
            self._fill_field(zipcode, data['sender_zipcode'])

            self.logger.info("Ввели индекс")

            city = self._get_element_by_xpath(
                '//input[@ng-model="appeal.city"]')
            self.make_visible(city)
            self._fill_field(city, data['sender_city'])

            self.logger.info("Ввели город")

            street = self._get_element_by_xpath(
                '//input[@ng-model="appeal.street"]')
            self.make_visible(street)
            self._fill_field(street, data['sender_street'])

            self.logger.info("Ввели улицу")

            building = self._get_element_by_xpath(
                '//input[@ng-model="appeal.house"]')
            self.make_visible(building)
            self._fill_field(building, data['sender_house'])

            self.logger.info("Ввели дом")

            block = self._get_element_by_xpath(
                '//input[@ng-model="appeal.korpus"]')
            self.make_visible(block)
            self._fill_field(block, data['sender_block'])

            self.logger.info("Ввели корпус")

            flat = self._get_element_by_xpath(
                '//input[@ng-model="appeal.flat"]')
            self.make_visible(flat)
            self._fill_field(flat, data['sender_flat'])

            self.logger.info("Ввели квартиру")

            text = self._get_element_by_xpath(
                '//textarea[@ng-model="appeal.text"]')
            self.make_visible(text)
            self._fill_field(text, data['text'])

            self.logger.info("Ввели текст")

            self.attach_photos(data['violation_photo_files_paths'])

            submit_button = self._get_element_by_xpath(
                '//div[@class="col-sm-6 text-center"]/' +
                'button[contains(@class, "md-primary")]')

            self.make_visible(submit_button)
            submit_button.click()

            self.logger.info("Отправили")

            submit_status, status_text = self.get_submit_status()

            if submit_status != config.OK:
                return config.FAIL, status_text
        except ElementClickInterceptedException as exc:
            self.browser.save_screenshot(
                'ElementClickInterceptedException.png')

            raise exc
        except Exception as exc:
            self.logger.info(f'ОЙ send_appeal - {str(exc)}')
            self.logger.exception(exc)
            return config.FAIL, str(exc)
        finally:
            self.browser.quit()

        self.logger.info("Успех")
        return config.OK, ''

    def get_submit_status(self) -> (str, str):
        text = ''
        counter = 0
        infobox = None

        while not text:
            self.logger.error(f'Попытка взять статус отправки {counter}')

            if counter > 5:
                self.logger.error('Нет сообщения со статусом отправки')
                self.browser.save_screenshot('get_submit_status_error.png')
                raise BrowserError

            infobox = self._get_element_by_xpath('//div[@id="info-message"]/p')
            text = infobox.text.strip()
            counter += 1
            time.sleep(1)

        return self._extract_status_appeal(infobox)

    def attach_photos(self, photo_paths: list) -> None:
        attach_field = self._get_element_by_xpath("//input[@type=\"file\"]")
        label = attach_field.find_element_by_xpath("./..")

        js = "arguments[0].style.height='100px'; \
            arguments[0].style.width='100px'; \
            arguments[0].style.overflow='visible'; \
            arguments[0].style.visibility='visible'; \
            arguments[0].style.opacity = 1"

        self.browser.execute_script(js, label)

        for path in photo_paths:
            try:
                self._fill_field(attach_field, path)
            except Exception as exc:
                self.logger.info(f'Фотка не прикрепляется {path} - {str(exc)}')

        self.logger.info("Прикрепили файлы")
