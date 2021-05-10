import logging
from abc import abstractmethod, ABC
from typing import List

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

    def get_alert_msg(self, diffs: List[dict], as_dict=False):
        prev = self.__get_previous_date(diffs)

        if not prev or (arrow.utcnow() - arrow.get(prev)).days > 180:
            return {diffs[0]['_id']: self.generate_msg(diffs)} if as_dict else self.generate_msg(diffs)
        else:
            return {} if as_dict else ''

    def generate_msg(self, diffs):
        return '*{name}* added:\n' \
               '{green_circle_emoji} {titles}'.format(name=self.name,
                                                      green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                      titles=', '.join([diff.get('title') for diff in diffs]))

    def __get_previous_date(self, diffs):
        prev_record = self.get_previous_record(diffs)
        return self.get_release_date(prev_record)

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
        if not record:
            return None
        elif record.get('releaseDate'):
            date = record.get('releaseDate')
        elif record.get('receivedDate'):
            date = record.get('receivedDate')
        else:
            raise ValueError("No relase date for record: {record}".format(record=record))

        return arrow.get(date)
