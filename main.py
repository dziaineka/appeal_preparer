from sender import start
import config
import sys
import random
import logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    try:
        start(random.choice(config.EMAILS))
    except Exception:
        sys.exit('reboot needed')
