import argparse
import logging
import os

import pandas

from alert import Alert
from src.alert.ticker_history import TickerHistory
from stocker_alerts_bot import get_history

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'client.log')


def main():
    args = get_args()
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    pandas.set_option('display.expand_frame_repr', False)

    mongo_db = Alert.init_mongo(args.uri)

    if args.history:
        print(get_history(mongo_db, args.history).to_string())
    else:
        print(get_diffs(mongo_db).to_string())


def get_diffs(mongo_db):
    # Pulling from diffs collection
    df = pandas.DataFrame(mongo_db.diffs.find()).drop("_id", axis='columns')

    # Prettify timestamps
    df["old"] = df["old"].apply(TickerHistory.timestamp_to_datestring)
    df["new"] = df["new"].apply(TickerHistory.timestamp_to_datestring)

    return df


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
    parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
    parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)
    return parser.parse_args()


if __name__ == '__main__':
    main()
