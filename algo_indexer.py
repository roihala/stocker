import json
import os
import pickle
import string
import random

import arrow
import pymongo

from td.client import TDClient

from alert import Alert
from common_runnable import CommonRunnable
from src.algo.candles import Candles
from src.read import readers
from src.read.reader_base import ReaderBase

CHANGES_DIR = os.path.join(os.path.dirname(__file__), 'changes')
TD_CONSUMER_KEY = "BZ6HMHYVTYFA30KX7KZPEIZHJMGJDMEY"


class Algo(CommonRunnable):
    KEYS = ['phone', 'website', 'email', 'twitter', 'isDelinquent', 'isCaveatEmptor', 'verifiedProfile']

    def __init__(self, args=None):
        super().__init__(args)

        # Create a new session, credentials path is required.
        self.td_session = TDClient(
            client_id=TD_CONSUMER_KEY,
            redirect_uri='http://localhost',
            credentials_path=r"C:\Users\RoiHa\Downloads\Telegram Desktop\td_state.json"
        )

        # Login to the session
        self.td_session.login()

    def run(self):
        changes = self.get_changes(self.get_diffs())
        raw_avg = self.parse_changes(changes)
        by_keys = self.parse_changes_by_keys(changes)

    def parse_changes_by_keys(self, changes):
        keys = set([change['diff']['changed_key'] for _id, change in changes.items()])
        
        parsed = {}

        for key in keys:
            key_changes = {_id: change for _id, change in changes.items() if change['diff']['changed_key'] == key}
            parsed[key] = self.parse_changes(key_changes)

        return parsed

    def parse_changes(self, changes):
        averages = {
            1: sum([value['change'][1] for key, value in changes.items()]) / len(
                changes.keys()),
            2: sum(
                [value['change'][2] for key, value in changes.items()]) / len(changes.keys()),
            5: sum(
                [value['change'][5] for key, value in changes.items()]) / len(changes.keys()),
            10: sum(
                [value['change'][10] for key, value in changes.items()]) / len(changes.keys()),
            15: sum(
                [value['change'][15] for key, value in changes.items()]) / len(changes.keys())
        }

        return averages

    def get_changes(self, diffs, name=''):
        batches = ReaderBase.aggregate_as_batches(diffs)

        diffs = [item for sublist in batches for item in sublist]

        changes = {}
        for diff in diffs:
            try:
                changes[diff.get('_id')] = {
                    'change': self.get_change_by_period(diff.get('date'), diff.get('ticker')),
                    'diff': diff}

            except Exception as e:
                self.logger.warning(f"Couldn't get change by time for diff: {diff}")
                self.logger.exception(e)

        with open(os.path.join(CHANGES_DIR, f'{name if name else random.choice(string.ascii_letters)}.pkl'), 'wb') as fp:
            pickle.dump(changes, fp)

        return changes

    def get_change_by_period(self, date, ticker):
        res = self.td_session.get_price_history(
            start_date=arrow.get(date).timestamp * 1000,
            symbol=ticker,
            **{"period_type": 'day',
               "period": '1',
               "frequency_type": 'minute',
               "frequency": '1'})

        minute_candles = Candles(res['candles'], start_time=arrow.get(date).floor('minute'))
        return \
            {1: minute_candles.get_percentage_by_period(minutes=1),
             2: minute_candles.get_percentage_by_period(minutes=2),
             5: minute_candles.get_percentage_by_period(minutes=5),
             10: minute_candles.get_percentage_by_period(minutes=10),
             15: minute_candles.get_percentage_by_period(minutes=15)}

    def get_diffs(self, max_os=None, max_price=None, keys=None):
        diffs = []

        for diff in self._mongo_db.diffs.find({"date": {"$gte": arrow.utcnow().shift(days=-14).format()}}).sort('date', pymongo.DESCENDING):
            try:
                ticker = Alert.extract_ticker([diff], include_price=False)
                securities = readers.Securities(self._mongo_db, ticker).get_latest()
                key = diff.get('changed_key')
                if (int(securities['outstandingShares']) <= max_os if max_os else True) and \
                        (ReaderBase.get_last_price(diff.get('ticker') <= max_price) if max_price else True) and \
                        (key in keys if keys else True):
                    diffs.append(diff)

            except Exception as e:
                self.logger.warning(f"Couldn't get diff {diff}")
                self.logger.exception(e)

        return diffs


if __name__ == '__main__':
    Algo().run()
