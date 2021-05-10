import arrow

from abc import ABC, abstractmethod
from typing import Iterable


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
    def get_alert_msg(self, diffs: Iterable[dict], as_dict=False):
        pass
