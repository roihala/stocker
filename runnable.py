import argparse
import logging
import os
import pandas
from abc import abstractmethod, ABC

import pymongo
import certifi
import telegram
from pymongo import MongoClient

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))


class Runnable(ABC):
    # PROXY_USERNAME = "yonisoli"
    PROXY_USERNAME = "roihala"
    PROXY_PASSWORD = "ed219e-f3f65b-ee63e4-8c9349-e28bfe"
    PROXY_RACK_DNS = "megaproxy.rotating.proxyrack.net:222"

    http_proxy_packetstream = "http://yonisoli:QKzLinmMxlo3UqbH@proxy.packetstream.io:31112"

    proxy = {"http": http_proxy_packetstream,
             'https': http_proxy_packetstream}

    def __init__(self, args=None):
        if os.getenv("ENV") == "production":
            self._debug = os.getenv('DEBUG', 'false').lower() == 'true'
            self._tickers_list = self.extract_tickers()
            self.logger = self._init_logging()
            self.disable_apscheduler_logs()

        else:
            self.args = args if args else self.create_parser().parse_args()
            self._tickers_list = self.extract_tickers(self.args.csv if hasattr(self.args, 'csv') else None)
            self._debug = self.args.debug
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(os.path.dirname(__file__), 'credentials/stocker.json')

            if self.args.verbose:
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
            else:
                logging.basicConfig(filename=os.path.join(LOG_DIR, self.__class__.__name__), level=logging.INFO,
                                    format='%(asctime)s %(levelname)s %(message)s')

            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info('running {cls}'.format(cls=self.__class__))

    def _init_logging(self):
        logger = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        logger.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    @abstractmethod
    def run(self):
        pass

    def create_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
        parser.add_argument('--verbose', dest='verbose', help='Print logs', default=False, action='store_true')

        return parser

    def init_mongo(self, mongo_uri):
        try:
            # Using selection timeout in order to check connectivity
            mongo_client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

            # Forcing a connection to mongo
            mongo_client.server_info()

            if self._debug:
                return mongo_client.dev
            else:
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
    def extract_tickers(csv=None, as_df=False):
        try:
            if not csv:
                csv = DEFAULT_CSV_PATH

            df = pandas.read_csv(csv)
            df.Symbol = df.Symbol.astype(str).apply(lambda ticker: ticker.upper())
            if as_df:
                return df
            else:
                return df.Symbol
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')

    @staticmethod
    def disable_apscheduler_logs():
        logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
