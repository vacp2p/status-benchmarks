# Python Imports
from dataclasses import dataclass


@dataclass
class ResultEntry:
    sender: str
    receiver: str
    timestamp: int
    result: str
