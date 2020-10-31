import argparse
import logging
import os

import pandas

from alert import Alert
from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

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


def get_history(mongo_db, ticker):
    history_df = TickerHistory(ticker, mongo_db).get_sorted_history(duplicates=False)

    if history_df.empty:
        raise InvalidTickerExcpetion("No history for {ticker}".format(ticker=ticker))

    # Prettify timestamps
    history_df["date"] = history_df["date"].apply(TickerHistory.timestamp_to_datestring)
    if 'verifiedDate' in history_df:
        history_df["verifiedDate"] = history_df["verifiedDate"].dropna().apply(TickerHistory.timestamp_to_datestring)

    return history_filters(history_df)


def history_filters(history_df):
    # Filtering columns that doesn't have even one truth value
    any_columns = history_df.any()
    return history_df[any_columns[any_columns].index]


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
