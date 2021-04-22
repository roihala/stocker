import argparse
import logging
import os
import pandas
import json
import requests
from abc import abstractmethod, ABC

import pymongo
import telegram
from pymongo import MongoClient
from src.find.site import Site



LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))

TDAMERITRADE_API_KEY = "7GF2GJN60ZAP2F9E4V7IXDMFZD5M6GQR"
TDAMERITRADE_SYMBOL = 'https://api.tdameritrade.com/v1/marketdata/quotes?apikey={api_key}&symbol={tickers_list}'

TICKER_GROUP = 500
TICKERS_API_DELIMITER = "%2C"

class Runnable(ABC):
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

            df = Runnable._get_tradeable_tickers(pandas.read_csv(csv))
            
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')

    @staticmethod
    def _get_tradeable_tickers(df):
        tradeable_tickers = []
        tickers_to_check = []
        print("Checking tickers...")
        for index, row in df.iterrows():
            tickers_to_check.append(row["Symbol"])

            if (index + 1) % TICKER_GROUP == 0:
                tdameritrade_site = Site("tdameritrade",
                            TDAMERITRADE_SYMBOL,
                            is_otc=False, api_key=TDAMERITRADE_API_KEY)
                try:
                    tradeable_tickers.extend(json.loads(requests.get(
                        tdameritrade_site.get_tickers_list_url(tickers_to_check)).content).keys())
                except Exception as e:
                    # In case there is some problem with retrieving the tradeable
                    # tickers we'll take all the tickers
                    tradeable_tickers.extend(tickers_to_check)
                tickers_to_check = []

        print(f"Out of {index + 1} tickers in the CSV, {len(tradeable_tickers)} are tradeable.")
        return df[df["Symbol"].isin(tradeable_tickers)]


    @staticmethod
    def disable_apscheduler_logs():
        logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
