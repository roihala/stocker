#!/usr/bin/env python3
import concurrent.futures
import json
import logging
import os
from functools import reduce

import arrow
import pymongo
from bson import json_util
from google.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1 import PublisherClient

from common_runnable import CommonRunnable
from redis import Redis

from src.collector_factory import CollectorsFactory


class Collect(CommonRunnable):
    PUBSUB_DIFFS_TOPIC_NAME = 'projects/stocker-300519/topics/diff-updates'
    PUBSUB_TICKER_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/collector-tickers-sub'
    MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', 10))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_MESSAGES)
        self.publisher = PublisherClient()
        self.topic_name = self.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_DIFFS_TOPIC_NAME
        self._subscription_name = self.PUBSUB_TICKER_SUBSCRIPTION_NAME + '-dev' if self._debug else self.PUBSUB_TICKER_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()

        if os.getenv('REDIS_IP') is not None:
            self.cache = Redis(host=os.getenv('REDIS_IP'))
        else:
            self.cache = {}

        if os.getenv("ENV") == "production":
            self.__is_static_tickers = False
        else:
            self.__is_static_tickers = self.args.static_tickers

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument('--static_tickers', dest='static_tickers', help='run on static list of tickers',
                            default=False, action='store_true')

        return parser

    def run(self):
        if self.__is_static_tickers:
            for ticker in self.extract_tickers(csv=self.args.csv):
                self.ticker_collect(str.encode(ticker))
            return
        response = self._subscriber.pull(
            request={"subscription": self._subscription_name, "max_messages": self.MAX_MESSAGES})

        for msg in response.received_messages:
            self.queue_listen(msg.message.data, msg.ack_id)

        self.executor.shutdown(wait=True)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_MESSAGES)

        self.run()

    def queue_listen(self, msg: bytes, ack_id):
        self.executor.submit(self.ticker_collect, msg, ack_id)

    def ticker_collect(self, msg: bytes, ack_id=None):
        if not ack_id and not self.args.static_tickers:
            raise ValueError("ticker_collect: ack_id is optional only for static_tickers debug mode")

        # ticker = msg.data.decode('utf-8')
        collect_info = json.loads(msg.decode('utf-8'))
        ticker = collect_info['ticker']
        collections = collect_info.get('collections', CollectorsFactory.COLLECTIONS.keys())

        # Using date as a key for matching entries between collections
        date = arrow.utcnow()

        all_diffs = []

        for collection_name in CollectorsFactory.COLLECTIONS.keys():
            try:
                collector_args = {'mongo_db': self._mongo_db, 'cache': self.cache, 'date': date, 'debug': self._debug,
                                  'ticker': ticker}
                collector = CollectorsFactory.factory(collection_name, **collector_args)
                diffs = collector.collect()

                if diffs:
                    all_diffs += diffs

            except pymongo.errors.OperationFailure as e:
                raise Exception("Mongo connectivity problems, check your credentials. error: {e}".format(e=e))
            except Exception as e:
                self.logger.warning("Couldn't collect {collection} for {ticker}".format(
                    collection=collection_name, ticker=ticker))
                self.logger.exception(e, exc_info=True)

        if all_diffs:
            data = json.dumps(all_diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.topic_name, data)

        # static_tickers debug mode ends here
        if self.__is_static_tickers:
            return

        self._subscriber.acknowledge(
            request={
                "subscription": self._subscription_name,
                "ack_ids": [ack_id],
            }
        )


def main():
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
