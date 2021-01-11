from copy import deepcopy
from itertools import tee

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
        self.name = self.__class__.__name__.lower()
        self.collection = mongo_db.get_collection(self.name)
        self._mongo_db = mongo_db
        self._date = date if date else arrow.utcnow()
        self._debug = debug

    @property
    def drop_keys(self):
        """
        A list of keys to drop. Note that the keys won't even be saved to mongo
        """
        return []

    @abstractmethod
    def fetch_data(self) -> dict:
        pass

    def collect(self):
        current = self.fetch_data()
        latest = self.get_latest()

        if current != latest:
            # Updating DB with the new data
            copy = deepcopy(current)
            copy.update({"ticker": self.ticker, "date": self._date.format()})

            if self._debug:
                logging.info('{collection}.insert_one: {entry}'.format(collection=self.name, entry=copy))
            else:
                self.collection.insert_one(copy)

        return current, latest

    def get_sorted_history(self, filter_rows=False, filter_cols=False):
        """
        Returning sorted history with the ability of filtering consecutive rows and column duplications

        ** NOTE THAT NESTED KEYS WILL BE FLATTENED IN ORDER TO FILTER!

        :param filter_rows: bool
        :param filter_cols: bool
        :return: df
        """
        history = pandas.DataFrame(
            self.collection.find({"ticker": self.ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))\
            .drop(self.drop_keys, axis='columns', errors='ignore')

        # Setting date as index
        history["date"] = history["date"].apply(
            self.timestamp_to_datestring)
        history = history.set_index(['date'])

        if filter_rows or filter_cols:
            try:
                history = self.flatten(history)
                history = self.__apply_filters(history, filter_rows, filter_cols)
            except Exception as e:
                logging.exception(self.__class__)
                logging.exception(e)

        # Resetting index
        history.reset_index(inplace=True)

        return history

    @classmethod
    def flatten(cls, history):
        nested_keys = factory.Factory.get_match(cls).get_nested_keys()

        for column, layers in nested_keys.items():
            if column in history.columns:
                history[column] = pandas.Series(
                    {date: cls.__unfold(value, tee(iter(layers))[1]) for date, value in
                     history[column].dropna().to_dict().items()})

        history.index.name = 'date'

        return history

    @classmethod
    def __unfold(cls, iterable, layers):
        try:
            layer = next(layers)

            if issubclass(layer, list):
                return tuple([cls.__unfold(value, tee(layers)[1]) for value in iterable])

            elif issubclass(layer, dict):
                key = next(layers)
                return cls.__unfold(iterable[key], tee(layers)[1])
        except StopIteration:
            return iterable
        except Exception as e:
            logging.warning("Couldn't unfold {iterable}".format(iterable=iterable))
            logging.exception(e)

    @classmethod
    def __apply_filters(cls, history, filter_rows, filter_cols):
        if filter_rows:
            shifted_history = history.apply(lambda x: pandas.Series(x.dropna().values), axis=1).fillna('')
            shifted_history.columns = history.columns

            # Filtering consecutive row duplicates where every column has the same value
            history = shifted_history.loc[(shifted_history.shift() != shifted_history).any(axis='columns')]

        if filter_cols:
            # Dropping monogemic columns where every row has the same value
            nunique = history.apply(pandas.Series.nunique)
            cols_to_drop = nunique[nunique == 1].index
            history = history.drop(cols_to_drop, axis=1).dropna(axis='columns')

        return history

    def get_latest(self):
        sorted_history = self.get_sorted_history()

        if sorted_history.empty:
            return None

        # to_dict indexes by rows, therefore getting the highest index
        history_as_dicts = sorted_history.tail(1).drop(['date', 'ticker'], 'columns', errors='ignore').to_dict('index')
        return history_as_dicts[max(history_as_dicts.keys())]

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (ParserError, TypeError, ValueError):
            return value
