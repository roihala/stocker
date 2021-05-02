import datetime
import json

import pandas
from typing import Iterable, List

import pymongo
import telegram

import arrow
from pymongo.change_stream import CollectionChangeStream

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

            msg = self.__init_msg(ticker)

            combined_ids = set()
            for source in set([diff.get('source') for diff in diffs]):
                ids, alert = self.__get_alert_by_source(source, ticker, diffs)

                if alert and ids:
                    msg = msg + '\n\n' + alert if msg else alert
                    combined_ids = combined_ids.union(ids)

            if combined_ids and msg:
                self.__send_or_delay(self.__add_title(ticker, msg), combined_ids)

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

    def __init_msg(self, ticker):
        msg = ''

        try:
            # Generate message if this ticker have never been alerted
            if pandas.DataFrame(self._mongo_db.diffs.find({'ticker': ticker, 'alerted': {'$eq': True}})).empty:
                msg = '{bang_emoji} First ever alert for this ticker'.format(bang_emoji=self.BANG_EMOJI_UNICODE)
        except Exception:
            pass
        return msg

    def __get_yesterday_diffs(self):
        diffs = pandas.DataFrame(
            self._mongo_db.diffs.find().sort('date', pymongo.ASCENDING))

        mask = (diffs['date'] > arrow.utcnow().shift(hours=-24).format()) & (diffs['date'] <= arrow.utcnow().format())

        return diffs.loc[mask].to_dict('records')

    def __unpack_stream(self, stream: CollectionChangeStream, first_event) -> List[dict]:
        event = first_event
        diffs = []

        while event is not None:
            self.logger.info('event: {event}'.format(event=event))

            diff = event.get('fullDocument')

            if event['operationType'] == 'insert' and diff.get('source') not in self.get_daily_alerters():
                diffs.append(diff)

            event = stream.try_next()

        return diffs

    def __get_alert_by_source(self, source, ticker, diffs):
        try:
            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'ticker': ticker, 'debug': self._debug, 'batch': diffs}
            alerter = Factory.alerters_factory(source, **alerter_args)

            return alerter.get_alert_msg([diff for diff in diffs if diff.get('source') == source])

        except Exception as e:
            self.logger.warning("Couldn't create alerter for {diffs}".format(diffs=diffs))
            self.logger.exception(e)

    def __send_or_delay(self, msg, alerts):
        if self._debug:
            self.__send_msg_with_ack(self._mongo_db.telegram_users.find(), msg, alerts)
            return

        self.__send_msg_with_ack(self._mongo_db.telegram_users.find({'delay': False}), msg, alerts)
        self.__send_delayed(self._mongo_db.telegram_users.find({'delay': True}), msg, alerts)

    def __send_delayed(self, delayed_users, msg, alerts):
        trigger = DateTrigger(run_date=datetime.datetime.utcnow() + datetime.timedelta(minutes=1))

        self._scheduler.add_job(self.__send_msg_with_ack,
                                args=[delayed_users, msg, alerts],
                                trigger=trigger)

    def __send_msg_with_ack(self, users_group, msg, alerts_ids):
        is_success = self.__send_msg(users_group, msg)

        if is_success:
            # Updating mongo that the diff has been alerted
            [self._mongo_db.diffs.update_one({'_id': object_id}, {'$set': {"alerted": True}}) for object_id in
             alerts_ids]

    def __send_msg(self, users_group, msg):
        is_sent_successfuly = False
        for user in users_group:
            try:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
                                               parse_mode=telegram.ParseMode.MARKDOWN)
                is_sent_successfuly = True

            except Exception as e:
                self.logger.warning("Couldn't send message to {user} at {chat_id}:".format(user=user.get("user_name"),
                                                                                           chat_id=user.get("chat_id")))
                self.logger.exception(e)

        return is_sent_successfuly

    def __add_title(self, ticker, alert_msg):
        return '{alert_emoji} {ticker} ({money_emoji}{last_price}, {trophy_emoji}{tier}):\n' \
               '{alert_msg}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                    ticker=ticker,
                                    money_emoji=self.MONEY_BAG_EMOJI_UNICODE,
                                    last_price=ReaderBase.get_last_price(ticker),
                                    trophy_emoji=self.TROPHY_EMOJI_UNICODE,
                                    tier=readers.Securities(self._mongo_db, ticker).get_latest().get('tierDisplayName'),
                                    alert_msg=alert_msg)

    @staticmethod
    def get_daily_alerters():
        return ['securities']


if __name__ == '__main__':
    Alert().run()
