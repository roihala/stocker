import logging

import arrow
import pandas
import pymongo

from abc import ABC
from itertools import tee

import requests
from pymongo.database import Database

from src import factory
from src.find.site import Site


logger = logging.getLogger('Collect')


class ReaderBase(ABC):
    def __init__(self, mongo_db: Database, ticker):
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

        self._collector = factory.Factory.get_collector(self.name)

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
            .drop(self._collector.get_drop_keys(), axis='columns', errors='ignore')

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
        for column, layers in self._collector.get_nested_keys().items():
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
            try:
                shifted_history.columns = history.columns
            except Exception as e:
                logger.warning("Couldn't reindex columns")
                logger.exception(e)

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
        except (arrow.ParserError, TypeError, ValueError):
            return value

    @staticmethod
    def get_last_price(ticker):
        url = Site('prices',
                   'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                   is_otc=True).get_ticker_url(ticker)

        response = requests.get(url)
        previous_close = response.json().get('previousClose')

        if previous_close:
            return float(previous_close)
        else:
            logger.warning("Couldn't get last price of {ticker}".format(ticker=ticker))
            return 0