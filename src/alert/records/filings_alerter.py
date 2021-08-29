import logging
from abc import abstractmethod, ABC
from json import JSONDecodeError
from typing import List

import arrow
import requests
from retry import retry

from src.alert.alerter_base import AlerterBase
from src.find.site import Site
from src.read import readers
from src.alert.tickers import alerters
from src.read.reader_base import ReaderBase

logger = logging.getLogger('Alert')


class FilingsAlerter(AlerterBase, ABC):
    @property
    @abstractmethod
    def site(self) -> Site:
        pass

    def generate_messages(self, diffs: List[dict]):
        # TODO: delete
        messages = {}
        prev_date = self._get_previous_date(diffs)

        tier = readers.Securities(self._mongo_db, diffs[0]['ticker']).get_latest().get('tierCode')
        hierarchy = alerters.Securities.get_hierarchy()['tierCode']

        # Filtering existing filings (shared across filings and filings_pdf)
        diffs = [diff for diff in diffs if not self._mongo_db.diffs.find_one({'record_id': diff.get('record_id')})]

        if diffs and (hierarchy.index(tier) < hierarchy.index('PC') or
                      ((not prev_date or (
                              arrow.utcnow() - arrow.get(prev_date)).days > 90) and self._last_price < 0.05)):
            messages.update({diffs[0]['_id']: self.generate_payload(diffs, prev_date)})
            # Adding empty ids in order to save those diffs
            messages.update({diff['_id']: {'message': ''} for diff in diffs[1:]})

        return messages

    def generate_msg(self, diffs, prev_date):
        msg = '\n'.join(['{green_circle_emoji} {cloud_path}'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                                    cloud_path=ReaderBase.escape_markdown(
                                                                        diff.get('cloud_path'))) for diff in diffs])
        prev_date_msg = f"_Previous filing date: {ReaderBase.format_stocker_date(prev_date, format='YYYY-MM-DD', style='')}_\n"

        return f"*Filings* added:\n{msg}\n{prev_date_msg if prev_date else ''}"

    def generate_payload(self, diffs, prev_date):
        return {'message': self.generate_msg(diffs, prev_date), 'date': diffs[0].get('date')}

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
