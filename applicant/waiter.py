import time
from typing import Callable, Any


def wait(exception, function: Callable, pause=0, *args) -> Any:
    for attempt in range(10):
        try:
            return function(*args)
        except exception:
            time.sleep(pause)
            continue

    raise exception


def wait_decorator(exception, pause=0) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(*args) -> Any:
            return wait(exception, function, pause, *args)

        return wrapper

    return decorator
