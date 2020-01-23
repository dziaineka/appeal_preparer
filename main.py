from multiprocessing import shared_memory
from sender import start
import config


def clear_busy_list() -> None:
    try:
        busy_list = shared_memory.ShareableList(name=config.BUSY_LIST)
    except FileNotFoundError:
        busy_list = shared_memory.ShareableList([], name=config.BUSY_LIST)

    busy_list.shm.close()
    busy_list.shm.unlink()


if __name__ == '__main__':
    clear_busy_list()
    jobs = []

    # for email in config.EMAILS:
    #     start(email)

    for email in config.EMAILS:
        p = multiprocessing.Process(target=start,
                                    args=(email,))
        jobs.append(p)
        p.start()
        time.sleep(3)
