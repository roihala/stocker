import logging
from abc import abstractmethod, ABC
from json import JSONDecodeError
from typing import List

import arrow
import requests
from retry import retry

from src.alert.alerter_base import AlerterBase
from src.find.site import Site

logger = logging.getLogger('Alert')


class RecordsAlerter(AlerterBase, ABC):
    @property
    @abstractmethod
    def site(self) -> Site:
        pass

    def generate_messages(self, diffs: List[dict]):
        messages = {}
        prev = self._get_previous_date(diffs)

        if not prev or (arrow.utcnow() - arrow.get(prev)).days > 60:
            messages.update({diffs[0]['_id']: self.generate_payload(diffs)})
            # Adding empty ids in order to save those diffs
            messages.update({diff['_id']: {'message': ''} for diff in diffs[1:]})

        return messages

    def generate_payload(self, diffs):
        return {'message': self.generate_msg(diffs), 'date': diffs[0].get('date')}

    def generate_msg(self, diffs):
        msg = '\n'.join(['{green_circle_emoji} {title}'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                               title=diff.get('title')) for diff in diffs])

        return f'*{self.name}* added:\n{msg}'

    def _get_previous_date(self, diffs):
        try:
            prev_record = self.get_previous_record(diffs)
            return self.get_release_date(prev_record)
        except Exception as e:
            logger.warning(f"Couldn't get previous date for diffs {diffs}")
            logger.exception(e)

    @retry(JSONDecodeError, tries=5, delay=1)
    def get_previous_record(self, diffs):
        # Records should be sorted in data source (self.site)
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
