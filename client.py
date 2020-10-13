import argparse
import logging
import os

import arrow
import pandas
from arrow import ParserError

from alert import init_mongo
from src.alert.ticker_history import TickerHistory

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'client.log')
DEFAULT_CLIENT_URI = 'mongodb://admin:admin123@51.91.11.169:27017/stocker'


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    pandas.set_option('display.expand_frame_repr', False)

    mongo_db = init_mongo(DEFAULT_CLIENT_URI)

    if args.history:
        history = TickerHistory(args.history, mongo_db).get_sorted_history(duplicates=True)
        history["date"] = history["date"].apply(__timestamp_to_datestring)
        print(history)

    else:
        print_diffs(mongo_db)


def print_diffs(mongo_db):
    df = pandas.DataFrame(mongo_db.diffs.find()).drop("_id", axis='columns')

    # Pretify timestamps
    df["old"] = df["old"].apply(__timestamp_to_datestring)
    df["new"] = df["new"].apply(__timestamp_to_datestring)

    print(df)


def __timestamp_to_datestring(value):
    try:
        return arrow.get(value).format()
    except (ParserError, TypeError):
        return value


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
    return parser.parse_args()


if __name__ == '__main__':
    main()
