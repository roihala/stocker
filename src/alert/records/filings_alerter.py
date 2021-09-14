import logging
from abc import abstractmethod, ABC
from typing import List, Iterable

import arrow
import requests
from retry import retry
from simplejson import JSONDecodeError

from runnable import Runnable
from src.alert.alerter_base import AlerterBase
from src.common.otcm import REQUIRED_HEADERS
from src.common.proxy import proxy_get
from src.find.site import Site
from src.read import readers
from src.alert.tickers import alerters
from src.read.reader_base import ReaderBase
from src.records_factory import RecordsFactory

logger = logging.getLogger('Alert')


class FilingsAlerter(AlerterBase, ABC):
    def __init__(self, mongo_db, *args, **kwargs):
        super().__init__(mongo_db, *args, **kwargs)

        # prev_date Could be None on failure
        self._prev_date = self._get_previous_date(self._diffs)

    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={'
                    'ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC',
                    True)

    def edit_batch(self, diffs: List[dict]):
        diffs = super().edit_batch(diffs)
        ticker = diffs[0]['ticker']

        hierarchy = alerters.Securities.get_hierarchy()['tierCode']
        try:
            tier = readers.Securities(self._mongo_db, ticker).get_latest().get('tierCode')
        except AttributeError:
            tier = hierarchy[0]

        # If lower than pink current or (last filing was more than 3 months)
        if hierarchy.index(tier) < hierarchy.index('PC') or \
                (not self._prev_date or (arrow.utcnow() - arrow.get(self._prev_date)).days > 90):
            # Filtering existing filings (shared across filings and filings_pdf)
            return [diff for diff in diffs if not self.__is_existing_record_id(diff.get('record_id'))]
        else:
            return []

    def __is_existing_record_id(self, record_id):
        return any([True for collection in list(RecordsFactory.COLLECTIONS.keys()) + ['diffs'] if
                    self._mongo_db.get_collection(collection).find_one({'record_id': record_id})])

    def generate_msg(self, diff):
        return '{green_circle_emoji} {cloud_path}'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                          cloud_path=ReaderBase.escape_markdown(diff.get('cloud_path')))

    def get_text(self, append_dates=False, separator='\n'):
        try:
            if self._prev_date:
                formatted_prev_date = ReaderBase.format_stocker_date(self._prev_date, format='YYYY-MM-DD', style='')
            else:
                formatted_prev_date = None
            prev_date_msg = f"{self.YELLOW_CIRCLE_EMOJI_UNICODE} _Previous filing date: {formatted_prev_date}_\n"
        except Exception:
            prev_date_msg = ''

        return f"*Filings* added:\n" + super().get_text(append_dates, separator) + prev_date_msg

    def _get_previous_date(self, diffs):
        try:
            prev_record = self.get_previous_record(diffs)
            return self.get_release_date(prev_record)
        except Exception as e:
            logger.warning(f"Couldn't get previous date for diffs {diffs}")
            logger.exception(e)

    @retry(tries=3, delay=1)
    def get_previous_record(self, diffs):

        # Records should be sorted in data source (self.site)
        url = self.site.get_ticker_url(self._ticker)
        response = proxy_get(url, self._debug, headers=REQUIRED_HEADERS)

        records = response.json().get('records')
        try:

            if not diffs or not records:
                return records[0] if records else None

            first_id = min([diff.get('record_id') for diff in diffs])

            for index, record in enumerate(records):
                if record.get('id') == first_id:
                    return records[index + 1]

            return None

        except (IndexError, JSONDecodeError):
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
