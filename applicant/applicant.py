from selenium import webdriver
from selenium.common.exceptions import \
    ElementClickInterceptedException, \
    WebDriverException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from applicant.mailbox import Mailbox
from applicant.waiter import wait_decorator
import requests
import applicant.config as config
from applicant.exceptions import *
from typing import Callable, Tuple
import time
import json


class Applicant:
    def __init__(self, logger):
        self.mailbox = Mailbox(logger)
        self.browser = None
        self.logger = logger

    def quit_browser(self):
        self.logger.info("Убиваем браузер")

        try:
            if self.browser:
                self.browser.quit()
        except WebDriverException as exc:
            self.logger.info(f'ОЙ quit_browser - {str(exc)}')
        except Exception as exc:
            self.logger.info(f'ОЙ quit_browser - {str(exc)}')
            self.logger.exception(exc)
            pass

    def get_browser(self):
        if self.browser:
            self.quit_browser()

        self.browser = webdriver.Remote(config.BROWSER_URL,
                                        DesiredCapabilities.FIREFOX)

        # self.browser = webdriver.Firefox()

        self.browser.implicitly_wait(10)  # seconds
        self.logger.info("Загрузили браузер")

    def make_visible(self, element) -> None:
        # returns dict of X, Y coordinates
        coordinates = element.location_once_scrolled_into_view

        self.browser.execute_script(
            f'window.scrollTo({coordinates["x"]}, {coordinates["y"]});')

    def _extract_status_captcha(self, element) -> Tuple[str, str]:
        text = element.text.lower()

        self.logger.info(f'_extract_status_captcha - {text}')

        if text == 'неверный ответ':
            return config.WRONG_INPUT, text
        elif 'выслано письмо со ссылкой' in text:
            return config.OK, text
        else:
            return config.FAIL, text

    def _extract_status_sending(self, element) -> Tuple[str, str]:
        text = element.text.lower().strip()

        self.logger.info(f'_extract_status_sending - {text}')

        if 'ваше обращение отправлено' in text:
            return config.OK, text
        else:
            # self.browser.save_screenshot('extract_status_sending.png')
            return config.FAIL, text

    def _extract_status_appeal(self, element) -> Tuple[str, str]:
        text = element.text.lower().strip()
        self.logger.info(f'_extract_status_appeal - {text}')
        return config.OK, text

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

        submit_button_xpath = \
            '//div[@class="col-sm-6"]/button[contains(@class, "md-primary")]'

        self.click_button(submit_button_xpath,
                          '//div[@id="info-message"]/p')

        self.logger.info("Нажали сабмит капчи")

        submit_status, status_text = self.get_popup_info(
            self._extract_status_captcha)

        self.logger.info(f'Достали статус {status_text}')

        if submit_status == config.WRONG_INPUT:
            # self.browser.save_screenshot('WRONG_INPUT.png')
            status = config.WRONG_INPUT
        elif submit_status != config.OK:
            # self.browser.save_screenshot('FAIL.png')
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

    @wait_decorator(Exception, pause=0.5, exception_to_raise=BrowserError)
    def _get_element_by_class(self, element_class: str):
        return self.browser.find_element_by_class_name(element_class)

    @wait_decorator(Exception, pause=0.5, exception_to_raise=BrowserError)
    def _get_element_by_id(self, element_id: str):
        return self.browser.find_element_by_id(element_id)

    @wait_decorator(Exception, pause=0.5, exception_to_raise=BrowserError)
    def _get_element_by_xpath(self, xpath: str):
        return self.browser.find_element_by_xpath(xpath)

    @wait_decorator(ElementClickInterceptedException)
    def get_png_captcha(self, email: str) -> str:
        self.get_browser()
        self._get_captcha_site(email)
        self.logger.info("Загрузили сайт с капчей")
        return self._upload_captcha()

    @wait_decorator(ElementClickInterceptedException)
    def get_svg_captcha(self, email: str) -> str:
        self.get_browser()
        self._get_captcha_site(email)
        self.logger.info("Загрузили сайт с капчей")
        return self._get_captcha_svg()

    def _get_captcha_svg(self) -> str:
        web_elements = self.browser.find_elements_by_xpath(
            '//div[@class="col-sm-6"]/div[2]/*[name()="svg"]/*[name()="path"]')

        html_elements = map(lambda element: element.get_attribute('outerHTML'),
                            web_elements)

        purified_svg_elements = filter(
            lambda element: 'fill="none"' not in element,
            html_elements)

        svg_image = ""
        svg_image += ('<svg xmlns="http://www.w3.org/2000/svg" ' +
                      'width="150" height="50" viewBox="0,0,150,50">')
        for element in purified_svg_elements:
            svg_image += element
        svg_image += "</svg>"

        return svg_image

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
            self.get_browser()
            self.browser.get(url)
            self.logger.info("Загрузили сайт с формой обращения")

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

            recipient_select_field_xpath = \
                '//md-select[@ng-model="appeal.division"]'

            division_xpath = '//div[@id="select_container_10"]/' + \
                'md-select-menu/md-content/' + \
                'md-option[starts-with(@id,"select_option_")]/' + \
                f'div[@class="md-text"]/span[.="{data["police_department"]}"]'

            self.click_button(recipient_select_field_xpath,
                              division_xpath,
                              ElementClickInterceptedException)

            zipcode_xpath = '//input[@ng-model="appeal.postal_code"]'

            self.click_button(division_xpath, zipcode_xpath)

            self.logger.info("Выбрали отдел ГУВД")

            zipcode = self._get_element_by_xpath(zipcode_xpath)
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
            self.enter_appeal('//textarea[@ng-model="appeal.text"]',
                              data['text'])
            self._fill_field(text, " ")

            self.logger.info("Ввели текст")

            self.attach_photos(data['violation_photo_files_paths'])

            submit_button_xpath = '//div[@class="col-sm-6 text-center"]/' + \
                                  'button[contains(@class, "md-primary")]'

            if config.ALLOW_SENDING:
                self.click_button(submit_button_xpath,
                                  '//div[@id="info-message"]/p')

                self.logger.info("Отправили")

                submit_status, status_text = self.get_popup_info(
                    self._extract_status_sending)

                if submit_status != config.OK:
                    return config.FAIL, status_text
        except ElementClickInterceptedException as exc:
            # let's try to get error message
            status, status_text = self.get_popup_info(
                self._extract_status_appeal,
                max_attempts=6)

            if status == config.OK:
                self.logger.info(status_text)
                raise RancidAppeal

            raise exc
        except Exception as exc:
            self.logger.info(f'ОЙ send_appeal - {str(exc)}')
            self.logger.exception(exc)
            return config.FAIL, str(exc)

        self.logger.info("Успех")
        return config.OK, ''

    def click_button(self, button_xpath: str,
                     next_elem_xpath: str,
                     exc=None):
        sended = False
        tries = 5

        while not sended:
            try:
                button = self._get_element_by_xpath(button_xpath)
                self.make_visible(button)
                button.click()
                self.browser.find_element_by_xpath(next_elem_xpath)
                sended = True
            except Exception:
                self.logger.exception("click_button")

                if tries:
                    sended = False
                    tries -= 1
                else:
                    if exc:
                        raise exc
                    else:
                        sended = True

    @wait_decorator(Exception, pause=0.5, exception_to_raise=BrowserError)
    def enter_appeal(self, xpath: str, appeal_text: str):
        text_for_js = json.dumps(appeal_text, ensure_ascii=False)

        self.browser.execute_script(
            f'document.getElementById("input_20").value={text_for_js};')

    def get_popup_info(self,
                       extractor: Callable,
                       max_attempts: int = 15) -> Tuple[str, str]:
        text = ''
        counter = 0
        infobox = None

        while not text:
            self.logger.info(f'Попытка взять текст попапа {counter}')

            if counter > max_attempts:
                self.logger.error('Нет попапа')
                self.browser.save_screenshot(
                    '/tmp/temp_files_parkun/get_popup_info_error.png')
                raise BrowserError

            try:
                infobox = self._get_element_by_xpath(
                    '//div[@id="info-message"]/p')
            except Exception:
                self.browser.save_screenshot(
                    '/tmp/temp_files_parkun/get_popup_info_error1.png')
                self.logger.exception("get_popup_info exc")

            text = infobox.text.strip()
            counter += 1
            time.sleep(2)

        return extractor(infobox)

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
