import asyncio
import itertools
from typing import List

import arrow
import json
import logging
import os
import random
from copy import deepcopy
import pandas
import telegram

from bson import ObjectId
from aiogram import Bot, Dispatcher, types
from aiogram.utils import exceptions, executor

from common_runnable import CommonRunnable
from src.alert.alerter_base import AlerterBase
from src.alerters_factory import AlertersFactory

from src.read import readers
from src.read.reader_base import ReaderBase
from src.alert.tickers.alerters import Securities, Otciq

from google.cloud.pubsub import SubscriberClient
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from bson import json_util

from src.telegram_bot.resources.activation_kaki import ActivationCodes

LOGO_PATH = os.path.join(os.path.dirname(__file__), 'images', 'ProfileS.png')


class Alert(CommonRunnable):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    DOLLAR_EMOJI_UNICODE = u'\U0001F4B2'
    TROPHY_EMOJI_UNICODE = u'\U0001F3C6'
    BANG_EMOJI_UNICODE = u'\U0001F4A5'

    PUBSUB_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/diff-updates-sub'
    PUBSUB_RELEVANT_TOPIC_NAME = 'projects/stocker-300519/topics/diffs-relevant'

    def __init__(self):
        super().__init__()
        self.publisher = pubsub_v1.PublisherClient()

        self._subscription_name = self.PUBSUB_SUBSCRIPTION_NAME + '-dev' if self._debug else self.PUBSUB_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()
        self._aiogram_bot = Bot(token=self._telegram_token)
        self._aiogram_bot_dp = Dispatcher(self._aiogram_bot)

    def run(self):
        streaming_pull_future = self._subscriber.subscribe(self._subscription_name, self.alert_batch)
        with self._subscriber:
            streaming_pull_future.result()

    def alert_batch(self, batch: PubSubMessage):
        diffs = json.loads(batch.data)
        self.logger.info('detected batch: {diffs}'.format(diffs=diffs))

        [diff.update({'_id': ObjectId()}) for diff in diffs if '_id' not in diff]

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
                            'ticker': ticker, 'last_price': price, 'debug': self._debug}

            alerters = [alerter for alerter in self.get_alerters(diffs, alerter_args) if alerter.generate_messages()]

            if any(alerters):
                processed_diffs = [diff for alerter in alerters for diff in alerter.processed_diffs]
                self._mongo_db.diffs.insert_many(processed_diffs)

                try:
                    data = json.dumps(processed_diffs, default=json_util.default).encode('utf-8')
                    if not self._debug:
                        self.publisher.publish(self.PUBSUB_RELEVANT_TOPIC_NAME, data)
                except Exception as e:
                    self.logger.exception(e)
                    self.logger.error("Failed to publish relevant diffs")

                # Otciq patch
                try:

                    otciq_alerter = [alerter for alerter in alerters if isinstance(alerter, Otciq)]

                    if otciq_alerter:
                        text = self.build_text(otciq_alerter[0].get_text(), ticker, self._mongo_db, date=arrow.utcnow(),
                                               price=price)

                        [self._telegram_bot.send_message(chat_id=_,
                                                         text=text,
                                                         parse_mode=telegram.ParseMode.MARKDOWN) for _ in
                         [1151317792, 406000980, 564105605]]

                except Exception as e:
                    self.logger.warning(f"Couldn't alert otciq for {ticker}")
                    self.logger.error(e)

                alerters = [alerter for alerter in alerters if not isinstance(alerter, Otciq)]

                if not alerters:
                    batch.ack()
                    return

                alert_body = '\n\n'.join([alerter.get_text() for alerter in alerters if
                                          alerter.get_text() and not isinstance(alerter, Otciq)])

                # Alerting with current date to avoid difference between collect to alert
                text = self.build_text(alert_body, ticker, self._mongo_db, date=arrow.utcnow(), price=price)

                users = [self._mongo_db.telegram_users.find_one({'chat_id': 1151317792})] + self.__get_users() + \
                        [self._mongo_db.telegram_users.find_one({'chat_id': 1865808006})]

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                executor.start(self._aiogram_bot_dp, self.__send_no_delay(text, users))

            batch.ack()
        except Exception as e:
            self.logger.warning("Couldn't alert diffs: {diffs}".format(diffs=diffs))
            self.logger.exception(e)
            batch.nack()

    @staticmethod
    def get_alerters(diffs, alerter_args) -> list:
        alerters = []

        for source in set([diff.get('source') for diff in diffs if diff.get('source')]):
            try:
                alerter_args.update({'diffs': [diff for diff in diffs if diff['source'] == source]})
                alerters.append(AlertersFactory.factory(source, **alerter_args))
            except Exception as e:
                logger = logging.getLogger(AlertersFactory.get_alerter(source).__class__.__name__)
                logger.warning(f"Couldn't generate {source} alerter for {diffs}")
                logger.exception(e)

        return alerters

    def __extract_ticker(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])

        if not len(tickers) == 1:
            raise ValueError("Batch consists more than one ticker: {tickers}".format(tickers=tickers))

        ticker = tickers.pop()
        return ticker, ReaderBase.get_last_price(ticker)

    def is_relevant(self, ticker, price):
        try:
            sec = readers.Securities(self._mongo_db, ticker).get_latest()
            tier_code = sec.get('tierCode')

            tier_hierarchy = Securities.get_hierarchy()['tierCode']
            relevant_tier = tier_hierarchy.index(tier_code) < tier_hierarchy.index('QB')

        except (ValueError, AttributeError):
            relevant_tier = True

        # Will we alert this ticker?
        if price < 0.05 \
                and not (len(ticker) == 5 and ticker[-1] == 'F') \
                and relevant_tier:
            return True
        return False

    def __get_users(self):
        registered_users = [user for user in self._mongo_db.telegram_users.find() if
                            user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE] and
                            user.get('chat_id') not in [1865808006, 1151317792]]
        random.shuffle(registered_users)
        return registered_users

    async def __send_no_delay(self, text, users):
        try:
            for user in [_ for _ in users if _]:
                await self.__send_msg(user, text)
                await asyncio.sleep(.0333333)
        except Exception as e:
            self.logger.warning("Couldn't send_no_delay")
            self.logger.exception(e)

    async def __send_msg(self, user, text):
        try:
            self._telegram_bot.send_message(chat_id=user.get("chat_id"),
                                            text=text,
                                            parse_mode=telegram.ParseMode.MARKDOWN)

        except telegram.error.TimedOut as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}: "
                                f"Timed out")
            await asyncio.sleep(10)
            return await self.__send_msg(user, text)  # Recursive call

        except exceptions.RetryAfter as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}: "
                                f"Flood limit is exceeded. Sleep {e.timeout} seconds.")
            await asyncio.sleep(e.timeout)
            return await self.__send_msg(user, text)  # Recursive call
        except Exception as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}")
            self.logger.exception(e)
        else:
            return True

        return False

    @classmethod
    def build_text(cls, alert_body, ticker, mongo_db, date=None, price=None):
        return '{title}\n' \
               '{alert_body}\n' \
               '{date}'.format(title=cls.generate_title(ticker, mongo_db, price),
                               alert_body=alert_body,
                               date=ReaderBase.format_stocker_date(date) if date else '')

    @classmethod
    def generate_title(cls, ticker, mongo_db, price=None):
        try:
            tier = readers.Securities(mongo_db, ticker).get_latest().get('tierDisplayName')
        except AttributeError:
            logging.warning(f"Couldn't get tier of {ticker}")
            tier = ''

        # Add title
        if pandas.DataFrame(mongo_db.diffs.find({'ticker': ticker})).empty:
            additions = f'{cls.BANG_EMOJI_UNICODE} First ever alert for this ticker!'
        else:
            additions = ''

        return '{alert_emoji} *{ticker}*\n{money_emoji}{last_price}\n{trophy_emoji}{tier}\n{additions}'.format(
            alert_emoji=Alert.ALERT_EMOJI_UNICODE,
            ticker=ticker,
            money_emoji=Alert.DOLLAR_EMOJI_UNICODE,
            last_price=price if price else ReaderBase.get_last_price(ticker),
            trophy_emoji=Alert.TROPHY_EMOJI_UNICODE,
            tier=tier,
            additions=additions + '\n' if additions else '')


if __name__ == '__main__':
    Alert().run()
