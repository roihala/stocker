#!/usr/bin/env python3
import logging
from functools import reduce

import arrow
import pymongo
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from runnable import Runnable
from src.factory import Factory
from apscheduler.schedulers.blocking import BlockingScheduler


class Collect(Runnable):
    def run(self):
        if self._debug:
            for ticker in self._tickers_list:
                self.ticker_collect(ticker)
            return

        scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(10000)
        })

        self.disable_apscheduler_logs()

        trigger = OrTrigger([IntervalTrigger(minutes=10, jitter=300), DateTrigger()])

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

        all_sons = reduce(lambda x, y: x + y.get_sons(), Factory.get_collectors(), [])

        for collection_name in Factory.COLLECTIONS.keys():
            try:
                if collection_name in all_sons:
                    continue

                collector_args = {'mongo_db': self._mongo_db, 'ticker': ticker, 'date': date, 'debug': self._debug, 'write': self._write}
                collector = Factory.collectors_factory(collection_name, **collector_args)
                collector.collect()

            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                self.logger.warning("Couldn't collect {collection} for {ticker}".format(
                    collection=collection_name, ticker=ticker))
                self.logger.exception(e, exc_info=True)


def main():
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
