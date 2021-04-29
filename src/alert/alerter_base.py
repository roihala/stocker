from abc import ABC, abstractmethod
from typing import Iterable, Tuple, Set


class AlerterBase(ABC):
    GREEN_CIRCLE_EMOJI_UNICODE = u'\U0001F7E2'
    RED_CIRCLE_EMOJI_UNICODE = u'\U0001F534'

    def __init__(self, mongo_db, telegram_bot, batch, ticker, debug=None):
        self.name = self.__class__.__name__.lower()
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug
        self._ticker = ticker
        self._batch = batch

    @abstractmethod
    def get_alert_msg(self, diffs: Iterable[dict]) -> Tuple[Set, str]:
        pass

    def _get_batch_by_source(self, source):
        return [diff for diff in self._batch if diff.get('source') == source]
