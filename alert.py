import argparse
import logging
import os
import time

import arrow
import pandas
import pause
import pytz

from src.alert.ticker_history import TickerHistory
from src.find.site import Site, InvalidTickerExcpetion

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'alert.log')


def main():
    logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO)

    args = get_args()

    tickers = extract_tickers(args.csv)

    # arrow.floor allows us to ignore minutes and seconds
    next_hour = arrow.now().floor('hour')

    while True:
        next_hour = next_hour.shift(hours=1)
        # pause.until(next_hour.timestamp)

        for ticker in tickers:
            try:
                with TickerHistory(ticker) as ticker_history:
                    if ticker_history.is_changed():
                        logging.info('{ticker} has changes: {changes}'.
                                     format(ticker=ticker, changes=ticker_history.get_changes()))
            except InvalidTickerExcpetion:
                logging.warning("There is no such ticker: {ticker}".format(ticker=ticker))

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

    return parser.parse_args()


if __name__ == '__main__':
    main()
