import json
import os
import urllib
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

    def __enter__(self):
        self._current_data = self.fetch_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__update_db()

    def fetch_data(self):
        try:
            site = urllib.request.urlopen(self.BADGES_SITE.get_ticker_url(self._ticker))
            response = json.loads(site.read().decode())
        except HTTPError:
            raise InvalidTickerExcpetion('Invalid ticker: {ticker}', self._ticker, )

        if len(response.keys()) < self.DEFAULT_FIELDS_NUMBER:
            raise InvalidTickerExcpetion('Incomplete data for ticker: ', self._ticker, response.json().keys(), len(response.keys()))

        return response

    def __update_db(self):
        self.__add_keys(self._current_data)
        self._mongo_db.symbols.insert_one(self._current_data)

    def __add_keys(self, data):
        data.update({"ticker": self._ticker, "date": arrow.utcnow().timestamp})

    def get_sorted_history(self):
        return self._mongo_db.symbols.find({"ticker": self._ticker}).sort('date', pymongo.DESCENDING)

    def get_latest(self):
        return self._sorted_history[0]

    def is_changed(self):
        return bool(self.get_changes())

    def get_changes(self):
        if self._sorted_history.count() == 0:
            return {}

        return {key: {"new": value, "old": self.get_latest()[key]}
                for key, value in self._current_data.items() if value != self.get_latest()[key]}
