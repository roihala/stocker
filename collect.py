#!/usr/bin/env python3
import concurrent.futures
import json
import logging
from functools import reduce
from time import sleep

import arrow
import pymongo
from bson import json_util
from google import pubsub_v1
from google.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage

from common_runnable import CommonRunnable
from runnable import Runnable
from src.factory import Factory

global cache
cache = {}


class Collect(CommonRunnable):
    PUBSUB_DIFFS_TOPIC_NAME = 'projects/stocker-300519/topics/diff-updates'
    PUBSUB_TICKER_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/collector-tickers-sub'
    MAX_MESSAGES = 50

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_MESSAGES)
        self.publisher = PublisherClient()
        self.topic_name = self.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_DIFFS_TOPIC_NAME
        self._subscription_name = self.PUBSUB_TICKER_SUBSCRIPTION_NAME + '-dev' if self._debug else self.PUBSUB_TICKER_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()

    def run(self):

        # flow_control = pubsub_v1.types.FlowControl(max_messages=self.MAX_MESSAGES)
        response = self._subscriber.pull(
            request={"subscription": self._subscription_name, "max_messages": self.MAX_MESSAGES})
        ack_ids = [msg.ack_id for msg in response.received_messages]

        if len(ack_ids) > 0:
            self._subscriber.acknowledge(
                request={
                    "subscription": self._subscription_name,
                    "ack_ids": ack_ids,
                }
            )

            for msg in response.received_messages:
                self.queue_listen(msg.message.data)

        self.executor.shutdown(wait=True)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_MESSAGES)

        self.run()

    def queue_listen(self, msg: bytes):
        self.executor.submit(self.ticker_collect, msg)

    def ticker_collect(self, msg: bytes):

        # ticker = msg.data.decode('utf-8')
        ticker = msg.decode('utf-8')

        # Using date as a key for matching entries between collections
        date = arrow.utcnow()

        all_sons = reduce(lambda x, y: x + y.get_sons(), Factory.get_tickers_collectors(), [])
        all_diffs = []

        for collection_name in Factory.TICKER_COLLECTIONS.keys():
            try:
                if collection_name in all_sons:
                    continue

                collector_args = {'mongo_db': self._mongo_db, 'cache': cache, 'date': date, 'debug': self._debug,
                                  'ticker': ticker}
                collector = Factory.collectors_factory(collection_name, **collector_args)
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


def main():
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
