import pandas
import arrow
import pymongo
import logging

from dictdiffer import diff as differ
from copy import deepcopy
from typing import List
from arrow import ParserError
from pymongo.database import Database
from abc import ABC, abstractmethod


class CollectorBase(ABC):
    def __init__(self, mongo_db: Database, name, ticker, date=None, debug=False):
        """
        :param mongo_db: mongo db connection
        :param name: collection name
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        self.ticker = ticker.upper()
        self.name = name
        self.collection = mongo_db.get_collection(self.name)
        self._mongo_db = mongo_db
        self._sorted_history = self.get_sorted_history(apply_filters=False)
        self._latest = self.__get_latest()
        self._date = date if date else arrow.utcnow()
        self._current_data = None
        self._debug = debug

    @abstractmethod
    def fetch_data(self) -> dict:
        pass

    @abstractmethod
    def _edit_diff(self, diff) -> dict:
        """
        This function is for editing or deleting an existing diff.
        It will be called with every diff that has been found while maintaining the diff structure of:

        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value,
            "diff_type": The type of the diff, could be add, remove, etc...
            "source": Which collection did it come from?
        }

        :return: The edited diff, None to delete the diff
        """
        if diff['changed_key'] == '':
            return None
        return diff

    def collect(self):
        self._current_data = self.fetch_data()

        # Updating DB with the new data
        entry = deepcopy(self._current_data)
        entry.update({"ticker": self.ticker, "date": self._date.format()})

        if not self._debug:
            self.collection.insert_one(entry)
        else:
            logging.info('collection.insert_one: {entry}'.format(entry=entry))

    def get_sorted_history(self, apply_filters=True):
        history = pandas.DataFrame(
            self.collection.find({"ticker": self.ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))

        if apply_filters:
            try:
                return self.__apply_filters(history)

            except Exception as e:
                logging.exception(e, exc_info=True)
                return history

        return history

    def __apply_filters(self, history):
        # Filtering all consecutive row duplicates where every column has the same value
        cols = history.columns.difference(['date', 'verifiedDate'])
        history = history.loc[(history[cols].shift() != history[cols]).any(axis='columns')]

        # Handling unhashable types
        for index, col in history.applymap(lambda x: isinstance(x, dict) or isinstance(x, list)).all().items():
            if col:
                history[index] = history[index].astype('str').value_counts()

        # Dropping monogemic columns where every row has the same value
        nunique = history.apply(pandas.Series.nunique)
        cols_to_drop = nunique[nunique == 1].index

        return history.drop(cols_to_drop, axis=1).dropna(axis='columns')

    def get_diffs(self) -> List[dict]:
        """
        This function returns the changes that occurred in a ticker's data.

        :return: A dict in the format of:
        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value,
            "diff_type": The type of the diff, could be add, remove, etc...
            "source": Which collection did it come from?
        }

        """
        if self._current_data is None:
            raise Exception('You should use collect() before using get_changes()')

        if self._latest is None:
            return []

        diffs = self.__parse_diffs(differ(self._latest, self._current_data))

        # Applying filters
        return list(filter(None, [self._edit_diff(diff) for diff in diffs]))

    def __parse_diffs(self, diffs):
        parsed_diffs = []

        for diff_type, key, values in diffs:
            if diff_type == 'change':
                # The first value is old, the second is new
                parsed_diffs.append(self.__build_diff(values[0], values[1], key, diff_type))
            elif diff_type == 'remove':
                # The removed value is in the list where the first cell is the index - therefore taking the "1" = value.
                parsed_diffs.append(self.__build_diff(values[0][1], None, key, diff_type))
            elif diff_type == 'add':
                # The removed value is in the list where the first cell is the index - therefore taking the "1" = value.
                parsed_diffs.append(self.__build_diff(None, values[0][1], key, diff_type))

        return parsed_diffs

    def __build_diff(self, old, new, key, diff_type):
        # joining by '.' if a key is a list of keys (differ's nested changes approach)
        key = key if not isinstance(key, list) else '.'.join((str(part) for part in key))
        return {
            "ticker": self.ticker,
            "date": self._date.format(),
            "changed_key": key,
            "old": old,
            "new": new,
            "diff_type": diff_type,
            "source": self.name
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
        except (ParserError, TypeError, ValueError):
            return value
