from typing import Optional, Tuple


class ErrorWhilePutInQueue(Exception):
    def __init__(self, text: str, data: Optional[Tuple[str, dict]] = None):
        self.text = text
        self.data = data


class ErrorWhileSending(Exception):
    pass
