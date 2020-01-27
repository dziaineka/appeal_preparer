import time
from typing import Callable, Any


def wait(exception,
         function: Callable,
         pause=0,
         exception_to_raise=None,
         *args) -> Any:
    current_exception = exception

    for attempt in range(10):
        try:
            return function(*args)
        except exception as exc:
            current_exception = exc
            print(f'ОЙ wait - {str(exc)}')
            time.sleep(pause)
            continue

    if exception_to_raise:
        raise exception_to_raise
    else:
        raise current_exception


def wait_decorator(exception, pause=0, exception_to_raise=None) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(*args) -> Any:
            return wait(exception, function, pause, exception_to_raise, *args)

        return wrapper

    return decorator
