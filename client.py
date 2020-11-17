import argparse
import logging
import os
import requests
import pandas
import xml.etree.ElementTree as ET

from collect import Collect
from src.collect.collector_base import CollectorBase
from src.collect.collectors.securities import Securities
from src.find.site import Site

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'client.log')
LOW_FLOATERS_001_1B_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_1B.csv')
LOW_FLOATERS_001_500M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_500M.csv')
LOW_FLOATERS_003_250M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters003_250M.csv')


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
        print(get_history(mongo_db, args.history, args.filters).to_string())
    elif args.low_floaters:
        get_low_floaters(mongo_db)
        print('low floaters file can be found in:', LOW_FLOATERS_PATH)
    else:
        print(get_diffs(mongo_db).to_string())


def get_history(mongo_db, ticker, apply_filters):
    history = pandas.DataFrame()

    for collection_name, collector in Collect.COLLECTORS.items():
        collector = collector(mongo_db, collection_name, ticker)
        current = collector.get_sorted_history(apply_filters)

        if current.empty:
            continue
        elif history.empty:
            history = current.set_index('date')
        else:
            history = history.join(current.set_index('date'),
                                   lsuffix='_Unknown', rsuffix='_' + collection_name, how='outer').dropna()

    return history


def get_low_floaters(mongo_db):
    tickers_001_1B = pandas.DataFrame(columns=['Symbol'])
    tickers_001_500M = pandas.DataFrame(columns=['Symbol'])
    tickers_003_250M = pandas.DataFrame(columns=['Symbol'])

    for ticker in Collect.extract_tickers(None):
        try:
            history = Securities(mongo_db, 'securities', ticker).get_sorted_history(False)
            outstanding = int(history.tail(1)['outstandingShares'].values[0])
            last_price = get_last_price(ticker)
            if last_price <= 0.001 and outstanding <= 1000000000:
                tickers_001_1B = tickers_001_1B.append({'Symbol': ticker}, ignore_index=True)
            if last_price <= 0.001 and outstanding <= 500000000:
                tickers_001_500M = tickers_001_500M.append({'Symbol': ticker}, ignore_index=True)
            if last_price <= 0.003 and outstanding <= 250000000:
                tickers_003_250M = tickers_003_250M.append({'Symbol': ticker}, ignore_index=True)
        except Exception as e:
            logging.exception(e, exc_info=True)

    with open(LOW_FLOATERS_001_1B_PATH, 'w') as tmp:
        tickers_001_1B.to_csv(tmp)
    with open(LOW_FLOATERS_001_500M_PATH, 'w') as tmp:
        tickers_001_500M.to_csv(tmp)
    with open(LOW_FLOATERS_003_250M_PATH, 'w') as tmp:
        tickers_003_250M.to_csv(tmp)


def get_last_price(ticker):
    url = Site('prices',
               "https://content1.edgar-online.com/cfeed/ext/charts.dll?81-0-0-0-0-A09301600-03NA000000{"
               "ticker}&SF:1000-FREQ=6-STOK=nupMb60cogGHY+0j6buIfRuhv9GBqT4oy+o+Pb9XZ7yxwhApAuD2i7kfKWnQCb9e"
               "-1605554241046",
               is_otc=True).get_ticker_url(ticker)

    response = requests.get(url)
    xml_tree = ET.fromstring(response.content)
    return float(xml_tree.find('security/securityInfo/securityDataSet/securityData').get('previousClose'))


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
    parser.add_argument('--low_floaters', dest='low_floaters', help='Get a list of light low float stocks', default=False,
                        action='store_true')
    parser.add_argument('--filters', dest='filters', help='Do you want to apply filters on the history?',
                        default=True, action='store_false')

    return parser.parse_args()


if __name__ == '__main__':
    main()
