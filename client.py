import argparse
import logging
import os

import pandas

from collect import Collect
from src.collect.collector_base import CollectorBase

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'client.log')


def main():
    args = get_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    else:
        logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(message)s')

    pandas.set_option('display.expand_frame_repr', False)

    mongo_db = Collect.init_mongo(args.uri)

    if args.history:
        print(get_history(mongo_db, args.history).to_string())
    else:
        print(get_diffs(mongo_db).to_string())


def get_history(mongo_db, ticker):
    history = pandas.DataFrame()

    for collection_name, collector in Collect.COLLECTORS.items():
        collector = collector(mongo_db, collection_name, ticker)
        current = collector.get_sorted_history()

        if current.empty:
            continue
        elif history.empty:
            history = current.set_index('date')
        else:
            history = history.join(current.set_index('date'),
                                   lsuffix='_Unknown', rsuffix='_' + collection_name, how='outer').dropna()

    return history


def get_diffs(mongo_db):
    # Pulling from diffs collection
    df = pandas.DataFrame(mongo_db.diffs.find()).drop("_id", axis='columns')

    # Prettify timestamps
    df["old"] = df["old"].apply(CollectorBase.timestamp_to_datestring)
    df["new"] = df["new"].apply(CollectorBase.timestamp_to_datestring)

    return df


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
    parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
    parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)
    parser.add_argument('--verbose', dest='verbose', help='Print logs', default=False, action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    main()
