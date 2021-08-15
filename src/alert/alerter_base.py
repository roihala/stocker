from abc import ABC, abstractmethod
from typing import List

import inflection


class AlerterBase(ABC):
    GREEN_CIRCLE_EMOJI_UNICODE = u'\U0001F7E2'
    RED_CIRCLE_EMOJI_UNICODE = u'\U0001F534'
    YELLOW_CIRCLE_EMOJI_UNICODE = u'\U0001F7E1'

    def __init__(self, mongo_db, telegram_bot, ticker, last_price=None, debug=None):
        self.name = inflection.underscore(self.__class__.__name__)
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug
        self._ticker = ticker
        self._last_price = last_price if last_price else 0

    @abstractmethod
    def generate_messages(self, diffs: List[dict]) -> dict:
        """
        This function will generate a dict that describes the messages of the obtained diff,
        while allowing customization at the alerter level, such as adding keys to the scheme and
        handling them differently (e.g: send file instead of message)

        Basic format:
        ObjectId('60cc6a43096cb97b35b1ee3c'): {'message': 'kaki'}
        """
        pass
