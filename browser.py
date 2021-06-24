import logging
from contextlib import contextmanager

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

logger = logging.getLogger(__name__)


def create_browser() -> webdriver.Remote:
    try:
        # browser = webdriver.Remote(config.BROWSER_URL,
        #                            config.BROWSER_CAPABILITIES)

        geckodriver_path = \
            r'/usr/local/bin/geckodriver'

        browser = webdriver.Firefox(
            executable_path=geckodriver_path)

        browser.implicitly_wait(20)  # seconds

        logger.info("Загрузили браузер")
        return browser
    except TimeoutException:
        logger.info("Не загрузили браузер")
        raise


@contextmanager
def get_browser():
    browser = create_browser()

    try:
        yield browser
    finally:
        browser.quit()


def create_window(browser: webdriver.Remote) -> webdriver.Remote:
    windows_before = browser.window_handles
    browser.execute_script("window.open('');")

    WebDriverWait(browser, 10).until(
        EC.number_of_windows_to_be(len(windows_before) + 1)
    )

    windows_after = browser.window_handles
    new_windows = set(windows_after) - set(windows_before)
    browser.switch_to.window(new_windows.pop())
    return browser


# with get_browser() as browser:
#     browser.get("https://google.com")
#     browser = create_window(browser)
#     browser.get("https://nn.by")

# print("stop")
