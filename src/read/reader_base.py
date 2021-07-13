import logging
from copy import deepcopy
from json import JSONDecodeError

from retry import retry

import arrow
import pandas
import pymongo

from abc import ABC
from itertools import tee

import requests
from pymongo.database import Database

from runnable import Runnable
from src import factory
from src.find.site import Site


logger = logging.getLogger('Collect')


class ReaderBase(ABC):
    INDEX_KEYS = ['_id', 'date', 'ticker']

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
        self._alerter = factory.Factory.get_alerter(self.name)
        self._sorted_history = None

    def get_sorted_history(self, filter_rows=False, filter_cols=False, ignore_latest=False):
        """
        Returning sorted history with the ability of filtering consecutive rows and column duplications

        ** NOTE THAT NESTED KEYS WILL BE FLATTENED IN ORDER TO FILTER!

        :param filter_rows: bool
        :param filter_cols: bool
        :param ignore_latest: Ignore the latest entry
        :return: df
        """
        if isinstance(self._sorted_history, pandas.DataFrame):
            return self._sorted_history

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

        self._sorted_history = history
        return history

    def get_entry_by_date(self, date):
        self.get_sorted_history()

        idx = self._sorted_history.index[self._sorted_history['date'] == date].tolist()
        if len(idx) != 1:
            raise AttributeError("There should be a single index for each date")

        idx = idx[0]

        return self._sorted_history.loc[idx - 1].to_dict(), self._sorted_history.loc[idx].to_dict()

    def flatten(self, history):
        for column, layers in self._collector.get_nested_keys().items():
            if column in history.columns:
                history[column] = pandas.Series(
                    {date: self.__unfold(value, tee(iter(layers))[1]) for date, value in
                     history[column].dropna().to_dict().items()})

        history.index.name = 'date'

        return history

    def generate_msg(self):
        return ''

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
            history = history.drop(cols_to_drop, axis=1)

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

    def get_latest(self, clear_nans=True, remove_index=False):
        try:
            latest = self.collection.find({"ticker": self.ticker}).sort("date", pymongo.DESCENDING).limit(1)[0]

            if clear_nans:
                latest = {k: v for k, v in latest.items() if v == v}

            if remove_index:
                [latest.pop(key) for key in list(latest) if key in self.INDEX_KEYS]

            return latest

        except IndexError:
            logger.info(f"No latest {self.name} for {self.ticker}")
        except Exception as e:
            logger.warning(f"Couldn't get latest of {self.ticker}")
            logger.exception(e)

    @staticmethod
    def timestamp_to_datestring(value):
        try:
            return arrow.get(value).format()
        except (arrow.ParserError, TypeError, ValueError):
            return value

    @staticmethod
    @retry((JSONDecodeError, requests.exceptions.ProxyError), tries=5, delay=1)
    def get_last_price(ticker):
        url = Site('prices',
                   'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                   is_otc=True).get_ticker_url(ticker)

        response = requests.get(url)

        try:
            # Trying with proxy
            if response.status_code == 429:
                response = requests.get(url, proxies=Runnable.proxy)

            if response.json().get('lastSale'):
                return float(response.json().get('lastSale'))
            elif response.json().get('previousClose'):
                return float(response.json().get('previousClose'))
            else:
                logger.warning("Couldn't get last price of {ticker}".format(ticker=ticker))
                return 0
        except Exception as e:
            logger.warning("Couldn't get last price of {ticker}".format(ticker=ticker))
            logging.exception(e)
            return 0

    @staticmethod
    def escape_markdown(msg):
        return msg.replace("_", "\\_").replace("[", "\\[").replace("`", "\\`").replace("*", "\\*")

    @staticmethod
    def get_stocker_date(date, format='YYYY-MM-DD HH:MM', timezone='US/Eastern'):
        date = arrow.get(date).to(timezone)
        return f"*{date.format(format)}*"

    @staticmethod
    def aggregate_as_batches(diffs):
        pandas.set_option('display.expand_frame_repr', False)
        df = pandas.DataFrame(diffs)
        df = df[df.changed_key == df.changed_key]

        grouped = df.groupby(['date', 'ticker'])
        groups = [grouped.get_group(_).to_dict('records') for _ in grouped.groups]

        to_pop = []
        for index, group in enumerate(groups):
            for i, _ in enumerate(deepcopy(groups)[index + 1:]):
                if group[0]['ticker'] == _[0]['ticker'] and arrow.get(group[0]['date']).date() == arrow.get(_[0]['date']).date():
                    to_pop.append(index + 1 + i)

        [groups.pop(_) for _ in sorted(to_pop, reverse=True)]

        return groups
