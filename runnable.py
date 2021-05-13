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
    PROXY_USERNAME = "yonisoli"
    PROXY_PASSWORD = "5ff06d-6ecc98-91006b-86dd29-388b2c"
    PROXY_RACK_DNS = "megaproxy.rotating.proxyrack.net:222"

    proxy_url = "http://{}:{}@{}".format(PROXY_USERNAME, PROXY_PASSWORD, PROXY_RACK_DNS)
    proxy = {"http": proxy_url,
             'https': proxy_url}

    def __init__(self, args=None):
        if os.getenv("ENV") == "production":
            self._debug = os.getenv('DEBUG', 'false').lower() == 'true'
            self._write = False
            self._mongo_db = self.init_mongo(os.environ['MONGO_URI'])
            self._telegram_bot = self.init_telegram(os.environ['TELEGRAM_TOKEN'])
            self._tickers_list = self.extract_tickers()

            logger = logging.getLogger(self.__class__.__name__)
            handler = logging.StreamHandler()
            logger.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            self.logger = logger
            self.disable_apscheduler_logs()

        else:
            self.args = args if args else self.create_parser().parse_args()
            self._debug = self.args.debug
            self._write = self.args.write
            self._mongo_db = self.init_mongo(self.args.uri)
            self._telegram_bot = self.init_telegram(self.args.token)
            self._tickers_list = self.extract_tickers(self.args.csv)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(os.path.dirname(__file__), 'credentials/stocker.json')

            if self.args.verbose:
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
            else:
                logging.basicConfig(filename=os.path.join(LOG_DIR, self.__class__.__name__), level=logging.INFO,
                                    format='%(asctime)s %(levelname)s %(message)s')

            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info('running {cls}'.format(cls=self.__class__))

    @abstractmethod
    def run(self):
        pass

    def create_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
        parser.add_argument('--write', dest='write', help='do you want to write? (overrides debug)', default=False, action='store_true')
        parser.add_argument('--verbose', dest='verbose', help='Print logs', default=False, action='store_true')
        parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
        parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)
        parser.add_argument('--csv', dest='csv', help='path to csv tickers file')

        return parser

    def init_mongo(self, mongo_uri):
        try:
            # Using selection timeout in order to check connectivity
            mongo_client = MongoClient(mongo_uri)

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
    def extract_tickers(csv=None):
        try:
            if not csv:
                csv = DEFAULT_CSV_PATH

            df = pandas.read_csv(csv)
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')

    @staticmethod
    def disable_apscheduler_logs():
        logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
