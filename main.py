#!/usr/bin/env python3
import base64
import json
import logging
import os

import arrow
import pymongo
from bson import json_util
from google.cloud.pubsub_v1 import PublisherClient
from redis import Redis

from common_runnable import CommonRunnable
from src.collector_factory import CollectorsFactory


class CollectFunc(CommonRunnable):
    PUBSUB_DIFFS_TOPIC_NAME = 'projects/stocker-300519/topics/diff-updates'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.publisher = PublisherClient()
        self.topic_name = self.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_DIFFS_TOPIC_NAME

        if os.getenv('REDIS_IP') is not None:
            self.cache = Redis(host=os.getenv('REDIS_IP'))
        else:
            self.cache = {}

        if os.getenv("ENV") == "production":
            self.__is_static_tickers = False
        else:
            self.__is_static_tickers = self.args.static_tickers

    def run(self):
        logging.info("Nothing")

    def ticker_collect(self, collect_info):
        logging.info(f"Started collecting, info: {collect_info}")
        ticker = collect_info['ticker']
        collections = collect_info.get('collections', CollectorsFactory.COLLECTIONS.keys())

        # Using date as a key for matching entries between collections
        date = arrow.utcnow()

        all_diffs = []

        for collection_name in collections:
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


def run(event, context):
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    collect_info = json.loads(pubsub_message)
    CollectFunc().ticker_collect(collect_info)
