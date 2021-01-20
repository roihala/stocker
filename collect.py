#!/usr/bin/env python3
import logging

import arrow
import json
import pymongo
import telegram
import requests
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from runnable import Runnable
from src.factory import Factory
from src.alert.daily_alerter import DailyAlerter
from apscheduler.schedulers.blocking import BlockingScheduler

from utils import disable_apscheduler_logs


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

        disable_apscheduler_logs()

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

        for collection_name in Factory.COLLECTIONS.keys():
            try:
                self.collect(ticker, collection_name, date)

            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                self.logger.exception(e, exc_info=True)

    def collect(self, ticker, collection_name, date, sub_collection=None, father_data=None):
        """
        Collecting and alerting data for specific ticker and collection

        :param ticker: Any of ticker.csv
        :param collection_name: One of our collections, described in Factory.COLLECTIONS
        :param date: Shared date, for aggregations
        :param sub_collection: In order to collections hierarchy
        :param father_data: In order to request data only once for sub collections
        """
        collection_args = {'mongo_db': self._mongo_db, 'ticker': ticker, 'date': date, 'debug': self._debug}
        collector = Factory.collectors_factory(collection_name, sub_collection, **collection_args)

        current = collector.fetch_data(data=father_data)
        latest = collector.get_latest()

        if current != latest:
            collector.save_data(current)

        alerter = Factory.alerters_factory(collection_name, sub_collection, **collection_args)
        alerts = alerter.get_alerts(latest=latest, current=current)

        if alerts and not isinstance(alerter, DailyAlerter):
            self.__telegram_alert(ticker, alerts)

        # Supporting one layer of sub collections
        if sub_collection is None and father_data is None:
            for sub_collection in Factory.get_sub_collections(collection_name):
                self.collect(ticker, collection_name, date, sub_collection, father_data=collector.raw_data)

    def __telegram_alert(self, ticker, alerts):
        # User-friendly message
        msg = '{alert_emoji} Detected change on {ticker}:\nstock price = {price}\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                           ticker=ticker,
                                                                           price=json.loads(requests.get('https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',ticker=ticker).text)['previousClose'],
                                                                           alert=alerts)

        if self._debug:
            self._telegram_bot.sendMessage(chat_id=1151317792, text=msg,
                                           parse_mode=telegram.ParseMode.MARKDOWN)
            self._telegram_bot.sendMessage(chat_id=480181908, text=msg,
                                           parse_mode=telegram.ParseMode.MARKDOWN)
            self._telegram_bot.sendMessage(chat_id=622163634, text=msg,
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
