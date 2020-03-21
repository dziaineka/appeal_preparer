from sender import start
import config
import sys
import random

if __name__ == '__main__':
    try:
        start(random.choice(config.EMAILS))
    except Exception:
        sys.exit('reboot needed')
