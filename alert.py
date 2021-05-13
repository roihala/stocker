import datetime
import json
import logging

import pandas
import pymongo
import telegram

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from runnable import Runnable

from src.factory import Factory
from src.read import readers
from src.read.reader_base import ReaderBase
from src.alert.tickers.alerters import Securities

from google.cloud.pubsub import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage


class Alert(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    MONEY_BAG_EMOJI_UNICODE = u'\U0001F4B0'
    TROPHY_EMOJI_UNICODE = u'\U0001F3C6'
    BANG_EMOJI_UNICODE = u'\U0001F4A5'

    PUBSUB_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/diff-updates-sub'

    def __init__(self):
        super().__init__()

        self._scheduler = BackgroundScheduler(executors={
            'default': ThreadPoolExecutor(10),
        }, timezone="Africa/Abidjan")

        self.disable_apscheduler_logs()

        self._scheduler.start()

        self._subscription_name = self.PUBSUB_SUBSCRIPTION_NAME + '-dev' if self._debug else self.PUBSUB_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()

    def run(self):
        streaming_pull_future = self._subscriber.subscribe(self._subscription_name, self.alert_batch)
        with self._subscriber:
            streaming_pull_future.result()

    def alert_batch(self, batch: PubSubMessage):
        diffs = json.loads(batch.data)
        self.logger.info('detected batch: {diffs}'.format(diffs=diffs))

        # Removing _id column from diffs that are going to be inserted to db
        raw_diffs = [{key: value for key, value in diff.items() if key != '_id'} for diff in diffs]

        try:
            ticker, price = self.__extract_ticker(diffs)
            if not self.is_relevant(ticker, price):
                batch.ack()
                return

            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'ticker': ticker, 'debug': self._debug}

            msg = self.generate_msg(diffs, alerter_args)

            if msg:
                self._mongo_db.diffs.insert_many(raw_diffs)
                delay = False if any([diff.get('source') == 'filings' for diff in raw_diffs]) else True
                self.__send_or_delay(self.__add_title(ticker, price, msg), delay=delay)

            batch.ack()
        except Exception as e:
            self.logger.warning("Couldn't alert diffs: {diffs}".format(diffs=diffs))
            self.logger.exception(e)
            batch.nack()

    @staticmethod
    def generate_msg(diffs, alerter_args, as_dict=False):
        """
        :param as_dict: Return the message as dict of {_id: msg}
        :param diffs: list of diffs
        :param alerter_args: e.g: {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'ticker': ticker, 'debug': self._debug}
        """
        messages = {} if as_dict else []

        for source in set([diff.get('source') for diff in diffs if diff.get('source')]):
            try:
                alerter = Factory.alerters_factory(source, **alerter_args)
                alerts = alerter.get_alert_msg([diff for diff in diffs if diff.get('source') == source], as_dict=as_dict)

                messages.update(alerts) if as_dict else messages.append(alerts)
            except Exception as e:
                logger = logging.getLogger(Factory.get_alerter(source).__class__.__name__)
                logger.warning(f"Couldn't generate msg {diffs}: {source}")
                logger.exception(e)

        return messages if as_dict else '\n\n'.join([value for value in messages])

    def __extract_ticker(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])
        if not len(tickers) == 1:
            raise ValueError("Batch consists more than one ticker: {tickers}".format(tickers=tickers))

        ticker = tickers.pop()
        return ticker, ReaderBase.get_last_price(ticker)

    def is_relevant(self, ticker, price):
        try:
            tier = readers.Securities(self._mongo_db, ticker).get_latest().get('tierDisplayName')
            tier_hierarchy = Securities.get_hierarchy()['tierDisplayName']
            relevant_tier = tier_hierarchy.index(tier) < tier_hierarchy.index('OTCQB')

        except (ValueError, AttributeError):
            relevant_tier = True

        # Will we alert this ticker?
        if price < 0.05 \
                and not (len(ticker) == 5 and ticker[-1] == 'F') \
                and relevant_tier:
            return True
        return False

    def __send_or_delay(self, msg, delay=True):
        if self._debug:
            self.__send_msg(self._mongo_db.telegram_users.find(), msg)
            return

        if delay:
            self.__send_msg(self._mongo_db.telegram_users.find({'delay': False}), msg)
            self.__send_delayed(self._mongo_db.telegram_users.find({'delay': True}), msg)
        else:
            self.__send_msg(self._mongo_db.telegram_users.find(), msg)

    def __send_delayed(self, delayed_users, msg):
        trigger = DateTrigger(run_date=datetime.datetime.utcnow() + datetime.timedelta(minutes=1))

        self._scheduler.add_job(self.__send_msg,
                                args=[delayed_users, msg],
                                trigger=trigger)

    def __send_msg(self, users_group, msg):
        for user in users_group:
            try:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
                                               parse_mode=telegram.ParseMode.MARKDOWN)

            except Exception as e:
                self.logger.warning(
                    "Couldn't alert {message} to {user} at {chat_id}:".format(user=user.get("user_name"),
                                                                              chat_id=user.get("chat_id"),
                                                                              message=msg))
                self.logger.exception(e)

    def __add_title(self, ticker, price, alert_msg):
        if pandas.DataFrame(self._mongo_db.diffs.find({'ticker': ticker})).empty:
            alert_msg = '{bang_emoji} First ever alert for this ticker\n'.format(
                bang_emoji=self.BANG_EMOJI_UNICODE) + alert_msg

        return '{title}\n' \
               '{alert_msg}'.format(title=self.generate_title(ticker, self._mongo_db, price), alert_msg=alert_msg)

    @staticmethod
    def generate_title(ticker, mongo_db, price=None):
        try:
            tier = readers.Securities(mongo_db, ticker).get_latest().get('tierDisplayName')
        except Exception as e:
            logging.warning(f"Couldn't get tier of {ticker}")
            logging.exception(e)
            tier = ''

        return '{alert_emoji} {ticker} ({money_emoji}{last_price}, {trophy_emoji}{tier}):'.format(
            alert_emoji=Alert.ALERT_EMOJI_UNICODE,
            ticker=ticker,
            money_emoji=Alert.MONEY_BAG_EMOJI_UNICODE,
            last_price=price if price else ReaderBase.get_last_price(ticker),
            trophy_emoji=Alert.TROPHY_EMOJI_UNICODE,
            tier=tier)


if __name__ == '__main__':
    Alert().run()
