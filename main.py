import logging
import random
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
from sender import start

Path("./logs").mkdir(parents=True, exist_ok=True)

file_handler_info = RotatingFileHandler("./logs/sender_info.log",
                                        maxBytes=100000000,
                                        backupCount=5)
file_handler_info.setLevel(logging.INFO)

file_handler_error = RotatingFileHandler("./logs/sender_error.log",
                                         maxBytes=10000000,
                                         backupCount=5)
file_handler_error.setLevel(logging.ERROR)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler_info, file_handler_error, stream_handler])

if __name__ == '__main__':
    try:
        start(random.choice(config.EMAILS))
    except Exception:
        sys.exit('reboot needed')
