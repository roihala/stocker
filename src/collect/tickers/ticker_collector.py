from copy import deepcopy

import logging

from abc import ABC, abstractmethod

from redis import Redis
import pickle

from src.collect.collector_base import CollectorBase
from src.collect.tickers.differ import Differ
from src import collector_factory
from src.find.site import InvalidTickerExcpetion
from src.readers_factory import ReadersFactory

logger = logging.getLogger('Collect')


class TickerCollector(CollectorBase, ABC):
    def __init__(self, ticker, *args, **kwargs):
        """
        :param mongo_db: mongo db connection
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        super().__init__(*args, **kwargs)

        if not isinstance(self.cache, Redis) and self.name not in self.cache:
            self.cache[self.name] = {}

        self.ticker = ticker.upper()
        self._reader = ReadersFactory.factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': ticker})

    @staticmethod
    def get_sons():
        return []

    @staticmethod
    def get_drop_keys():
        """
        A list of keys to drop. Note that the keys won't even be saved to mongo
        """
        return []

    @abstractmethod
    def fetch_data(self, data=None) -> dict:
        pass

    def _get_cache_latest(self):
        if isinstance(self.cache, dict):
            return self.cache[self.name].get(self.ticker, None)
        if isinstance(self.cache, Redis):
            key = self.name + '.' + self.ticker
            result = self.cache.get(key)
            if result is None:
                return None

            result = pickle.loads(result)
            if result == {}:
                return None

    def _set_cache_value(self, current_value):
        if isinstance(self.cache, dict):
            self.cache[self.name][self.ticker] = current_value
        if isinstance(self.cache, Redis):
            key = self.name + '.' + self.ticker
            pickled = pickle.dumps(current_value)
            self.cache.set(key, pickled)

    def collect(self, raw_data=None):
        diffs = []
        try:
            current = self.fetch_data(raw_data)
        except InvalidTickerExcpetion as e:
            return self.__collect_sons(diffs)

        latest = self._get_cache_latest()
        latest = latest if latest else self._reader.get_latest(remove_index=True)

        if not latest:
            self.__save_document(current)

        elif current != latest:
            # Saving the fetched data
            self.__save_document(current)

            diffs = [self.decorate_diff(diff) for diff in
                     Differ().get_diffs(latest, current, self._reader.get_nested_keys())]

            logger.info('diffs: {diffs}'.format(diffs=diffs))

        self._set_cache_value(current)
        return self.__collect_sons(diffs)

    def decorate_diff(self, diff, *args, **kwargs):
        diff = super().decorate_diff(diff)

        if isinstance(diff.get('changed_key'), list):
            key = diff.get('changed_key')[0]
            # joining by '.' if a subkey is a list of keys (differ's nested changes approach)
            subkey = '.'.join(str(part) for part in diff.get('changed_key')[1:])

            diff.update({
                "subkey": subkey
            })

        else:
            key = diff.get('changed_key')

        diff.update({
            "ticker": self.ticker,
            "changed_key": key
        })

        return diff

    def __save_document(self, data: dict):
        # Updating DB with the new data
        copy = deepcopy(data)
        copy.update({"ticker": self.ticker, "date": self._date.format()})

        if self._debug:
            logger.info('{collection}.insert_one: {entry}'.format(collection=self.name, entry=copy))
        self.collection.insert_one(copy)

        # Updating latest_collection
        self.collection_latest.delete_many({'ticker': self.ticker})
        self.collection_latest.insert_one(copy)

    def __collect_sons(self, diffs):
        for son in self.get_sons():
            try:
                collection_args = {'mongo_db': self._mongo_db, 'ticker': self.ticker, 'date': self._date,
                                   'debug': self._debug, 'cache': self.cache}
                collector = collector_factory.CollectorsFactory.factory(son, **collection_args)
                result = collector.collect(self._raw_data)
                if result:
                    diffs += result

            except Exception as e:
                logger.warning("Couldn't collect {name}'s son {son}".format(name=self.name, son=son))
                logger.exception(e)

        return diffs
