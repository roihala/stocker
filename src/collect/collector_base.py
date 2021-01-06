from copy import deepcopy

import pandas
import arrow
import pymongo
import logging

from arrow import ParserError
from pymongo.database import Database
from abc import ABC, abstractmethod

from src import factory


class CollectorBase(ABC):
    def __init__(self, mongo_db: Database, ticker, date=None, debug=False):
        """
        :param mongo_db: mongo db connection
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        self.ticker = ticker.upper()
        self.name = factory.Factory.resolve_name(self.__class__)
        self.collection = mongo_db.get_collection(self.name)
        self._mongo_db = mongo_db
        self._sorted_history = self.get_sorted_history(apply_filters=False)
        self._date = date if date else arrow.utcnow()
        self._debug = debug

    @abstractmethod
    def fetch_data(self) -> dict:
        pass

    def collect(self):
        current = self.fetch_data()

        # Updating DB with the new data
        copy = deepcopy(current)
        copy.update({"ticker": self.ticker, "date": self._date.format()})

        if not self._debug:
            self.collection.insert_one(copy)
        else:
            logging.info('{collection}.insert_one: {entry}'.format(collection=self.name, entry=copy))

        return current, self.get_latest()

    def get_sorted_history(self, apply_filters=True):
        history = pandas.DataFrame(
            self.collection.find({"ticker": self.ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))

        if apply_filters:
            try:
                return self.__apply_filters(history)

            except Exception as e:
                logging.exception(e)
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

    def get_latest(self):
        if self._sorted_history.empty:
            return None

        # to_dict indexes by rows, therefore getting the highest index
        history_as_dicts = self._sorted_history.tail(1).drop(['date', 'ticker'], 'columns').to_dict('index')
        return history_as_dicts[max(history_as_dicts.keys())]

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (ParserError, TypeError, ValueError):
            return value
