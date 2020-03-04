# RabbitMQ
RABBIT_HOST = 'localhost'
RABBIT_AMQP_PORT = '5672'
RABBIT_LOGIN = 'appeal_sender'
RABBIT_PASSWORD = 'appeal_sender'
RABBIT_ADDRESS = f'http://{RABBIT_LOGIN}:{RABBIT_PASSWORD}@{RABBIT_HOST}:15672'

RABBIT_AMQP_ADDRESS = \
    f'amqp://{RABBIT_LOGIN}:{RABBIT_PASSWORD}@{RABBIT_HOST}:{RABBIT_AMQP_PORT}'

RABBIT_EXCHANGE_MANAGING = 'managing'
RABBIT_EXCHANGE_SENDING = 'sending'
RABBIT_ROUTING_STATUS = 'appeal_sending_status'
RABBIT_ROUTING_AVAILABILITY = 'sender_availability'
RABBIT_ROUTING_APPEAL = 'appeal_to_queue'
RABBIT_QUEUE_APPEAL = 'appeal'
RABBIT_QUEUE_TO_BOT = 'sending_status'

# sender statuses
FREE_WORKER = 'free_worker'
BUSY_WORKER = 'busy_worker'

# captcha solver
CAPTCHA_SOLVER_HOST = 'http://localhost:5000'

# email busy list
BUSY_LIST = 'email_busy_list'

# cancel timer
CANCEL_TIMEOUT = 40  # seconds
TIMEOUT_MESSAGE = 'times_up'

# appeal status codes
OK = 'ok'
FAIL = 'fail'
WRONG_INPUT = 'wrong_input'
CAPTCHA = 'captcha'
CAPTCHA_URL = 'captcha_url'
CAPTCHA_OK = 'captcha_ok'
CAPTCHA_FAIL = 'captcha_fail'
FREE_WORKER = 'free_worker'
BUSY_WORKER = 'busy_worker'

# message types
CAPTCHA_TEXT = 'captcha_text'
SENDING_CANCELLED = 'sending_cancelled'
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
