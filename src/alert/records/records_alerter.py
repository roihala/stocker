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
    @property
    @abstractmethod
    def site(self) -> Site:
        pass

    @property
    def brothers(self):
        return []

    def get_alert_msg(self, diffs: Iterable[dict]):
        prev = self.__get_previous_date(diffs)

        if not prev or (arrow.utcnow() - arrow.get(prev)).days > 180:
            return self.generate_msg(diffs)

        else:
            return ''

    def generate_msg(self, diffs):
        return '*{name}* added:\n' \
               '{green_circle_emoji} {titles}'.format(name=self.name,
                                                      green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                      titles=', '.join([diff.get('title') for diff in diffs]))

    def __get_previous_date(self, diffs):
        # Previous record date
        prev_records = [brother.get_previous_record(self._get_batch_by_source(brother.name)) for brother in self.brothers] + [self.get_previous_record(diffs)]

        dates = [self.get_release_date(record) for record in prev_records if record is not None]

        # Returning the latest releaseDate
        return max(dates) if dates else None

    def get_previous_record(self, diffs):
        # Records should be sorted via url arguments (self.url)
        records = requests.get(self.site.get_ticker_url(self._ticker)).json().get('records')

        try:
            if not diffs:
                return records[0] if records else None

            first_id = min([diff.get('record_id') for diff in diffs])

            for index, record in enumerate(records):
                if record.get('id') == first_id:
                    return records[index + 1]

            return None

        except IndexError:
            logger.info("No last records for {ticker}:{records}".format(ticker=self._ticker, records=records))

        except Exception as e:
            logger.warning("Couldn't get last record for ticker: {ticker}".format(ticker=self._ticker))
            logger.exception(e)

    @staticmethod
    def get_release_date(record):
        if record.get('releaseDate'):
            date = record.get('releaseDate')
        elif record.get('receivedDate'):
            date = record.get('receivedDate')
        else:
            raise ValueError("No relase date for record: {record}".format(record=record))

        return arrow.get(date)
