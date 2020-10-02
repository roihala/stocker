import argparse

from src.alert.ticker_history import TickerHistory


def main():
    args = get_args()

    alert = TickerHistory(args.ticker)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', dest='ticker', help='Stock ticker to look up for', default='')
    parser.add_argument('--change', dest='change', help='Whether a changed occur in the ticker parameters', default='')

    return parser.parse_args()


if __name__ == '__main__':
    main()
