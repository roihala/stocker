import argparse
import os, sys

current_directory = os.path.dirname(os.path.realpath(__file__))
rootDir = os.path.abspath(os.path.join(current_directory, '..'))

sys.path.append(os.path.abspath(os.path.join(current_directory, '..')))

from src.Gui.App import run_gui
from src.search import search_stock, SITES


def main():
    args = get_args()

    if args.console:
        search_stock(args.ticker, args.otc, args.exclude_sites, args.include_sites)
    else:
        run_gui()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', dest='ticker', help='Stock ticker to look up for', default='')
    parser.add_argument('--console', help='Run with console instead of GUI', default=False, action='store_true')
    parser.add_argument('--otc', dest='otc', help='Looking for OTC stocks?', default=False, action='store_true')
    parser.add_argument("--exclude_sites", help="Which websites you want to exclude?", nargs='+', choices=[site.name for site in SITES], default=[])
    parser.add_argument("--include_sites", help="Which websites you want to include?", nargs='+',
                        choices=[site.name for site in SITES], default=[])

    return parser.parse_args()


if __name__ == '__main__':
    main()
