#!/usr/bin/env python3
import argparse
import logging
import os
import arrow
import pymongo
import pandas
import telegram
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from runnable import Runnable
from src.collect.collector_base import CollectorBase
from src.collect.collectors.profile import Profile
from src.collect.collectors.securities import Securities
from src.collect.collectors.symbols import Symbols
from src.collect.collectors.prices import Prices
from apscheduler.schedulers.blocking import BlockingScheduler

DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))

logger = logging.getLogger("collector")
handler = logging.StreamHandler()
logger.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)


class Collect(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'

    COLLECTORS = {'symbols': Symbols,
                  'profile': Profile,
                  'prices': Prices,
                  'securities': Securities}

    def __init__(self):

        if os.getenv("ENV") == "production":
            self._debug = False
            self._mongo_db = self.init_mongo(os.environ['MONGO_URI'])
            self._telegram_bot = self.init_telegram(os.environ['TELEGRAM_TOKEN'])

            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
            self._tickers_list = self.extract_tickers()
        else:
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
        scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(10000)
        })

        trigger = OrTrigger([IntervalTrigger(minutes=10), DateTrigger()])

        for ticker in self._tickers_list:
            scheduler.add_job(self.ticker_collect,
                              args=[ticker],
                              trigger=trigger,
                              max_instances=1,
                              misfire_grace_time=120)

        scheduler.start()

    def ticker_collect(self, ticker):
        # Using date as a key for matching entries between collections
        date = arrow.utcnow()

        for collection, obj in self.COLLECTORS.items():
            collector = obj(self._mongo_db, collection, ticker, date, self._debug)
            self.collect(collector)

    def collect(self, collector: CollectorBase):
        try:
            data = collector.collect()

            diffs = collector.get_diffs()

            if diffs:
                logger.info('diffs: {diffs}'.format(diffs=diffs))

                if not self._debug:
                    # Save the new data and the diffs to mongo
                    collector.collection.insert_one(data)
                    [self._mongo_db.diffs.insert_one(diff) for diff in diffs]

                # Alert every registered user
                [self.__telegram_alert(diff) for diff in diffs]

        except pymongo.errors.OperationFailure as e:
            raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
        except Exception as e:
            logger.exception(e, exc_info=True)

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
                logger.exception(e)

    @staticmethod
    def extract_tickers(csv=DEFAULT_CSV_PATH):
        try:
            df = pandas.read_csv(csv)
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')


def main():
    try:
        Collect().run()
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    main()
