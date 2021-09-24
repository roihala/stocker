import arrow
import json
import logging
import time
import os
import random
import pandas
import telegram

from bson import ObjectId
from aiogram.utils import exceptions
from retry import retry

from common_runnable import CommonRunnable
from src.alerters_factory import AlertersFactory
from src.alert.records.filings_alerter import FilingsAlerter

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

    def run(self):
        streaming_pull_future = self._subscriber.subscribe(self._subscription_name, self.alert_batch)
        with self._subscriber:
            streaming_pull_future.result()

    def alert_batch(self, batch: PubSubMessage):
        diffs = [{k: '' if v == 'None' else v for k, v in diff.items()} for diff in json.loads(batch.data)]
        self.logger.info('detected batch: {diffs}'.format(diffs=diffs))

        [diff.update({'_id': ObjectId()}) for diff in diffs if '_id' not in diff]

        try:
            ticker = self.__extract_ticker(diffs)

            if not ticker:
                self.logger.warning(f"Couldn't detect ticker in {diffs}")
                batch.nack()
                return

            if not self.is_relevant(ticker):
                batch.ack()
                return

            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bots[STOCKER_ALERTS_BOT],
                            'ticker': ticker, 'debug': self._debug}

            alerters = [alerter for alerter in self.get_alerters(diffs, alerter_args) if alerter.generate_messages()]

            if not any(alerters):
                batch.ack()
                return

            # Filtering by price as late as possible
            price = ReaderBase.get_last_price(ticker)

            if price > 0.05:
                batch.ack()
                return

            processed_diffs = [diff for alerter in alerters for diff in alerter.processed_diffs]
            self._mongo_db.diffs.insert_many(processed_diffs)

            try:
                data = json.dumps(processed_diffs, default=json_util.default).encode('utf-8')
                if not self._debug:
                    self.publisher.publish(self.PUBSUB_RELEVANT_TOPIC_NAME, data)
            except Exception as e:
                self.logger.exception(e)
                self.logger.error("Failed to publish relevant diffs")

            alert_body = '\n\n'.join([alerter.get_text() for alerter in alerters if alerter.get_text()])

            # Alerting with current date to avoid difference between collect to alert
            text = self.build_text(alert_body, ticker, self._mongo_db, date=arrow.utcnow(), price=price)

            if any([isinstance(alerter, FilingsAlerter) for alerter in alerters]):
                try:
                    self.init_telegram('1840118134:AAEo0DdrZj5ZHEJ95Y9o1FJxDsfIcm5K7xk'). \
                        send_message(chat_id=1151317792,
                                     text=text,
                                     parse_mode=telegram.ParseMode.MARKDOWN)
                except Exception as e:
                    self.logger.warning("Couldn't alert filings")
                    self.logger.exception(e)
                finally:
                    batch.ack()
                    return

            vips = [1151317792, 564105605, 331478596, 887214621, 975984160, 406000980, 262828800]

            users = [_ for _ in self.__get_users() if _.get('chat_id') not in vips + [1865808006]]

            users = [self._mongo_db.telegram_users.find_one({'chat_id': vip}) for vip in vips] + users + \
                    [self._mongo_db.telegram_users.find_one({'chat_id': 1865808006})]

            self.trigger_send(text, users)

            batch.ack()
        except Exception as e:
            self.logger.warning("Couldn't alert diffs: {diffs}".format(diffs=diffs))
            self.logger.exception(e)
            batch.nack()

    def trigger_send(self, text, users):
        try:
            for user in [_ for _ in users if _]:
                self.__send_msg(user, text)
        except Exception as e:
            self.logger.warning("Couldn't __send_msg")
            self.logger.exception(e)

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
        return ticker

    def is_relevant(self, ticker):
        is_relevant_tier, is_ce = None, None

        try:
            sec = readers.Securities(self._mongo_db, ticker).get_latest()

            is_ce = bool(sec.get('isCaveatEmptor'))

            tier_code = sec.get('tierCode')
            tier_hierarchy = Securities.get_hierarchy()['tierCode']
            is_relevant_tier = tier_hierarchy.index(tier_code) < tier_hierarchy.index('QB')

        except (ValueError, AttributeError):
            is_relevant_tier = True if is_relevant_tier is None else is_relevant_tier
            # ce (Caveat Emptor) is bad thing!
            is_ce = False if is_ce is None else is_ce

        # Will we alert this ticker?
        if not (len(ticker) == 5 and ticker[-1] == 'F') \
                and is_relevant_tier and not is_ce:
            return True
        return False

    def __get_users(self):
        registered_users = [user for user in self._mongo_db.telegram_users.find() if
                            user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]]
        random.shuffle(registered_users)
        return registered_users

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

    @retry(tries=3)
    def __send_msg(self, user, text):
        try:
            self._telegram_bots[
                user.get("bot", STOCKER_ALERTS_BOT) if not self._debug else 'stocker_tests_bot'].send_message(
                chat_id=user.get("chat_id"),
                text=text,
                parse_mode=telegram.ParseMode.MARKDOWN)

        except telegram.error.TimedOut as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}: "
                                f"Timed out")
            time.sleep(10)
            return self.__send_msg(user, text)  # Recursive call

        except exceptions.RetryAfter as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}: "
                                f"Flood limit is exceeded. Sleep {e.timeout} seconds.")
            time.sleep(e.timeout)
            return self.__send_msg(user, text)  # Recursive call
        except telegram.error.Unauthorized:
            self._mongo_db.telegram_users.update_one({'chat_id': user.get('chat_id')},
                                                     {'activation': {'$set': ActivationCodes.BLOCKED}})
        except Exception as e:
            self.logger.warning(f"Couldn't send msg to {user.get('user_name')} of {user.get('chat_id')}")
            self.logger.exception(e)
        finally:
            return True

    @classmethod
    def build_text(cls, alert_body, ticker, mongo_db, date=None, price=None, is_alert=True):
        return '{title}\n' \
               '{alert_body}\n' \
               '{date}'.format(title=cls.generate_title(ticker, mongo_db, price, is_alert),
                               alert_body=alert_body,
                               date=ReaderBase.format_stocker_date(date) if date else '')

    @classmethod
    def generate_title(cls, ticker, mongo_db, price=None, is_alert=True):
        try:
            tier = readers.Securities(mongo_db, ticker).get_latest().get('tierDisplayName')
        except AttributeError:
            logging.warning(f"Couldn't get tier of {ticker}")
            tier = ''

        # Add title only for alerts
        if is_alert and pandas.DataFrame(mongo_db.diffs.find({'ticker': ticker})).empty:
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
