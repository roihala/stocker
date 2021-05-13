from abc import ABC, abstractmethod
from typing import List


class AlerterBase(ABC):
    GREEN_CIRCLE_EMOJI_UNICODE = u'\U0001F7E2'
    RED_CIRCLE_EMOJI_UNICODE = u'\U0001F534'

    def __init__(self, mongo_db, telegram_bot, ticker, debug=None):
        self.name = self.__class__.__name__.lower()
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug
        self._ticker = ticker

    @abstractmethod
    def get_alert_msg(self, diffs: List[dict], as_dict=False):
        if as_dict and '_id' not in diffs[0]:
            raise ValueError("Can't generate dict for diffs with no _id")
