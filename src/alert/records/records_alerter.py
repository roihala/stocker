import logging
from abc import abstractmethod, ABC
from functools import reduce
from typing import Iterable

import arrow
import requests

from src.alert.alerter_base import AlerterBase
from src.find.site import Site

logger = logging.getLogger('Alert')


class RecordsAlerter(AlerterBase, ABC):
    def get_alert_msg(self, diffs: Iterable[dict]):
        msg = ''

        first_id = min([diff.get('record_id') for diff in diffs])

        prev = self._get_previous_record(self._ticker, first_id)

        if prev and (arrow.utcnow() - arrow.get(prev.get('releaseDate'))).days > 180:
            msg = self.generate_msg(diffs)

        if msg:
            return set(diff['_id']['$oid'] for diff in diffs), msg
        else:
            return set(), msg

    def generate_msg(self, diffs):
        return '*{name}* added:\n' \
               '{green_circle_emoji} {titles}'.format(name=self.name,
                                                      green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                      titles=', '.join([diff.get('title') for diff in diffs]))

    @property
    @abstractmethod
    def site(self) -> Site:
        pass

    def _get_previous_record(self, ticker, record_id):
        try:
            # Records should sorted via url arguments (self.url)
            records = requests.get(self.site.get_ticker_url(ticker)).json().get('records')
            index = next((i for i, record in enumerate(records) if record["id"] == record_id), None)

            return records[index + 1] if index else None
            # TODO: read from db


        except Exception as e:
            logger.warning("Couldn't get last record for ticker: {ticker}".format(ticker=ticker))
            logger.exception(e)

    @staticmethod
    def get_first(diffs: Iterable[dict]):
        def calc_first(x, y):
            return x if x.get('record_id') < y.get('record_id') else y

        return reduce(lambda x, y: calc_first(x, y), diffs)
