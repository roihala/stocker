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
from src.collect.differ import Differ

logger = logging.getLogger('Collect')


class CollectorBase(ABC):
    def __init__(self, mongo_db: Database, ticker, date=None, debug=False, write=False):
        """
        :param mongo_db: mongo db connection
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        self.ticker = ticker.upper()
        self.name = self.__class__.__name__.lower()
        self.collection = mongo_db.get_collection(self.name)
        self._raw_data = None
        self._mongo_db = mongo_db
        self._date = date if date else arrow.utcnow()
        self._debug = debug
        self._write = write

    @staticmethod
    def sons():
        return []

    @property
    def drop_keys(self):
        """
        A list of keys to drop. Note that the keys won't even be saved to mongo
        """
        return []

    @property
    def nested_keys(self):
        return {}

    @abstractmethod
    def fetch_data(self, data=None) -> dict:
        pass

    def collect(self, raw_data=None):
        current = self.fetch_data(raw_data)
        latest = self.get_latest()

        if not latest:
            self.__save_data(current)
        elif current != latest:
            # Saving the fetched data
            self.__save_data(current)

            # Saving the diffs to diffs collection
            diffs = [self.__decorate_diff(diff) for diff in Differ().get_diffs(latest, current, self.nested_keys)]
            logger.info('diffs: {diffs}'.format(diffs=diffs))
            self._mongo_db.diffs.insert_many(diffs)

        self.__collect_sons()

    def __decorate_diff(self, diff):
        # joining by '.' if a key is a list of keys (differ's nested changes approach)
        key = diff['changed_key'] if not isinstance(diff['changed_key'], list) else \
            '.'.join((str(part) for part in diff['changed_key']))

        diff.update({
            "ticker": self.ticker,
            "date": self._date.format(),
            "changed_key": key,
            "source": self.name,
            "alerted": False
        })

        return diff

    def __save_data(self, data):
        # Updating DB with the new data
        copy = deepcopy(data)
        copy.update({"ticker": self.ticker, "date": self._date.format()})

        if self._debug and self._write is not True:
            logger.info('{collection}.insert_one: {entry}'.format(collection=self.name, entry=copy))
        else:
            self.collection.insert_one(copy)

    def __collect_sons(self):
        for son in self.sons():
            try:
                collection_args = {'mongo_db': self._mongo_db, 'ticker': self.ticker, 'date': self._date, 'debug': self._debug}
                collector = factory.Factory.collectors_factory(son, **collection_args)
                collector.collect(self._raw_data)
            except Exception as e:
                logger.warning("Couldn't collect {name}'s son {son}".format(name=self.name, son=son))
                logger.exception(e)

    def get_sorted_history(self, filter_rows=False, filter_cols=False, ignore_latest=False):
        """
        Returning sorted history with the ability of filtering consecutive rows and column duplications

        ** NOTE THAT NESTED KEYS WILL BE FLATTENED IN ORDER TO FILTER!

        :param filter_rows: bool
        :param filter_cols: bool
        :param ignore_latest: Ignore the latest entry
        :return: df
        """
        history = pandas.DataFrame(
            self.collection.find({"ticker": self.ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))\
            .drop(self.drop_keys, axis='columns', errors='ignore')

        if history.empty:
            return history

        # Setting date as index
        history["date"] = history["date"].apply(
            self.timestamp_to_datestring)

        history = history.set_index(['date'])

        pandas.set_option('display.expand_frame_repr', False)

        if ignore_latest and len(history.index) > 1:
            history.drop(history.tail(1).index, inplace=True)

        if filter_rows or filter_cols:
            try:
                history = self.flatten(history)
                history = self.__apply_filters(history, filter_rows, filter_cols)
            except Exception as e:
                logger.exception(self.__class__)
                logger.exception(e)

        # Resetting index
        history.reset_index(inplace=True)

        return history

    def flatten(self, history):
        for column, layers in self.nested_keys.items():
            if column in history.columns:
                history[column] = pandas.Series(
                    {date: self.__unfold(value, tee(iter(layers))[1]) for date, value in
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
            logger.warning("Couldn't unfold {iterable}".format(iterable=iterable))
            logger.exception(e)

    @classmethod
    def __apply_filters(cls, history, filter_rows, filter_cols):
        if filter_cols:
            # Dropping monogemic columns where every row has the same value
            nunique = history.apply(pandas.Series.nunique)
            cols_to_drop = nunique[nunique == 1].index
            history = history.drop(cols_to_drop, axis=1).dropna(axis='columns')

        if filter_rows:
            shifted_history = history.apply(lambda x: pandas.Series(x.dropna().values), axis=1).fillna('')

            # Filtering consecutive row duplicates where every column has the same value
            history = shifted_history.loc[(shifted_history.shift() != shifted_history).any(axis='columns')]

        return history

    def get_latest(self):
        sorted_history = self.get_sorted_history()

        if sorted_history.empty:
            return {}

        # to_dict indexes by rows, therefore getting the highest index
        history_as_dicts = sorted_history.tail(1).drop(['date', 'ticker'], 'columns', errors='ignore').to_dict('index')
        return history_as_dicts[max(history_as_dicts.keys())]

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (ParserError, TypeError, ValueError):
            return value
