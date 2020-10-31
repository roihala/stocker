from copy import deepcopy
from typing import List
import pandas
import arrow
import pymongo
from arrow import ParserError
from pymongo.database import Database
from abc import ABC, abstractmethod


class CollectorBase(ABC):
    def __init__(self, mongo_db: Database, collection, ticker, date=None, debug=False):
        self.ticker = ticker.upper()
        self.collection = mongo_db.get_collection(collection)
        self._mongo_db = mongo_db
        self._sorted_history = self.get_sorted_history()
        self._latest = self.__get_latest()
        self._date = date if date else arrow.utcnow()
        self._current_data = None
        self._debug = debug

    @abstractmethod
    def fetch_data(self) -> dict:
        pass

    @abstractmethod
    def _filter_diff(self, diff) -> bool:
        pass

    def collect(self):
        self._current_data = self.fetch_data()

        # Updating DB with the new data
        entry = deepcopy(self._current_data)
        entry.update({"ticker": self.ticker, "date": self._date.format()})
        if not self._debug:
            self.collection.insert_one(entry)
        else:
            print(entry)

    def get_sorted_history(self, duplicates=False):
        history = pandas.DataFrame(
            self.collection.find({"ticker": self.ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))
        if duplicates:
            return history
        else:
            # Filtering all consecutive duplicates
            cols = history.columns.difference(['date', 'verifiedDate'])
            return history.loc[(history[cols].shift() != history[cols]).any(axis='columns')]

    def get_diffs(self) -> List[dict]:
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
        if self._current_data is None:
            raise Exception('You should use collect() before using get_changes()')

        if self._latest is None:
            return []

        # Finding the keys that has changes, either from current->latest or latest->current
        changed_keys = [key for key in set(list(self._latest.keys()) + list(self._current_data.keys()))
                        if self._latest.get(key) != self._current_data.get(key)]

        diffs = [self.__get_diff(self._latest, changed_key) for changed_key in changed_keys]

        # Applying filters
        return list(filter(self._filter_diff, diffs))

    def __get_diff(self, latest, key):
        return {
            "ticker": self.ticker,
            "date": self._date.format(),
            "changed_key": key,
            "old": latest.get(key),
            "new": self._current_data.get(key)
        }

    def __get_latest(self):
        if self._sorted_history.empty:
            return None

        # to_dict indexes by rows, therefore getting the highest index
        history_dict = self._sorted_history.tail(1).drop(['date', 'ticker'], 'columns').to_dict('index')
        return history_dict[max(history_dict.keys())]

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (ParserError, TypeError):
            return value
