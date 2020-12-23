#!/usr/bin/env python3
import argparse
import logging
import os
import arrow
import pymongo
import pandas
import telegram

from runnable import Runnable
from src.collect.collector_base import CollectorBase
from src.collect.collectors.profile import Profile
from src.collect.collectors.securities import Securities
from src.collect.collectors.symbols import Symbols
from src.collect.collectors.prices import Prices

DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))


class Collect(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'

    COLLECTORS = {'symbols': Symbols,
                  'profile': Profile,
                  'prices': Prices,
                  'securities': Securities}

    def __init__(self):
        super().__init__()
        self._tickers_list = self.extract_tickers(self.args.csv)

    @property
    def log_name(self) -> str:
        return 'collect.log'

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument('--csv', dest='csv', help='path to csv tickers file')
        return parser

    def run(self):
        self.collect_all()

    def collect_all(self):
        for ticker in self._tickers_list:
            # Using date as a key for matching entries between collections
            date = arrow.utcnow()

            for collection, obj in self.COLLECTORS.items():
                collector = obj(self._mongo_db, collection, ticker, date, self._debug)
                self.collect(collector)

    def collect(self, collector: CollectorBase):
        try:
            collector.collect()

            diffs = collector.get_diffs()

            if diffs:
                logging.info('diffs: {diffs}'.format(diffs=diffs))

                if not self._debug:
                    # Insert the new diffs to mongo
                    [self._mongo_db.diffs.insert_one(diff) for diff in diffs]

                # Alert every registered user
                [self.__telegram_alert(diff) for diff in diffs]

        except pymongo.errors.OperationFailure as e:
            raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
        except Exception as e:
            logging.exception(e, exc_info=True)

    def __telegram_alert(self, change):
        # User-friendly message
        msg = '{alert_emoji} Detected change on {ticker}:\n' \
              '*{key}* has changed:\n' \
              ' {old} {fast_forward}{fast_forward}{fast_forward} {new}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                               fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                                                                               ticker=change.get('ticker'),
                                                                               key=change.get('changed_key'),
                                                                               old=change.get('old'),
                                                                               new=change.get('new'))

        if self._debug:
            self._telegram_bot.sendMessage(chat_id=1151317792, text=msg,
                                           parse_mode=telegram.ParseMode.MARKDOWN)
            self._telegram_bot.sendMessage(chat_id=480181908, text=msg,
                                           parse_mode=telegram.ParseMode.MARKDOWN)
            return

        for user in self._mongo_db.telegram_users.find():
            try:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
                                               parse_mode=telegram.ParseMode.MARKDOWN)

            except Exception as e:
                logging.exception(e)

    @staticmethod
    def extract_tickers(csv):
        try:
            if csv:
                file_path = csv
            else:
                file_path = DEFAULT_CSV_PATH

            df = pandas.read_csv(file_path)
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')


def main():
    logging.info('Starting Collect')

    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
