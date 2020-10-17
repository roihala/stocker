import json
import pandas
import urllib

import urllib3
from urllib.error import HTTPError

import arrow
import pymongo
from arrow import ParserError
from pymongo.database import Database

from src.find.site import Site, InvalidTickerExcpetion


class TickerHistory(object):
    BADGES_SITE = Site('badges',
                       'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)
    PROFILE_SITE = Site('profile_url', 'https://backend.otcmarkets.com/otcapi/company/profile/full/ZHCLF?symbol=ZHCLF',
                        True)
    DEFAULT_FIELDS_NUMBER = 15

    def __init__(self, ticker, mongo_db: Database):
        self._mongo_db = mongo_db
        self._ticker = ticker.upper()
        self._sorted_history = self.get_sorted_history()

    def __enter__(self):
        self._current_data = self.fetch_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__update_db()

    def fetch_data(self):
        try:
            site = urllib.request.urlopen(self.BADGES_SITE.get_ticker_url(self._ticker))
            response = json.loads(site.read().decode())
            # http = urllib3.PoolManager(maxsize=10)
            # r = http.request('GET', self.BADGES_SITE.get_ticker_url(self._ticker))
            # response = json.loads(r.data.decode('utf-8'))

        except HTTPError:
            raise InvalidTickerExcpetion('Invalid ticker: {ticker}', self._ticker)

        if len(response.keys()) < self.DEFAULT_FIELDS_NUMBER:
            raise InvalidTickerExcpetion('Incomplete data for ticker: ', self._ticker, response.json().keys(),
                                         len(response.keys()))

        return response

    def __update_db(self):
        self.__add_unique_keys(self._current_data)
        self._mongo_db.symbols.insert_one(self._current_data)

    def __add_unique_keys(self, data):
        data.update({"ticker": self._ticker, "date": arrow.utcnow().format()})

    def get_sorted_history(self, duplicates=True):
        history = pandas.DataFrame(self._mongo_db.symbols.find({"ticker": self._ticker}, {"_id": False}).sort('date', pymongo.DESCENDING))
        if duplicates:
            return history
        else:
            # Filtering all consecutive duplicates
            cols = history.columns.difference(['date'])
            return history.loc[(history[cols].shift() != history[cols]).any(axis='columns')]

    def is_changed(self):
        return bool(self.get_changes())

    def get_changes(self):
        """
        This function returns the changes that occurred in a ticker's data.

        :return: A dict in the format of:
        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value
        }

        """
        if self._sorted_history.empty:
            return {}

        # print(self._sorted_history.head(n=1)
        latest = self.__get_latest()

        # Finding the keys that has changes, either from current->latest or latest->current
        changed_keys = [key for key in set(list(latest.keys()) + list(self._current_data.keys()))
                        if latest.get(key) != self._current_data.get(key)]

        return [self.__get_diff(latest, changed_key) for changed_key in changed_keys]

    def __get_diff(self, latest, key):
        return {
            "ticker": self._ticker,
            "date": arrow.utcnow().format(),
            "changed_key": key,
            "old": latest.get(key),
            "new": self._current_data.get(key)
        }

    def __get_latest(self):
        # Index dict indexes by rows, therefore returning the row of index 0
        return self._sorted_history.head(n=1).drop(['date', 'ticker'], 'columns').to_dict('index')[0]

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (ParserError, TypeError):
            return value
