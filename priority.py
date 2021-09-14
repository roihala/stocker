# !/usr/bin/env python3
import logging
import os
from copy import deepcopy

import arrow
import numpy
import pandas
import requests
from retry import retry

from td.client import TDClient

from client import Client
from common_runnable import CommonRunnable
from src.alert.tickers.alerters import Securities
from src.collect.tickers.collectors import Profile
from src.collector_factory import CollectorsFactory
from src.find.site import InvalidTickerExcpetion

ALL_TICKERS_CSV = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'all_tickers.csv'))


class PriorityCodes(object):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    IGNORE = 'ignore'


class Priority(CommonRunnable):
    ALL_TICKERS_URL = r'https://www.otcmarkets.com/research/stock-screener/api/downloadCSV?pageSize=20'
    TD_TICKERS_CHUNK = 300

    QUERY_COLUMNS = ['tierCode', 'isCaveatEmptor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create a new session, credentials path is required.
        self.td_session = TDClient(
            client_id="BZ6HMHYVTYFA30KX7KZPEIZHJMGJDMEY",
            redirect_uri='http://localhost',
            credentials_path=os.path.join(os.path.dirname(__file__), 'credentials/td_state.json'))

        self.td_session.login()

    def run(self):
        current_date = arrow.utcnow().floor(frame='days')

        # Updating all_tickers.csv file
        self.__update_all_tickers()

        # DataFrame with ticker, tierCode, isCaveatEmptor columns
        tickers = Client.get_latest_data(self._mongo_db.profile, as_df=True) \
            .reindex(['ticker'] + self.QUERY_COLUMNS, axis=1)

        # Merging last_seen values
        tickers_collection = pandas.DataFrame(self._mongo_db.tickers.find()).reindex(['ticker', 'last_seen'], axis=1)
        tickers = pandas.merge(tickers, tickers_collection, on='ticker', how='outer')
        tickers['last_seen'].fillna(current_date.shift(days=-1).format(), inplace=True)

        all_tickers = tickers['ticker']

        tier_code_hierarchy = Securities.get_hierarchy()['tierCode']
        # Getting tierCode <= PC (Pink Current)
        tickers = tickers[tickers['tierCode'].isin(tier_code_hierarchy[0:1 + tier_code_hierarchy.index('QB')])]

        # Removing F (bankrupt) tickers
        tickers = tickers[~((tickers['ticker'].str[-1] == 'F') & (tickers['ticker'].str.len() == 5))]

        # Filtering by price
        tickers = tickers.merge(self.__get_priced_tickers(tickers), how='left', on='ticker').fillna(0)
        tickers = tickers[(tickers['last_price'] < 0.5)]

        # Filtering out tickers that weren't seen for more than 3 days
        tickers['last_seen'][tickers['ticker'].apply(self.__is_existing_ticker)] = current_date.format()
        tickers = tickers[tickers['last_seen'].apply(lambda value: (current_date - arrow.get(value)).days < 1)]

        # Delaying bad tickers
        tickers['profile'] = numpy.where(tickers['tierCode'].isin(['EM', 'GM']) | tickers['isCaveatEmptor'] == True,
                                         PriorityCodes.MEDIUM, PriorityCodes.HIGH)
        tickers['symbols'] = numpy.where(tickers['tierCode'].isin(['EM', 'GM']) | tickers['isCaveatEmptor'] == True,
                                         PriorityCodes.IGNORE, PriorityCodes.HIGH)

        tickers = tickers[['ticker', 'last_seen'] + CollectorsFactory.get_father_collections()]

        self._mongo_db.tickers.delete_many({'ticker': {'$in': tickers['ticker'].tolist()}})
        self._mongo_db.tickers.insert_many(tickers.to_dict('records'))

        # Updating irrelevant tickers
        irrevant_tickers = pandas.Series(list(set(all_tickers) - set(tickers['ticker']))).to_frame('ticker')
        self._mongo_db.tickers.update_many({'ticker': {'$in': irrevant_tickers['ticker'].tolist()}},
                                           {'$set': {collection: PriorityCodes.IGNORE for collection in
                                                     CollectorsFactory.get_father_collections()}})

    def get_tickers_bid_ask(self, tickers):
        stock_data = self.td_session.get_quotes(instruments=tickers)
        result = {}
        for ticker in stock_data:
            result[ticker] = {'ask': stock_data[ticker]['askPrice'],
                              'bid': stock_data[ticker]['bidPrice'],
                              'last_price': stock_data[ticker]['lastPrice'],
                              'ask_size': stock_data[ticker]['askSize'],
                              'bid_size': stock_data[ticker]['bidSize'],
                              'total_volume': stock_data[ticker]['totalVolume']}

        return result

    def __get_priced_tickers(self, tickers: pandas.DataFrame):
        priced_tickers = pandas.DataFrame(columns=['ticker'])
        last_size = -1

        while last_size != priced_tickers.size:
            last_size = priced_tickers.size
            priced_tickers = self.__update_priced_tickers(tickers['ticker'], priced_tickers)

        return priced_tickers

    @retry(tries=5, delay=1)
    def __update_priced_tickers(self, tickers_series: pandas.Series, priced_tickers: pandas.DataFrame):
        relevant_tickers = pandas.Series(list(set(tickers_series).difference(set(priced_tickers['ticker']))))

        for i in range(max(1, int(len(relevant_tickers) / self.TD_TICKERS_CHUNK))):
            df = pandas.DataFrame(self.get_tickers_bid_ask(relevant_tickers[
                                                           i * self.TD_TICKERS_CHUNK: i * self.TD_TICKERS_CHUNK + self.TD_TICKERS_CHUNK])).transpose()
            df.index.name = 'ticker'
            df.reset_index(inplace=True)
            priced_tickers = pandas.concat([priced_tickers, df])

        return priced_tickers

    def __update_all_tickers(self):
        try:
            response = requests.get(self.ALL_TICKERS_URL)

            with open(ALL_TICKERS_CSV, 'wb') as f:
                f.write(response.content)

        except Exception as e:
            self.logger.warning("Couldn't update all_tickers.csv")
            self.logger.error(e)

    def __is_existing_ticker(self, ticker):
        try:
            Profile(ticker, mongo_db=self._mongo_db, cache={}, debug=self._debug).fetch_data()
        except InvalidTickerExcpetion as e:
            if e.response.status_code == 404:
                return False

        return True

    @staticmethod
    def __is_bad_ticker(row):
        return bool(row['tierCode'] in ['EM', 'GM'] or row['isCaveatEmptor'] is True)


def main():
    try:
        a = Priority()
        a.run()
    except Exception as e:
        logging.exception(e)
        logging.error(e)


if __name__ == '__main__':
    main()
