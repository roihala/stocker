import json
import os

import arrow
import requests

from src.find.site import Site


class TickerHistory(object):
    BADGES_SITE = Site('badges', 'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)
    PROFILE_SITE = Site('profile_url', 'https://backend.otcmarkets.com/otcapi/company/profile/full/ZHCLF?symbol=ZHCLF', True)
    TICKERS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'tickers')
    DEFAULT_FIELDS_NUMBER = 15

    def __init__(self, ticker, debug):
        self._ticker = ticker
        self._debug = debug
        self._ticker_path = os.path.join(self.TICKERS_FOLDER, self._ticker + '.json')
        self._history = self.__get_history()
        self._latest = self.get_latest()

    def __enter__(self):
        os.makedirs(self.TICKERS_FOLDER)
        self._current_data = self.__fetch_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__update_history()

    def __fetch_data(self):
        response = requests.get(self.BADGES_SITE.get_ticker_url(self._ticker))

        if len(response.json().keys()) != self.DEFAULT_FIELDS_NUMBER:
            raise Exception('Incomplete data for ticker: ', self._ticker, response.json().keys(), len(response.json().keys()))

        return response.json()

    def __update_history(self):
        updated = self._history
        updated[arrow.now().for_json()] = self._current_data

        with open(self._ticker_path, 'w') as history_file:
            return json.dump(updated, history_file)

    def __get_history(self):
        if not os.path.exists(self._ticker_path):
            return {}
        else:
            with open(self._ticker_path, 'r') as history:
                return json.load(history)

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

        return {k: v for k, v in self._current_data.items() if v != self._latest[k]}
