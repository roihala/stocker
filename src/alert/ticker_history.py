import json
import os
import pathlib
import urllib3
from urllib.error import HTTPError

import arrow
import requests

from src.find.site import Site, InvalidTickerExcpetion


class TickerHistory(object):
    BADGES_SITE = Site('badges', 'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)
    PROFILE_SITE = Site('profile_url', 'https://backend.otcmarkets.com/otcapi/company/profile/full/ZHCLF?symbol=ZHCLF', True)
    TICKERS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'tickers')
    DEFAULT_FIELDS_NUMBER = 15

    def __init__(self, ticker):
        self._ticker = ticker
        self._ticker_path = os.path.join(self.TICKERS_FOLDER, self._ticker + '.json')
        self._history = self.get_history()
        self._latest = self.get_latest()

    def __enter__(self):
        pathlib.Path(self.TICKERS_FOLDER).mkdir(parents=True, exist_ok=True)
        self._current_data = self.fetch_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__update_history()

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

    def __update_history(self):
        updated = self._history
        updated[arrow.now().for_json()] = self._current_data

        with open(self._ticker_path, 'w') as history_file:
            return json.dump(updated, history_file)

    def get_history(self):
        if not os.path.exists(self._ticker_path):
            return {}
        else:
            with open(self._ticker_path, 'r') as history:
                return json.load(history)

    def __get_latest_date(self):
        if not self._history.keys():
            return None

        return max(self._history.keys())

    def get_latest(self):
        if not self._history.keys():
            return {}

        latest = max(self._history.keys())
        return self._history[latest]

    def is_changed(self):
        return bool(self.get_changes())

    def get_changes(self):
        if not self._latest:
            return {}

        return {badge: (value, self._latest[badge])
                for badge, value in self._current_data.items() if value != self._latest[badge]}

    def get_current_data(self):
        return self._current_data
