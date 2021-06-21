import datetime
import json
import logging
import os
from copy import deepcopy
from functools import reduce
from typing import Dict, Iterable

import pandas
import telegram

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from bson import ObjectId
from telegram import InputMediaDocument

from runnable import Runnable
from src.collect.records.dynamic_records_collector import DynamicRecordsCollector
from src.collect.records.collectors.filings_pdf import FILINGS_PDF_URL

from src.factory import Factory
from src.read import readers
from src.read.reader_base import ReaderBase
from src.alert.tickers.alerters import Securities

from google.cloud.pubsub import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage

LOGO_PATH = os.path.join(os.path.dirname(__file__), 'img/profileS.png')


class Alert(Runnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    DOLLAR_EMOJI_UNICODE = u'\U0001F4B2'
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

        [diff.update({'_id': ObjectId()}) for diff in diffs if '_id' not in diff]

        raw_diffs = deepcopy(diffs)

        try:
            ticker, price = self.__extract_ticker(diffs)

            if not ticker:
                self.logger.warning(f"Couldn't detect ticker in {diffs}")
                batch.nack()
                return

            if not self.is_relevant(ticker, price):
                batch.ack()
                return

            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                            'ticker': ticker, 'debug': self._debug}

            msg = self.get_msg(diffs, alerter_args)

            if msg:
                self._mongo_db.diffs.insert_many([diff for diff in raw_diffs if diff.get('_id') in msg.keys()])

                delay = False if any([diff.get('source') in ['filings', 'filings_pdf'] for diff in raw_diffs]) else True
                self.__send_or_delay(msg, ticker, price, is_delay=delay)

            batch.ack()
        except Exception as e:
            self.logger.warning("Couldn't alert diffs: {diffs}".format(diffs=diffs))
            self.logger.exception(e)
            batch.nack()

    @staticmethod
    def get_msg(diffs, alerter_args) -> dict:
        """
        returns a dict of the form:
        {
        ObjectId('60cc6a43096cb97b35b1ee3c'): {'message': 'kaki'},
        ObjectId('60cc6a43096cb97b35b1ee3c'): {'message': 'pipi', 'file': 'path/to/file'}
        }
        """
        messages = {}

        for source in set([diff.get('source') for diff in diffs if diff.get('source')]):
            try:
                alerter = Factory.alerters_factory(source, **alerter_args)
                messages_dict = alerter.generate_messages([diff for diff in diffs if diff.get('source') == source])
                messages.update(messages_dict)
            except Exception as e:
                logger = logging.getLogger(Factory.get_alerter(source).__class__.__name__)
                logger.warning(f"Couldn't generate msg {diffs}: {source}")
                logger.exception(e)

        return messages

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

    def __send_or_delay(self, msg: dict, ticker, price, is_delay=True):
        if self._debug:
            self.__send_msg(self.__get_users(ignore_delay=True), msg, ticker, price)
            return

        if is_delay:
            self.__send_msg(self.__get_users(delay=False), msg, ticker, price)
            self.__send_delayed(self.__get_users(), msg, ticker, price)
        else:
            self.__send_msg(self.__get_users(ignore_delay=True), msg, ticker, price)

    def __get_users(self, delay=True, ignore_delay=False):
        users = self._mongo_db.telegram_users.find({'delay': delay}) if not ignore_delay \
            else self._mongo_db.telegram_users.find()

        return [user for user in users if ('activation' not in user) or (user.get('activation') in ['trial', 'active'])]

    def __send_delayed(self, delayed_users: Iterable[Dict], msg: dict, ticker, price):
        trigger = DateTrigger(run_date=datetime.datetime.utcnow() + datetime.timedelta(seconds=20))

        self._scheduler.add_job(self.__send_msg,
                                args=[delayed_users, msg, ticker, price],
                                trigger=trigger)

    def __send_msg(self, users_group: Iterable[Dict], msg: dict, ticker, price):
        text = self.__extract_text(msg, ticker, price)
        record_ids = reduce(lambda _, value: _ + value['pdf_record_ids'] if 'pdf_record_ids' in value else _,
                            msg.values(), [])
        # TODO: Use the existing files with webhooks

        for user in users_group:
            files = [DynamicRecordsCollector.get_pdf(record_id, base_url=FILINGS_PDF_URL) for record_id in record_ids]

            media = [InputMediaDocument(media=open(file, 'rb'),
                                        filename=f"{ticker}.pdf",
                                        thumb=open(LOGO_PATH, 'rb')) for file in files]

            try:
                if record_ids:
                    media[-1].caption = text
                    media[-1].parse_mode = telegram.ParseMode.MARKDOWN

                    if len(media) == 0:
                        raise ValueError("Media should contain at least one pdf location")
                    elif len(media) == 1:
                        first_media = media[0]
                        self._telegram_bot.send_document(chat_id=user.get("chat_id"),
                                                         document=first_media.media,
                                                         filename=f"{ticker}.pdf",
                                                         thumb=first_media.thumb,
                                                         parse_mode=first_media.parse_mode,
                                                         caption=first_media.caption)
                    elif len(media) > 1:
                        self._telegram_bot.send_media_group(chat_id=user.get("chat_id"),
                                                            media=media)
                else:
                    self._telegram_bot.send_message(chat_id=user.get("chat_id"),
                                                    text=text,
                                                    parse_mode=telegram.ParseMode.MARKDOWN)

            except Exception as e:
                self.logger.warning(
                    "Couldn't alert {message} to {user} at {chat_id}:".format(user=user.get("user_name"),
                                                                              chat_id=user.get("chat_id"),
                                                                              message=text))
                self.logger.exception(e)

    def __extract_text(self, msg: dict, ticker, price):
        alert_text = '\n\n'.join([value['message'] for value in msg.values() if value.get('message')])

        # Add title
        if pandas.DataFrame(self._mongo_db.diffs.find({'ticker': ticker})).empty:
            alert_text = f'{self.BANG_EMOJI_UNICODE} First ever alert for this ticker\n{alert_text}'

        return '{title}\n' \
               '{alert_msg}\n' \
               '{date}'.format(title=self.generate_title(ticker, self._mongo_db, price),
                               alert_msg=alert_text,
                               date=sorted([value['date'] for value in msg.values()])[-1])

    @staticmethod
    def generate_title(ticker, mongo_db, price=None):
        try:
            tier = readers.Securities(mongo_db, ticker).get_latest().get('tierDisplayName')
        except AttributeError:
            logging.warning(f"Couldn't get tier of {ticker}")
            tier = ''

        return '{alert_emoji} *{ticker}*\n{money_emoji}{last_price}\n{trophy_emoji}{tier}\n'.format(
            alert_emoji=Alert.ALERT_EMOJI_UNICODE,
            ticker=ticker,
            money_emoji=Alert.DOLLAR_EMOJI_UNICODE,
            last_price=price if price else ReaderBase.get_last_price(ticker),
            trophy_emoji=Alert.TROPHY_EMOJI_UNICODE,
            tier=tier)


if __name__ == '__main__':
    Alert().run()
