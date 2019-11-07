# RabbitMQ
RABBIT_HOST = 'localhost'
RABBIT_LOGIN = 'appeal_preparer'
RABBIT_PASSWORD = 'appeal_preparer'
RABBIT_ADDRESS = f'http://{RABBIT_LOGIN}:{RABBIT_PASSWORD}@localhost:15672'
RABBIT_EXCHANGE_APPEAL = 'appeal'
RABBIT_ROUTING_TO_BOT = 'to_bot'
RABBIT_ROUTING_STATUS = 'appeal_status'
RABBIT_ROUTING_APPEAL_URL = 'appeal_url'

# appeal status codes
OK = 'ok'
FAIL = 'fail'
WRONG_INPUT = 'wrong_input'
CAPTCHA = 'captcha'
CAPTCHA_URL = 'captcha_url'
CAPTCHA_OK = 'captcha_ok'
CAPTCHA_FAIL = 'captcha_fail'

# message types
CAPTCHA_TEXT = 'captcha_text'
GET_CAPTCHA = 'get_captcha'
APPEAL = 'appeal'
CANCEL = 'cancel'

# appeals email
EMAIL_PWD = "password"

EMAILS = [
    'mail1@example.com',
    'mail2@example.com',
    'mail3@example.com',
    'mail4@example.com',
    'mail5@example.com',
    'mail6@example.com',
    'mail7@example.com',
    'mail8@example.com',
    'mail9@example.com',
]
