import argparse
import logging
import os

import arrow
import pandas
import pause
from pymongo import MongoClient

from src.alert.ticker_history import TickerHistory
from src.find.site import Site, InvalidTickerExcpetion

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'alert.log')
DEFAULT_MONGO_PORT = 27017
DEFAULT_MONGO_HOST = 'localhost'
DB_NAME = 'stocker'


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    tickers = extract_tickers(args.csv)
    alert_tickers(tickers, args.debug)


def alert_tickers(args, debug=False):
    mongo_db = MongoClient('mongodb://{user}:{pwd}@{host}:{port}/{db}'.format(
        user=args.user,
        pwd=args.pwd,
        host=DEFAULT_MONGO_HOST,
        port=DEFAULT_MONGO_PORT,
        db=DB_NAME
    )).stocker

    # arrow.floor allows us to ignore minutes and seconds
    next_hour = arrow.now().floor('hour')

    while True:
        if not debug:
            next_hour = next_hour.shift(hours=1)
            pause.until(next_hour.timestamp)

        for ticker in args.tickers_list:
            try:
                with TickerHistory(ticker, mongo_db) as ticker_history:
                    if debug:
                        print('running on {ticker}'.format(ticker=ticker))
                    if ticker_history.is_changed():
                        mongo_db.diffs.insert_one(ticker_history.get_changes())
            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))
            except Exception as e:
                logging.warning('Exception on {ticker}: {e}'.format(ticker=ticker, e=e))

        if debug:
            break


def extract_tickers(csv_path):
    try:
        df = pandas.read_csv(csv_path)
        return df.Symbol.apply(lambda ticker: ticker.upper())
    except Exception:
        raise Exception('Invalid csv file - validate the path and that the tickers are under a column named symbol')


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', dest='csv', help='path to csv tickers file', required=True)
    parser.add_argument('--change', dest='change', help='Whether a changed occur in the ticker parameters', default='')
    parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
    parser.add_argument('--user', dest='user', help='username for MongoDB')
    parser.add_argument('--pass', dest='pwd', help='password for MongoDB')
    return parser.parse_args()


if __name__ == '__main__':
    main()
