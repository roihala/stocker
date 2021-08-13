import asyncio

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
from src.alerters_factory import AlertersFactory

from src.read import readers
from src.read.reader_base import ReaderBase
from src.alert.tickers.alerters import Securities

from google.cloud.pubsub import SubscriberClient
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from bson import json_util

from src.telegram_bot.resources.activation_kaki import ActivationCodes

LOGO_PATH = os.path.join(os.path.dirname(__file__), 'images', 'ProfileS.png')
STOCKER_ALERTS_BOT = "stocker_alerts_bot"

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

        self._telegram_bot = None
        self._telegram_bots = self.init_telegram_bots(self.__get_bots())

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

            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bots[STOCKER_ALERTS_BOT],
                            'ticker': ticker, 'debug': self._debug}

            msg = self.get_msg(diffs, alerter_args)

            if msg:
                processed_diffs = [diff for diff in raw_diffs if diff.get('_id') in msg.keys()]
                self._mongo_db.diffs.insert_many(processed_diffs)

                try:
                    data = json.dumps(processed_diffs, default=json_util.default).encode('utf-8')
                    if not self._debug:
                        self.publisher.publish(self.PUBSUB_RELEVANT_TOPIC_NAME, data)
                except Exception as e:
                    self.logger.exception(e)
                    self.logger.error("Failed to publish relevant diffs")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                executor.start(self._aiogram_bot_dp, self.__send_no_delay(msg, ticker, price))

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
                alerter = AlertersFactory.factory(source, **alerter_args)
                messages_dict = alerter.generate_messages([diff for diff in diffs if diff.get('source') == source])
                messages.update(messages_dict)
            except Exception as e:
                logger = logging.getLogger(AlertersFactory.get_alerter(source).__class__.__name__)
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

    def __get_users(self):
        registered_users = [user for user in self._mongo_db.telegram_users.find() if
                            user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE] and
                            user.get('chat_id') not in [1865808006, 1151317792]]
        random.shuffle(registered_users)
        return registered_users

    # async def __send_no_delay(self):
    async def __send_no_delay(self, msg: dict, ticker, price):
        try:
            # Alerting with current date to avoid difference between collect to alert
            text = self.__extract_text(msg, ticker, price, date=arrow.utcnow())
            users = [self._mongo_db.telegram_users.find_one({'chat_id': 1151317792})] + self.__get_users() + \
                    [self._mongo_db.telegram_users.find_one({'chat_id': 1865808006})]

            for user in users:
                await self.__send_msg(user, text)
                await asyncio.sleep(.0333333)
        except Exception as e:
            self.logger.warning("Couldn't send_no_delay")
            self.logger.exception(e)

    async def __send_msg(self, user, text):
        try:
            self._telegram_bots[user.get("bot") if user.get("bot") else STOCKER_ALERTS_BOT].send_message(
                                            chat_id=user.get("chat_id"),
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

    def __extract_text(self, msg: dict, ticker, price, date=None):
        alert_text = '\n\n'.join([value['message'] for value in msg.values() if value.get('message')])

        # Add title
        if pandas.DataFrame(self._mongo_db.diffs.find({'ticker': ticker})).empty:
            alert_text = f'{self.BANG_EMOJI_UNICODE} First ever alert for this ticker\n{alert_text}'

        return '{title}\n' \
               '{alert_msg}\n' \
               '{date}'.format(title=self.generate_title(ticker, self._mongo_db, price),
                               alert_msg=alert_text,
                               date=ReaderBase.format_stocker_date(date if date else
                                                                   sorted([value['date'] for value in msg.values() if
                                                                           'date' in value])[-1]))

    def __get_bots(self):
        return pandas.DataFrame(self._mongo_db.bots.find())

    @staticmethod
    def init_telegram_bots(bots: pandas.DataFrame) -> dict:
        telegram_bots = {}

        for index, bot in bots.iterrows():
            try:
                telegram_bots[bot['name']] = telegram.Bot(bot['token'])
            except telegram.error.Unauthorized:
                raise ValueError("Couldn't connect to telegram, check your credentials")

        return telegram_bots

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
