import arrow
import json
import pandas
import urllib
import urllib3
from urllib.error import HTTPError
import arrow
import pymongo
from arrow import ParserError
from pymongo.database import Database
from arrow import ParserError
import argparse
import logging
import os
import pandas
import sys
from pymongo import MongoClient
from src.alert.alert import init_mongo
from src.alert.ticker_history import TickerHistory

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'client.log')
DEFAULT_CLIENT_URI = 'mongodb://admin:admin123@51.91.11.169:27017/stocker'




def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    pandas.set_option('display.expand_frame_repr', False)

    mongo_db = init_mongo(DEFAULT_CLIENT_URI)

    if args.history:
        history = TickerHistory(args.history, mongo_db).get_sorted_history()
        if history.empty:
            raise Exception("No history for {ticker}".format(ticker=args.history))
        history["date"] = history["date"].apply(TickerHistory.timestamp_to_datestring)
        print(history.to_string())

    else:
        print_diffs(mongo_db)


def print_diffs(mongo_db):
    df = pandas.DataFrame(mongo_db.diffs.find()).drop("_id", axis='columns')

    # Pretify timestamps
    df["old"] = df["old"].apply(TickerHistory.timestamp_to_datestring)
    df["new"] = df["new"].apply(TickerHistory.timestamp_to_datestring)

    print(df.to_string())


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
    return parser.parse_args()


if __name__ == '__main__':
    main()
