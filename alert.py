import argparse
import logging
import os
import pymongo

import arrow
import pandas
import pause
from pymongo import MongoClient

from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'alert.log')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), 'tickers.csv')
DEFAULT_MONGO_PORT = 27017
DEFAULT_MONGO_HOST = 'localhost'
DB_NAME = 'stocker'


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    alert_tickers(args, args.debug)


def alert_tickers(args, debug=False):
    mongo_db = init_mongo(args.uri)

    # arrow.floor allows us to ignore minutes and seconds
    next_hour = arrow.now().floor('hour')
    tickers_list = extract_tickers(args)

    while True:
        if not debug:
            next_hour = next_hour.shift(hours=1)
            pause.until(next_hour.timestamp)

        for ticker in tickers_list:
            try:
                with TickerHistory(ticker, mongo_db) as ticker_history:
                    if debug:
                        print('running on {ticker}'.format(ticker=ticker))
                    if ticker_history.is_changed():
                        [mongo_db.diffs.insert_one(change) for change in ticker_history.get_changes()]
            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))
            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                logging.warning('Exception on {ticker}: {e}'.format(ticker=ticker, e=e))

        if debug:
            break


def init_mongo(mongo_uri=None):
    try:
        # Using selection timeout in order to check connectivity
        if mongo_uri:
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1)
        else:
            mongo_client = MongoClient(DEFAULT_MONGO_HOST, DEFAULT_MONGO_PORT, serverSelectionTimeoutMS=1)

        # Forcing a connection to mongo
        mongo_client.server_info()

        return mongo_client.stocker

    except pymongo.errors.ServerSelectionTimeoutError:
        raise Exception("Couldn't connect to MongoDB, check your credentials")


def extract_tickers(args):
    try:

        if args.csv:
            file_path = args.csv
        else:
            file_path = DEFAULT_CSV_PATH

        df = pandas.read_csv(file_path)
        return df.Symbol.apply(lambda ticker: ticker.upper())
    except Exception:
        raise Exception('Invalid csv file - validate the path and that the tickers are under a column named symbol')


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', dest='csv', help='path to csv tickers file')
    parser.add_argument('--change', dest='change', help='Whether a changed occur in the ticker parameters', default='')
    parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
    parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...')
    return parser.parse_args()


if __name__ == '__main__':
    main()
