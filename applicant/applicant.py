from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementClickInterceptedException
from applicant.mailbox import Mailbox
from applicant.waiter import wait_decorator
import requests
import applicant.config as config
import time


class Applicant:
    def __init__(self, logger, address: str = config.EMAIL):

        self.address = address
        self.mailbox = Mailbox()
        self.browser = None
        self.logger = logger

    def cancel(self):
        try:
            self.browser.quit()
        except:
            pass

    def _get_browser(self):
        chrome_options = Options()

        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1080,1920")
        self.browser = webdriver.Chrome(options=chrome_options)
        # self.browser = webdriver.Chrome()
        self.browser.implicitly_wait(20)  # seconds

    def make_visible(self, element) -> None:
        # returns dict of X, Y coordinates
        coordinates = element.location_once_scrolled_into_view

        self.browser.execute_script(
            f'window.scrollTo({coordinates["x"]}, {coordinates["y"]});')

    def _extract_status_captcha(self, element) -> str:
        text = element.text.lower()

        if text == 'неверно введена капча':
            return config.WRONG_INPUT
        elif 'выслано письмо со ссылкой' in text:
            return config.OK
        else:
            return config.FAIL

    def _extract_status_appeal(self, element) -> str:
        text = element.text.lower()

        if 'ваше обращение отправлено' in text:
            return config.OK
        else:
            return config.FAIL

    def _upload_captcha(self) -> str:
        captcha = self.browser.find_element_by_xpath(
            '//div[@class="col-sm-6"]/div[2]/*[name()="svg"]')

        upload_url = 'https://telegra.ph/upload'
        files = {'file': ('file', captcha.screenshot_as_png, 'image/png')}
        result = requests.post(upload_url, files=files).json()
        return f'https://telegra.ph{result[0]["src"]}'

    def enter_captcha_and_submit(self, captcha_text: str) -> str:
        captcha_field = self.browser.find_element_by_id("captcha")
        self.make_visible(captcha_field)
        captcha_field.send_keys(captcha_text)

        submit_button = self.browser.find_element_by_xpath(
            '//div[@class="col-sm-6"]/button[contains(@class, "md-primary")]')

        self.make_visible(submit_button)
        submit_button.click()

        time.sleep(1)

        submit_status = self._extract_status_captcha(
            self.browser.find_element_by_xpath('//div[@id="info-message"]/p'))

        self.browser.quit()

        if submit_status == config.WRONG_INPUT:
            return config.WRONG_INPUT
        elif submit_status != config.OK:
            return config.FAIL

        return config.OK

    def _get_captcha_site(self) -> None:
        self.browser.get('https://minsk.mvd.gov.by/ru/electronicAppealLogin')

        email_field = self.browser.find_element_by_id("email")
        self.make_visible(email_field)
        email_field.send_keys(self.address)

        rules_acception = self.browser.find_element_by_class_name(
                                                            "md-container")

        self.make_visible(rules_acception)
        rules_acception.click()

    def get_appeal_url(self, email: str) -> str:
        return self.mailbox.get_appeal_url(email)

    @wait_decorator(ElementClickInterceptedException)
    def get_captcha(self) -> str:
        self._get_browser()
        self._get_captcha_site()
        return self._upload_captcha()

    @wait_decorator(ElementClickInterceptedException)
    def request_appeal_url(self, email: str) -> str:
        self._get_captcha_site()

        captcha = input("Captcha: ")

        if self.enter_captcha_and_submit(captcha) != config.OK:
            self.request_appeal_url(email)

        return self.mailbox.get_appeal_url(email)

    @wait_decorator(ElementClickInterceptedException)
    def send_appeal(self, data: dict, url: str) -> tuple:
        try:
            self._get_browser()
            self.browser.get(url)

            self.logger.info("Получили браузер")

            last_name_field = self.browser.find_element_by_xpath(
                '//input[@data-ng-model="appeal.last_name"]')

            self.make_visible(last_name_field)
            last_name_field.send_keys(data['sender_last_name'])

            self.logger.info("Ввели фамилию")

            first_name_field = self.browser.find_element_by_xpath(
                '//input[@data-ng-model="appeal.first_name"]')
            self.make_visible(first_name_field)
            first_name_field.send_keys(data['sender_first_name'])

            self.logger.info("Ввели имя")

            patronymic_name_field = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.middle_name"]')
            self.make_visible(patronymic_name_field)
            patronymic_name_field.send_keys(data['sender_patronymic'])

            self.logger.info("Ввели отчество")

            recipient_select_field = self.browser.find_element_by_xpath(
                '//md-select[@ng-model="appeal.division"]')
            self.make_visible(recipient_select_field)
            recipient_select_field.click()

            division = self.browser.find_element_by_xpath(
                '//div[@id="select_container_10"]/' +
                'md-select-menu/md-content/' +
                'md-option[starts-with(@id,"select_option_")]/' +
                f'div[@class="md-text"]/span[.="{data["police_department"]}"]')

            self.make_visible(division)
            division.click()

            self.logger.info("Выбрали отдел ГУВД")

            zipcode = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.postal_code"]')
            self.make_visible(zipcode)
            zipcode.send_keys(data['sender_zipcode'])

            self.logger.info("Ввели индекс")

            city = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.city"]')
            self.make_visible(city)
            city.send_keys(data['sender_city'])

            self.logger.info("Ввели город")

            street = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.street"]')
            self.make_visible(street)
            street.send_keys(data['sender_street'])

            self.logger.info("Ввели улицу")

            building = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.house"]')
            self.make_visible(building)
            building.send_keys(data['sender_house'])

            self.logger.info("Ввели дом")

            block = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.korpus"]')
            self.make_visible(block)
            block.send_keys(data['sender_block'])

            self.logger.info("Ввели корпус")

            flat = self.browser.find_element_by_xpath(
                '//input[@ng-model="appeal.flat"]')
            self.make_visible(flat)
            flat.send_keys(data['sender_flat'])

            self.logger.info("Ввели квартиру")

            text = self.browser.find_element_by_xpath(
                '//textarea[@ng-model="appeal.text"]')
            self.make_visible(text)
            text.send_keys(data['text'])

            self.logger.info("Ввели текст")

            submit_button = self.browser.find_element_by_xpath(
                '//div[@class="col-sm-6 text-center"]/' +
                'button[contains(@class, "md-primary")]')

            self.make_visible(submit_button)
            submit_button.click()

            self.logger.info("Отправили")

            time.sleep(1)

            infobox = self.browser.find_element_by_xpath(
                '//div[@id="info-message"]/p')

            submit_status = self._extract_status_appeal(infobox)

            if submit_status != config.OK:
                return config.FAIL, infobox.text
        except Exception as exc:
            return config.FAIL, str(exc)
        finally:
            self.browser.quit()

        return config.OK, ''
