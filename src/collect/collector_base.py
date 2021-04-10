from copy import deepcopy

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

global cache
cache = {}


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
        self._reader = factory.Factory.readers_factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': ticker})

        if self.name not in cache:
            cache[self.name] = {}

    @staticmethod
    def get_sons():
        return []

    @staticmethod
    def get_drop_keys():
        """
        A list of keys to drop. Note that the keys won't even be saved to mongo
        """
        return []

    @staticmethod
    def get_nested_keys():
        return {}

    @abstractmethod
    def fetch_data(self, data=None) -> dict:
        pass

    def collect(self, raw_data=None):
        current = self.fetch_data(raw_data)
        latest = cache[self.name].get(self.ticker, None)
        if latest is None:
            latest = self._reader.get_latest()

        if not latest:
            self.__save_data(current)

        elif current != latest:
            # Saving the fetched data
            self.__save_data(current)

            # Saving the diffs to diffs collection
            diffs = [self.__decorate_diff(diff) for diff in Differ().get_diffs(latest, current, self.get_nested_keys())]
            logger.info('diffs: {diffs}'.format(diffs=diffs))
            if diffs:
                self._mongo_db.diffs.insert_many(diffs)

        cache[self.name][self.ticker] = current
        self.__collect_sons()

    def __decorate_diff(self, diff):
        subkey = None
        if not isinstance(diff['changed_key'], list):
            key = diff.get('changed_key')
        elif len(diff.get('changed_key')) > 1:
            key = diff.get('changed_key')[0]
            # joining by '.' if a subkey is a list of keys (differ's nested changes approach)
            subkey = '.'.join(str(part) for part in diff.get('changed_key')[1:])

            diff.update({
                "subkey": subkey
            })

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
        for son in self.get_sons():
            try:
                collection_args = {'mongo_db': self._mongo_db, 'ticker': self.ticker, 'date': self._date, 'debug': self._debug}
                collector = factory.Factory.collectors_factory(son, **collection_args)
                collector.collect(self._raw_data)
            except Exception as e:
                logger.warning("Couldn't collect {name}'s son {son}".format(name=self.name, son=son))
                logger.exception(e)
