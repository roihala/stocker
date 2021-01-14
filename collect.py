#!/usr/bin/env python3
import logging

import arrow
import pymongo
import telegram
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from runnable import Runnable
from src.factory import Factory
from src.alert.daily_alerter import DailyAlerter
from apscheduler.schedulers.blocking import BlockingScheduler


class Collect(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'

    def run(self):
        if self._debug:
            for ticker in self._tickers_list:
                self.ticker_collect(ticker)
            return

        scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(10000)
        })

        trigger = OrTrigger([IntervalTrigger(minutes=10, jitter=60), DateTrigger()])

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

        for collection_name in Factory.COLLECTIONS.keys():
            try:
                collection_args = {'mongo_db': self._mongo_db, 'ticker': ticker, 'date': date, 'debug': self._debug}
                collector = Factory.colleectors_factory(collection_name, **collection_args)
                current, latest = collector.collect()

                alerter = Factory.alerters_factory(collection_name, **collection_args)
                alerts = alerter.get_alerts(latest=latest, current=current)

                if alerts and not isinstance(alerter, DailyAlerter):
                    self.__telegram_alert(ticker, alerts)

            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                self.logger.exception(e, exc_info=True)

    def __telegram_alert(self, ticker, alerts):
        # User-friendly message
        msg = '{alert_emoji} Detected change on {ticker}:\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                           ticker=ticker,
                                                                           alert=alerts)

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
                self.logger.exception(e)


def main():
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
