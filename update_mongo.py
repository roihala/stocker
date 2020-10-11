import argparse
import json
import logging
import os
from json import JSONDecodeError


import pymongo
from pymongo import MongoClient
from pymongo.database import Database

import arrow
import pandas
import pause

from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'update_mongo.log')
DB_NAME = 'stocker'


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    try:
        # Defining max timeout to catch invalid connections
        client = MongoClient(args.uri, serverSelectionTimeoutMS=1)

        # Forcing a connection on mongo to test connectivity
        client.server_info()

        update_mongo(client, args.ticker_dir)

    except pymongo.errors.ServerSelectionTimeoutError:
        raise Exception("Please validate that MongoDB URI is valid")

    alert_tickers(args, args.debug)


def update_mongo(mongo_db: Database, tickers_dir):
    for json_file in os.listdir(tickers_dir):
        full_path = os.path.join(tickers_dir, json_file)
        try:
            with open(full_path) as ticker_data:
                json.load(ticker_data)

            TickerHistory()
        except (FileNotFoundError, JSONDecodeError):
            logging.warning("Invalid file: {file_path}".format(file_path=full_path))



def alert_tickers(args, debug=False):
    if args.user and args.pwd:
        mongo_db = MongoClient('mongodb://{user}:{pwd}@{host}:{port}/{db}'.format(
            user=args.user,
            pwd=args.pwd,
            host=DEFAULT_MONGO_HOST,
            port=DEFAULT_MONGO_PORT,
            db=DB_NAME
        )).stocker
    else:
        mongo_db = MongoClient(DEFAULT_MONGO_HOST, DEFAULT_MONGO_PORT).stocker

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
                        mongo_db.diffs.insert_one(ticker_history.get_changes())
            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))
            except Exception as e:
                logging.warning('Exception on {ticker}: {e}'.format(ticker=ticker, e=e))

        if debug:
            break


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
    parser.add_argument('--tickers_dir', dest='tickers_dir', help='Tickers directory to be loaded', required=True)
    parser.add_argument('--uri', dest='uri', help='URI for mongo', required=True)
    return parser.parse_args()


if __name__ == '__main__':
    main()
