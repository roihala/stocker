from abc import ABC, abstractmethod
from copy import deepcopy
from operator import itemgetter
from typing import List, Iterable

import inflection

from src.read.reader_base import ReaderBase


class AlerterBase(ABC):
    GREEN_CIRCLE_EMOJI_UNICODE = u'\U0001F7E2'
    RED_CIRCLE_EMOJI_UNICODE = u'\U0001F534'
    YELLOW_CIRCLE_EMOJI_UNICODE = u'\U0001F7E1'

    def __init__(self, mongo_db, telegram_bot, ticker, diffs: List[dict], last_price=None, debug=None):
        self.name = inflection.underscore(self.__class__.__name__)
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug
        self._ticker = ticker
        self._last_price = last_price if last_price else 0
        self._diffs = deepcopy(diffs)
        self.__messages = None

    @property
    def messages(self):
        if self.__messages is None:
            self.generate_messages()
        return self.__messages

    @property
    def processed_diffs(self):
        return [diff for diff in self._diffs if diff.get('_id') in self.messages.keys()]

    def generate_messages(self) -> dict:
        """
        This function will generate a dict that describes the messages of the obtained diff,
        while allowing customization at the alerter level, such as adding keys to the scheme and
        handling them differently (e.g: send file instead of message)

        Basic format:
        ObjectId('60cc6a43096cb97b35b1ee3c'): 'Wow! Something has changed'
        """
        self.__messages = {}

        for diff in self.edit_batch(self._diffs):
            if not self.is_relevant_diff(diff):
                continue

            diff = self.edit_diff(diff)

            diff_msg = self.generate_msg(diff)

            if diff_msg:
                self.__messages[diff['_id']] = diff_msg

        return deepcopy(self.__messages)

    @abstractmethod
    def generate_msg(self, diff, *args, **kwargs):
        """
        This is where you generate text for a given diff, after it was edited by self.edit_diff
        """
        pass

    def get_text(self, append_dates=False, separator='\n\n'):
        return separator.join([self.__append_date(object_id, message) if append_dates else message
                               for object_id, message in self.messages.items()])

    def is_relevant_diff(self, diff):
        return True

    def edit_batch(self, diffs: List[dict]) -> List[dict]:
        return sorted(diffs, key=itemgetter('changed_key'))

    def edit_diff(self, diff):
        return diff

    def __append_date(self, object_id, message):
        date = next(diff for diff in self.processed_diffs if diff.get('_id') == object_id).get('date')
        return f'{message}\n{ReaderBase.format_stocker_date(date)}'
