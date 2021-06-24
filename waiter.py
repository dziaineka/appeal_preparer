import time
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


def wait(exception_to_handle,
         function: Callable,
         pause: float,
         exception_to_raise,
         attempts: int,
         *args) -> Any:
    current_exception = exception_to_handle

    for _ in range(attempts):
        try:
            return function(*args)
        except exception_to_handle as exc:
            current_exception = exc
            logger.info(f'ОЙ wait - {str(exc)}')
            time.sleep(pause)
            continue

    if exception_to_raise:
        raise exception_to_raise
    else:
        raise current_exception


def wait_decorator(exception_to_handle,
                   pause: float = 0,
                   exception_to_raise=None,
                   attempts: int = 20) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(*args) -> Any:
            return wait(exception_to_handle,
                        function,
                        pause,
                        exception_to_raise,
                        attempts,
                        *args)

        return wrapper

    return decorator
