import argparse
import os
from abc import ABC

from runnable import Runnable


class CommonRunnable(Runnable, ABC):
    def __init__(self, args=None):
        super().__init__(args)

        if os.getenv("ENV") == "production":
            self._mongo_db = self.init_mongo(os.environ['MONGO_URI'])
            self._telegram_bot = self.init_telegram(os.environ['TELEGRAM_TOKEN'])
        else:
            self._mongo_db = self.init_mongo(self.args.uri)
            self._telegram_bot = self.init_telegram(self.args.token)

    def create_parser(self):
        parser = super().create_parser()

        parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
        parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)
        parser.add_argument('--csv', dest='csv', help='path to csv tickers file')

        return parser
