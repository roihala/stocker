import argparse
import logging
import os
import pandas
from abc import abstractmethod, ABC

import pymongo
import telegram
from pymongo import MongoClient


LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))


class Runnable(ABC):
    def __init__(self, args=None):
        self.args = args if args else self.create_parser().parse_args()
        self._mongo_db = self.init_mongo(self.args.uri)
        self._telegram_bot = self.init_telegram(self.args.token)
        self._debug = self.args.debug
        self._tickers_list = self.extract_tickers(self.args.csv)

        if self.args.verbose:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        else:
            logging.basicConfig(filename=os.path.join(LOG_DIR, self.log_name), level=logging.INFO,
                                format='%(asctime)s %(levelname)s %(message)s')
        logging.info('running {cls}'.format(cls=self.__class__))

    @property
    @abstractmethod
    def log_name(self) -> str:
        pass

    @abstractmethod
    def run(self):
        pass

    def create_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
        parser.add_argument('--verbose', dest='verbose', help='Print logs', default=False, action='store_true')
        parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
        parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)

        return parser

    @staticmethod
    def init_mongo(mongo_uri):
        try:
            # Using selection timeout in order to check connectivity
            mongo_client = MongoClient(mongo_uri)

            # Forcing a connection to mongo
            mongo_client.server_info()

            return mongo_client.stocker

        except pymongo.errors.ServerSelectionTimeoutError:
            raise ValueError("Couldn't connect to MongoDB, check your credentials")

    @staticmethod
    def init_telegram(token):
        try:
            return telegram.Bot(token)
        except telegram.error.Unauthorized:
            raise ValueError("Couldn't connect to telegram, check your credentials")

    @staticmethod
    def extract_tickers(csv=None):
        try:
            if not csv:
                csv = DEFAULT_CSV_PATH

            df = pandas.read_csv(csv)
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')