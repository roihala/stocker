from copy import deepcopy

import logging

from abc import ABC, abstractmethod

from src import factory
from src.collect.collector_base import CollectorBase
from src.collect.tickers.differ import Differ

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
        if self.name not in self.cache:
            self.cache[self.name] = {}

        self.ticker = ticker.upper()
        self._reader = factory.Factory.readers_factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': ticker})

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
        latest = self.cache[self.name].get(self.ticker, None)
        latest = latest if latest else self._reader.get_latest()

        diffs = []

        if not latest:
            self.__save_document(current)

        elif current != latest or not latest:
            # Saving the fetched data
            self.__save_document(current)

            # Saving the diffs to diffs collection
            diffs = [self.__decorate_diff(diff) for diff in Differ().get_diffs(latest, current, self.get_nested_keys())]

            logger.info('diffs: {diffs}'.format(diffs=diffs))

        self.cache[self.name][self.ticker] = current
        return self.__collect_sons(diffs)

    def __decorate_diff(self, diff):
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
            "date": self._date.format(),
            "changed_key": key,
            "source": self.name,
            "alerted": False
        })
        
        return diff

    def __save_document(self, data: dict):
        # Updating DB with the new data
        copy = deepcopy(data)
        copy.update({"ticker": self.ticker, "date": self._date.format()})

        if self._debug and self._write is not True:
            logger.info('{collection}.insert_one: {entry}'.format(collection=self.name, entry=copy))
        else:
            self.collection.insert_one(copy)

    def __collect_sons(self, diffs):
        for son in self.get_sons():
            try:
                collection_args = {'mongo_db': self._mongo_db, 'ticker': self.ticker, 'date': self._date,
                                   'debug': self._debug, 'cache': self.cache}
                collector = factory.Factory.collectors_factory(son, **collection_args)
                result = collector.collect(self._raw_data)
                if result:
                    diffs += result

            except Exception as e:
                logger.warning("Couldn't collect {name}'s son {son}".format(name=self.name, son=son))
                logger.exception(e)

        return diffs
