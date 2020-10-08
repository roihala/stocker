import json
import os
import pathlib
import urllib3
from urllib.error import HTTPError

import arrow
import pymongo
from pymongo.database import Database
from pymongo.errors import OperationFailure

from src.find.site import Site, InvalidTickerExcpetion


class TickerHistory(object):
    BADGES_SITE = Site('badges', 'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)
    PROFILE_SITE = Site('profile_url', 'https://backend.otcmarkets.com/otcapi/company/profile/full/ZHCLF?symbol=ZHCLF', True)
    DEFAULT_FIELDS_NUMBER = 15

    def __init__(self, ticker, mongo_db: Database):
        self._mongo_db = mongo_db
        self._ticker = ticker
        self._sorted_history = self.get_sorted_history()
        self._latest = self._sorted_history[0]

    def __enter__(self):
        self._current_data = self.fetch_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__update_db()

    def fetch_data(self):
        try:
            #site = urllib.request.urlopen(self.BADGES_SITE.get_ticker_url(self._ticker))
            #response = json.loads(site.read().decode())
            http = urllib3.PoolManager(maxsize=10)
            r = http.request('GET', self.BADGES_SITE.get_ticker_url(self._ticker))
            response = json.loads(r.data.decode('utf-8'))

        except HTTPError:
            raise InvalidTickerExcpetion('Invalid ticker: {ticker}', self._ticker, )

        if len(response.keys()) < self.DEFAULT_FIELDS_NUMBER:
            raise InvalidTickerExcpetion('Incomplete data for ticker: ', self._ticker, response.json().keys(), len(response.keys()))

        return response

    def __update_db(self):
        self.__add_ticker_and_date(self._current_data)
        self._mongo_db.symbols.insert_one(self._current_data)

    def __add_ticker_and_date(self, data):
        data.update({"ticker": self._ticker, "date": arrow.utcnow().timestamp})

    def get_sorted_history(self):
        return self._mongo_db.symbols.find({"ticker": self._ticker}).sort('date', pymongo.DESCENDING)

    def is_changed(self):
        return bool(self.get_changes())

    def get_changes(self):
        """
        This function returns the changes that occurred in a ticker's data.

        :return: A dict in the format of:
        {
            "ticker_name": The name of the ticker,
            "date": The current date,
            "changed_keys": A list of the keys that have changed,
            "old_values": A list of the "old" values,
            "new_values": A list of the "new" values)
        }

        """
        if self._sorted_history.count() == 0:
            return {}

        # Finding the keys that has changes, either from current->latest or latest->current
        changed_keys = [key for key in set(self._latest.keys() + self._current_data.keys())
                        if self._latest[key] != self._current_data.keys()]

        return {
            "ticker_name": self._ticker,
            "date": arrow.utcnow().timestamp,
            "changed_keys": changed_keys,
            "old_values": [self._latest.get(key) for key in changed_keys],
            "new_values": [self._current_data.get(key) for key in changed_keys]
        }
