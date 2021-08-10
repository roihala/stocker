# !/usr/bin/env python3
import logging
import os

from td.client import TDClient

from runnable import Runnable


class Priority(Runnable):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mongo_db = self.init_mongo(os.environ['MONGO_URI'])

        # Create a new session, credentials path is required.
        self.td_session = TDClient(
            client_id="BZ6HMHYVTYFA30KX7KZPEIZHJMGJDMEY",
            redirect_uri='http://localhost',
            credentials_path='./credentials/td_state.json')

        self.td_session.login()

    def get_tickers_bid_ask(self, tickers):
        stock_data = self.td_session.get_quotes(instruments=tickers)
        result = {}
        for ticker in stock_data:
            result[ticker] = {'ask': stock_data[ticker]['askPrice'],
                              'bid': stock_data[ticker]['bidPrice']}

        return result

    def run(self):
        pass

    def save_ticker(self, ticker: str, priority: int):
        query = {'ticker': ticker}
        db_record = {'ticker': ticker, 'priority': priority}
        self._mongo_db.priority.find_one_and_replace(query, db_record, upsert=True)


def main():
    try:
        a = Priority()
        res = a.get_tickers_bid_ask(["AZFL", "LEAS"])
        print(res)
    except Exception as e:
        logging.exception(e)
        logging.error(e)


if __name__ == '__main__':
    main()
