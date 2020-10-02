import argparse
import time

from src.alert.ticker_history import TickerHistory
from src.find.site import Site


def main():
    args = get_args()

    args.ticker = args.ticker.upper()

    if not Site.is_ticker_exist(args.ticker):
        raise Exception("There is no such ticker: {ticker}".format(ticker=args.ticker))

    if args.debug:
        args.ticker = 'DPUI'

    with TickerHistory(args.ticker, args.debug) as ticker_history:
        if args.debug:
            print(ticker_history.is_changed())
            print(ticker_history.__get_history())
            print(ticker_history.get_changes())


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', dest='ticker', help='Stock ticker to look up for', required=True)
    parser.add_argument('--change', dest='change', help='Whether a changed occur in the ticker parameters', default='')
    parser.add_argument('--debug', dest='debug', help='debug mode', default=False, action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    main()
