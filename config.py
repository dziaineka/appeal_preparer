from os import getenv
from os.path import join, dirname
from dotenv import load_dotenv

# Create .env file path.
dotenv_path = join(dirname(__file__), ".env")

# Load file from the path.
load_dotenv(dotenv_path)

# RabbitMQ
RABBIT_HOST = getenv("RABBIT_HOST", "localhost")
RABBIT_AMQP_PORT = getenv("RABBIT_AMQP_PORT", "5672")
RABBIT_HTTP_PORT = getenv("RABBIT_HTTP_PORT", "15672")
RABBIT_LOGIN = getenv("RABBIT_LOGIN", "appeal_sender")
RABBIT_PASSWORD = getenv("RABBIT_PASSWORD", "appeal_sender")

RABBIT_ADDRESS = \
    f'http://{RABBIT_LOGIN}:{RABBIT_PASSWORD}@{RABBIT_HOST}:{RABBIT_HTTP_PORT}'

RABBIT_AMQP_ADDRESS = \
    f'amqp://{RABBIT_LOGIN}:{RABBIT_PASSWORD}@{RABBIT_HOST}:{RABBIT_AMQP_PORT}'

RABBIT_EXCHANGE_MANAGING = 'managing'
RABBIT_EXCHANGE_SENDING = 'sending'
RABBIT_ROUTING_STATUS = 'appeal_sending_status'
RABBIT_ROUTING_AVAILABILITY = 'sender_availability'
RABBIT_ROUTING_APPEAL = 'appeal_to_queue'
RABBIT_QUEUE_APPEAL = 'appeal'

# captcha solver
CAPTCHA_SOLVER_HOST = getenv("CAPTCHA_SOLVER_HOST", "http://localhost:5000")
CAPTCHA_SOLVER_PATH = '/solve'

# cancel timer
CANCEL_TIMEOUT = 40  # seconds
TIMEOUT_MESSAGE = 'times_up'

# appeal status codes
OK = 'ok'
FAIL = 'fail'
WRONG_INPUT = 'wrong_input'
CAPTCHA_URL = 'captcha_url'
CAPTCHA_OK = 'captcha_ok'
BAD_EMAIL = 'bad_email'

# message types
CAPTCHA_TEXT = 'captcha_text'
SENDING_CANCELLED = 'sending_cancelled'
CANCEL = 'cancel'

# appeals email
EMAIL_PWD = getenv("EMAIL_PWD", "password")

default_emails = "mail1@example.com;;" + \
    "mail2@example.com;;" + \
    "mail3@example.com;;" + \
    "mail4@example.com;;" + \
    "mail5@example.com;;" + \
    "mail6@example.com;;" + \
    "mail7@example.com;;" + \
    "mail8@example.com;;" + \
    "mail9@example.com;;"

EMAILS = getenv("EMAILS", default_emails).split(";;")

IMAP_SERVER = "imap-mail.outlook.com"

# Recipients
CENTRALNY = 'centralny'
SAVIECKI = 'saviecki'
PIERSAMAJSKI = 'piersamajski'
PARTYZANSKI = 'partyzanski'
ZAVODSKI = 'zavodski'
LENINSKI = 'leninski'
KASTRYCNICKI = 'kastrycnicki'
MASKOUSKI = 'maskouski'
FRUNZIENSKI = 'frunzienski'
MINSK = 'minsk'
BREST_REGION = 'brest_region'
VITSEBSK_REGION = 'vitsebsk_region'
HOMEL_REGION = 'homel_region'
HRODNA_REGION = 'hrodna_region'
MINSK_REGION = 'minsk_region'
MAHILEU_REGION = 'mahileu_region'

DEPARTMENT_NAMES = {
    MINSK: 'ГУВД Мингорисполкома',
    BREST_REGION: 'УВД Брестского облисполкома',
    VITSEBSK_REGION: 'УВД Витебского облисполкома',
    HOMEL_REGION: 'УВД Гомельского облисполкома',
    HRODNA_REGION: 'УВД Гродненского облисполкома',
    MINSK_REGION: 'УВД Минского облисполкома',
    MAHILEU_REGION: 'УВД Могилевского облисполкома',
}

MINSK_DEPARTMENT_NAMES = {
    CENTRALNY: 'Центральное РУВД',
    SAVIECKI: 'Советское РУВД',
    PIERSAMAJSKI: 'Первомайское РУВД',
    PARTYZANSKI: 'Партизанское РУВД',
    ZAVODSKI: 'Заводское РУВД',
    LENINSKI: 'Ленинское РУВД',
    KASTRYCNICKI: 'Октябрьское РУВД',
    MASKOUSKI: 'Московское РУВД',
    FRUNZIENSKI: 'Фрунзенское РУВД',
}

# sending protection
ALLOW_SENDING = bool(getenv("ALLOW_SENDING", "False"))

# browser options
BROWSER_HOST = getenv("BROWSER_HOST", "localhost")
BROWSER_PORT = getenv("BROWSER_PORT", "4444")
BROWSER_URL = f'http://{BROWSER_HOST}:{BROWSER_PORT}/wd/hub'
