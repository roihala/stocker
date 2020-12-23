import argparse
import logging
import os
import requests
import pandas

from collect import Collect
from runnable import Runnable
from src.collect.collector_base import CollectorBase
from src.collect.collectors.prices import Prices
from src.collect.collectors.securities import Securities
from src.find.site import Site

LOW_FLOATERS_001_1B_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_1B.csv')
LOW_FLOATERS_001_500M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_500M.csv')
LOW_FLOATERS_003_250M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters003_250M.csv')
TICKERS_0006_3B_CURRENT_PATH = os.path.join(os.path.dirname(__file__), 'tickers_0006_3B_current.csv')


class Client(Runnable):
    def __init__(self):
        super().__init__()
        pandas.set_option('display.expand_frame_repr', False)

    @property
    def log_name(self) -> str:
        return 'client.log'

    def run(self):
        if self.args.history:
            print(self.get_history(self._mongo_db, self.args.history, self.args.filters).to_string())
        elif self.args.low_floaters:
            self.get_low_floaters(self._mongo_db, Collect.extract_tickers(self.args.csv))
            print('low floaters lists are ready')
        else:
            print(self.get_diffs(self._mongo_db).to_string())

    def create_parser(self):
        parser = super().create_parser()

        parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
        parser.add_argument('--low_floaters', dest='low_floaters', help='Get a list of light low float stocks',
                            default=False,
                            action='store_true')
        parser.add_argument('--filters', dest='filters', help='Do you want to apply filters on the history?',
                            default=True, action='store_false')
        parser.add_argument('--csv', dest='csv', help='path to csv tickers file')
        return parser

    @staticmethod
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

    @staticmethod
    def get_low_floaters(mongo_db, tickers_list):
        tickers_001_1B = pandas.DataFrame(columns=['Symbol'])
        tickers_001_500M = pandas.DataFrame(columns=['Symbol'])
        tickers_003_250M = pandas.DataFrame(columns=['Symbol'])
        tickers_0006_3B_current = pandas.DataFrame(columns=['Symbol'])

        for ticker in tickers_list:
            try:
                logging.info('running on {ticker}'.format(ticker=ticker))

                securities = Securities(mongo_db, 'securities', ticker).get_latest()
                outstanding, tier_code = int(securities['outstandingShares']),  securities['tierCode']
                last_price = Prices(mongo_db, 'prices', ticker).get_latest()['previousClose']

                if last_price <= 0.001 and outstanding <= 1000000000:
                    tickers_001_1B = tickers_001_1B.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.001 and outstanding <= 500000000:
                    tickers_001_500M = tickers_001_500M.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.003 and outstanding <= 250000000:
                    tickers_003_250M = tickers_003_250M.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.0006 and outstanding >= 3000000000 and tier_code == 'PC':
                    tickers_0006_3B_current = tickers_0006_3B_current.append({'Symbol': ticker}, ignore_index=True)

            except Exception as e:
                logging.exception('ticker: {ticker}'.format(ticker=ticker), e, exc_info=True)

        with open(LOW_FLOATERS_001_1B_PATH, 'w') as tmp:
            tickers_001_1B.to_csv(tmp)
        with open(LOW_FLOATERS_001_500M_PATH, 'w') as tmp:
            tickers_001_500M.to_csv(tmp)
        with open(LOW_FLOATERS_003_250M_PATH, 'w') as tmp:
            tickers_003_250M.to_csv(tmp)
        with open(TICKERS_0006_3B_CURRENT_PATH, 'w') as tmp:
            tickers_0006_3B_current.to_csv(tmp)

    @staticmethod
    def get_last_price(ticker):
        url = Site('prices',
                   'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                   is_otc=True).get_ticker_url(ticker)

        response = requests.get(url)
        return float(response.json().get('previousClose'))

    @staticmethod
    def get_diffs(mongo_db, ticker=None):
        # Pulling from diffs collection
        alerts = pandas.DataFrame(mongo_db.diffs.find()).drop("_id", axis='columns')
        if ticker:
            alerts = alerts[alerts['ticker'] == ticker]

        # Dropping unnecessary columns
        alerts = alerts.drop(['diff_type', 'source'], axis=1)

        # Prettify timestamps
        alerts['new'] = alerts.apply(
            lambda row: CollectorBase.timestamp_to_datestring(row['new']) if 'Date' in row['changed_key'] else row['new'],
            axis=1)
        alerts['old'] = alerts.apply(
            lambda row: CollectorBase.timestamp_to_datestring(row['old']) if 'Date' in row['changed_key'] else row['old'],
            axis=1)

        return alerts


def main():
    try:
        Client().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
