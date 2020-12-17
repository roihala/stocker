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
            # merge_diffs is initialized for each ticker
            merge_diffs = []
            for collection, obj in self.COLLECTORS.items():
                collector = obj(self._mongo_db, collection, ticker, date, self._debug)
                # merge all collectors from the same ticker
                merge_diffs += self.collect(collector)

            if merge_diffs:
                logging.info('diffs: {diffs}'.format(diffs=merge_diffs))

                if not self._debug:
                    # Insert the new diffs to mongo
                    [self._mongo_db.diffs.insert_one(diff) for diff in merge_diffs]

                # Alert every registered user
                [self.__telegram_alert(self, merge_diffs)]

    def collect(self, collector: CollectorBase):
        try:
            collector.collect()

            diffs = collector.get_diffs()

            return diffs

        except pymongo.errors.OperationFailure as e:
            raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
        except Exception as e:
            logging.exception(e, exc_info=True)

    def __telegram_alert(self, diffs):

        # gets the header of the message
        msg = self.__header_message(diffs[0])

        for diff in diffs:
            # concatenate the key that has been changed to the header
            msg += self.__concatenate_message(diff)

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

    def __header_message(self, change):
        # return the header part of the message
        return '{alert_emoji} Detected change on {ticker}:\n'

    def __concatenate_message(self, change):
        # return the relevant part that needs to be concatenated to the header message
        return '*{key}* has changed:\n' \
               ' {old} {fast_forward}{fast_forward}{fast_forward} {new} \n'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                               fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                                                                               key=change.get('changed_key'),
                                                                               old=change.get('old'),
                                                                               new=change.get('new'))

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
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
