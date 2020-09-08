import argparse
import os, sys

current_directory = os.path.dirname(os.path.realpath(__file__))
rootDir = os.path.abspath(os.path.join(current_directory, '..'))

sys.path.append(os.path.abspath(os.path.join(current_directory, '..')))

from src.Gui.App import run_gui
from src.search_tools import search_stock


def main():
    args = get_args()

    if not args.ticker:
        run_gui()
    else:
        search_stock(args.ticker)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', dest='ticker')

    return parser.parse_args()


if __name__ == '__main__':
    main()
