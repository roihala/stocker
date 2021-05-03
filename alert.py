import datetime
import json

import pandas
import telegram

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from runnable import Runnable
from src.factory import Factory
from src.read import readers
from src.read.reader_base import ReaderBase

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

        try:
            ticker = self.__extract_ticker(diffs)

            msg = ''

            for source in set([diff.get('source') for diff in diffs]):
                alert = self.__get_alert_by_source(source, ticker, diffs)

                if alert:
                    msg = msg + '\n\n' + alert if msg else alert

            if msg:
                self._mongo_db.diffs.insert_many(diffs)
                self.__send_or_delay(self.__add_title(ticker, msg))


            batch.ack()
        except Exception as e:
            self.logger.warning("Couldn't alert diffs: {diffs}".format(diffs=diffs))
            self.logger.exception(e)
            batch.nack()

    def __extract_ticker(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])
        if not len(tickers) == 1:
            raise ValueError("Batch consists more than one ticker: {tickers}".format(tickers=tickers))

        return tickers.pop()

    def __get_alert_by_source(self, source, ticker, diffs):
        try:
            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'ticker': ticker, 'debug': self._debug, 'batch': diffs}
            alerter = Factory.alerters_factory(source, **alerter_args)

            return alerter.get_alert_msg([diff for diff in diffs if diff.get('source') == source])

        except Exception as e:
            self.logger.warning("Couldn't create alerter for {diffs}".format(diffs=diffs))
            self.logger.exception(e)

    def __send_or_delay(self, msg):
        if self._debug:
            self.__send_msg(self._mongo_db.telegram_users.find(), msg)
            return

        self.__send_msg(self._mongo_db.telegram_users.find({'delay': False}), msg)
        self.__send_delayed(self._mongo_db.telegram_users.find({'delay': True}), msg)

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

    def __add_title(self, ticker, alert_msg):
        if pandas.DataFrame(self._mongo_db.diffs.find({'ticker': ticker})).empty:
            alert_msg = '{bang_emoji} First ever alert for this ticker\n'.format(
                bang_emoji=self.BANG_EMOJI_UNICODE) + alert_msg

        return '{alert_emoji} {ticker} ({money_emoji}{last_price}, {trophy_emoji}{tier}):\n' \
               '{alert_msg}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                    ticker=ticker,
                                    money_emoji=self.MONEY_BAG_EMOJI_UNICODE,
                                    last_price=ReaderBase.get_last_price(ticker),
                                    trophy_emoji=self.TROPHY_EMOJI_UNICODE,
                                    tier=readers.Securities(self._mongo_db, ticker).get_latest().get('tierDisplayName'),
                                    alert_msg=alert_msg)


if __name__ == '__main__':
    Alert().run()
