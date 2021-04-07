import datetime
import pandas
from functools import reduce
from typing import Iterable, List

import pymongo
import telegram
from time import sleep

import arrow
from pymongo.change_stream import CollectionChangeStream

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from runnable import Runnable
from src.factory import Factory
from src.read import readers
from src.read.reader_base import ReaderBase


class Alert(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    MONEY_BAG_EMOJI_UNICODE = u'\U0001F4B0'
    TROPHY_EMOJI_UNICODE = u'\U0001F3C6'

    def __init__(self):
        super().__init__()

        self._scheduler = BackgroundScheduler(executors={
            'default': ThreadPoolExecutor(10),
        }, timezone="Africa/Abidjan")

        self.disable_apscheduler_logs()

        self._scheduler.start()

    def run(self):
        self.listen()

    def listen(self):
        # Alerting historic diffs to prevent losses
        self.alert_diffs(self.__get_yesterday_diffs())

        while True:
            try:
                with self._mongo_db.diffs.watch() as stream:
                    event = stream.next()
                    self.alert_diffs(self.__unpack_stream(stream, event))

            except Exception as e:
                # We know it's unrecoverable:
                self.logger.exception(e)

            sleep(5)

    def alert_diffs(self, diffs: Iterable[dict]):
        tickers = set([diff.get('ticker') for diff in diffs])

        for ticker in tickers:
            self.__alert_by_ticker(ticker, [diff for diff in diffs if diff.get('ticker') == ticker])

    def __alert_by_ticker(self, ticker, diffs: Iterable[dict]):
        # Creating a mapping of object_id to alert in order to update mongo accordingly
        alerts = {}

        for diff in diffs:
            object_id = diff.pop('_id')

            if diff.get('alerted') is True:
                continue

            alert = self.__get_alert(diff)

            if alert:
                alerts[object_id] = alert

        if alerts:
            # Sending or delaying our concatenated alerts
            msg = self.__add_title(ticker, reduce(lambda x, y: x + '\n\n' + y, alerts.values()))
            self.__send_or_delay(msg, alerts)

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

    def __add_title(self, ticker, alert_msg):
        return '{alert_emoji} {ticker} ({money_emoji}{last_price}, {trophy_emoji}{tier}):\n' \
               '{alert_msg}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                    ticker=ticker,
                                    money_emoji=self.MONEY_BAG_EMOJI_UNICODE,
                                    last_price=ReaderBase.get_last_price(ticker),
                                    trophy_emoji=self.TROPHY_EMOJI_UNICODE,
                                    tier=readers.Securities(self._mongo_db, ticker).get_latest().get('tierDisplayName'),
                                    alert_msg=alert_msg)

    def __get_alert(self, diff):
        try:
            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'debug': self._debug}
            alerter = Factory.alerters_factory(diff.get('source'), **alerter_args)

            return alerter.get_alert_msg(diff)

        except Exception as e:
            self.logger.warning("Couldn't create alerter for {diff}".format(diff=diff))
            self.logger.exception(e)

    def __send_or_delay(self, msg, alerts):
        if self._debug:
            self.__send_msg(self._mongo_db.telegram_users.find(), msg)
            return

        self.__send_msg(self._mongo_db.telegram_users.find({'delay': False}), msg)
        self.__send_delayed(self._mongo_db.telegram_users.find({'delay': True}), msg, alerts)

    def __send_delayed(self, delayed_users, msg, alerts):
        trigger = DateTrigger(run_date=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))

        self._scheduler.add_job(self.__send_msg_with_ack,
                                args=[delayed_users, msg, alerts],
                                trigger=trigger)

    def __send_msg_with_ack(self, users_group, msg, alerts):
        is_success = self.__send_msg(users_group, msg)

        if is_success:
            # Updating mongo that the diff has been alerted
            [self._mongo_db.diffs.update_one({'_id': object_id}, {'$set': {"alerted": True}}) for object_id in
             alerts.keys()]

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

    @staticmethod
    def get_daily_alerters():
        return ['securities']


if __name__ == '__main__':
    Alert().run()
