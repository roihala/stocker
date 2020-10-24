#!/usr/bin/env python3
import argparse
import logging
import os

import pymongo

import pandas
import telegram
from pymongo import MongoClient

from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'alert.log')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), 'tickers.csv')


class Alert(object):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'

    def __init__(self, args):
        logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

        self._mongo_db = self.init_mongo(args.uri)
        self._tickers_list = self.extract_tickers(args)
        self._telegram_bot = self.init_telegram(args.token)

    @staticmethod
    def init_mongo(mongo_uri):
        try:
            # Using selection timeout in order to check connectivity
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1)

            # Forcing a connection to mongo
            mongo_client.server_info()

            return mongo_client.stocker

        except pymongo.errors.ServerSelectionTimeoutError:
            raise ValueError("Couldn't connect to MongoDB, check your credentials")

    @staticmethod
    def extract_tickers(args):
        try:
            if args.csv:
                file_path = args.csv
            else:
                file_path = DEFAULT_CSV_PATH

            df = pandas.read_csv(file_path)
            return df.Symbol.apply(lambda ticker: ticker.upper())
        except Exception:
            raise ValueError('Invalid csv file - validate the path and that the tickers are under a column named symbol')

    @staticmethod
    def init_telegram(token):
        try:
            return telegram.Bot(token)
        except telegram.error.Unauthorized:
            raise ValueError("Couldn't connect to telegram, check your credentials")

    def alert(self):
        for ticker in self._tickers_list:
            try:
                with TickerHistory(ticker, self._mongo_db) as ticker_history:
                    logging.info('running on {ticker}'.format(ticker=ticker))

                    changes = ticker_history.get_changes()
                    logging.info('changes: {changes}'.format(changes=changes))

                    if changes:
                        # Insert the new diffs to mongo
                        [self._mongo_db.diffs.insert_one(change) for change in changes]

                        # Alert every registered user
                        [self.__telegram_alert(change) for change in changes]

            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))
            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                logging.warning('Exception on {ticker}: {e}'.format(ticker=ticker, e=e))

    def __telegram_alert(self, change):
        # User-friendly message
        msg = self.ALERT_EMOJI_UNICODE + ' Detected change on {ticker}:\n*{key}* has changed from {old} to {new}'.format(
            ticker=change.get('ticker'), key=change.get('changed_key'), old=change.get('old'), new=change.get('new'))

        for user in self._mongo_db.telegram_users.find():
            try:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg, parse_mode=telegram.ParseMode.MARKDOWN)

            except telegram.error.BadRequest:
                logging.warning("Can't alert to {user} - invalid chat id: {chat_id}".format(
                    user=user.get('user_name'), chat_id=user.get('chat_id')))


def main():
    Alert(get_args()).alert()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', dest='csv', help='path to csv tickers file')
    parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
    parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
    parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)

    return parser.parse_args()


if __name__ == '__main__':
    main()
