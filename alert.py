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


class Alert(Runnable):
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
        # Creating a mapping of object_id to alert in order to update mongo accordingly
        alerts = {}
        imgs = []

        for diff in diffs:
            object_id = diff.pop('_id')

            if diff.get('alerted') is True:
                continue

            alert, img = self.__get_alert(diff)

            if alert:
                alerts[object_id] = alert

            if img:
                imgs.append(img)

        if alerts:
            # Sending or delaying our concatenated alerts
            self.__send_or_delay(reduce(lambda x, y: x + '\n' + y, alerts.values()), alerts)

        for img in imgs:
            self.__img_send_or_delay(img)

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

    def __get_alert(self, diff):
        try:
            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'debug': self._debug}
            alerter = Factory.alerters_factory(diff.get('source'), **alerter_args)

            return (alerter.get_alert_msg(diff), alerter.get_alert_diff_img(diff))

        except Exception as e:
            self.logger.warning("Couldn't create alerter for {diff}".format(diff=diff))
            self.logger.exception(e)

    def __img_send_or_delay(self, img):
        if self._debug:
            self.__img_send(self._mongo_db.telegram_users.find(), img)

        self.__img_send(self._mongo_db.telegram_users.find({'delay': False}), img)
        self.__img_send_delayed(self._mongo_db.telegram_users.find({'delay': True}), img)

    def __img_send_delayed(self, delayed_users, img):
        trigger = DateTrigger(run_date=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))

        self._scheduler.add_job(self.__img_send,
                                args=[delayed_users, img],
                                trigger=trigger)

    def __img_send(self, users_group, img):
        is_sent_successfuly = False
        for user in users_group:
            try:
                img.seek(0)
                self._telegram_bot.send_photo(chat_id=user.get("chat_id"), photo=img)
                is_sent_successfuly = True

            except Exception as e:
                self.logger.warning("Couldn't send image to {user} at {chat_id}:".format(user=user.get("user_name"),
                                                                                           chat_id=user.get("chat_id")))
                self.logger.exception(e)

        return is_sent_successfuly

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
                self.logger.warning("Couldn't send message to {user} at {chat_id}:".format(user=user.get("user_name"), chat_id=user.get("chat_id")))
                self.logger.exception(e)

        return is_sent_successfuly

    @staticmethod
    def get_daily_alerters():
        return ['securities']


if __name__ == '__main__':
    Alert().run()
