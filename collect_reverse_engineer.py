#!/usr/bin/env python3
import concurrent.futures
import json
import logging
import os
import re
from functools import reduce

import arrow
import pymongo
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from bson import json_util
from google.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1 import PublisherClient

from common_runnable import CommonRunnable
from redis import Redis

from src.collect.tickers.collectors import Profile, Securities, Symbols
from src.collector_factory import CollectorsFactory


class Collect(CommonRunnable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #
        # self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_MESSAGES)
        # self.publisher = PublisherClient()
        # self.topic_name = self.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_DIFFS_TOPIC_NAME
        # self._subscription_name = self.PUBSUB_TICKER_SUBSCRIPTION_NAME + '-dev' if self._debug else self.PUBSUB_TICKER_SUBSCRIPTION_NAME
        # self._subscriber = SubscriberClient()

        # if os.getenv('REDIS_IP') is not None:
        #     self.cache = Redis(host=os.getenv('REDIS_IP'))
        # else:
        self.cache = {}

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument('--static_tickers', dest='static_tickers', help='run on static list of tickers',
                            default=False, action='store_true')

        return parser

    def run(self):
        for message in x:
            data = self.parse_message(message)
            #TODO: validate parse
            fixed_data = self.match_schema(data)
            # Collect
            # Test test test

    def collect(self, fixed_data):
        # Pull latest.
        # If match old_value skip
        # If not collect old_value
        # Collect new_value
        pass


    @classmethod
    def parse_message(cls, message):
        data = {}

        # Extract basic fields
        data["stock_name"] = re.search(r"\$\w+", message).group(0)
        data["Tier Code"] = re.search(r"(?:🎀\s*)?(.+)", message).group(1)  # Ribbon is now optional
        data["price"] = re.search(r"💰\s*([0-9.]+)", message).group(1)

        # Extract AS, R, UR, DTC, and Float information
        as_r_ur_dtc_float = re.search(
            r"🏛️ AS: ([\d.]+[BK]?) • R: ([\d.]+[BK]?) • UR: ([\d.]+[BK]?) • DTC: ([\d.]+[BK]?) • Float: ([\d.]+[BK]?)",
            message)
        data["AS"] = as_r_ur_dtc_float.group(1)
        data["R"] = as_r_ur_dtc_float.group(2)
        data["UR"] = as_r_ur_dtc_float.group(3)
        data["DTC"] = as_r_ur_dtc_float.group(4)
        data["float"] = as_r_ur_dtc_float.group(5)

        # Initialize changes dictionary
        data["changes"] = {}

        # Extract each change category (Business Description, Facilities Description, Address)
        changes = re.findall(r"([\w\s]+) Changed:\n❌\s*([^\n]+)\n✅\s*([^\n]+)", message)
        for change in changes:
            field_name = change[0].strip().replace(" ", "_").lower()
            old_value = change[1].strip()
            new_value = change[2].strip()
            data[field_name] = {"old_value": old_value, "new_value": new_value}

        # Handle Removed or Added fields separately
        removed_added = re.findall(r"❌\s*([^\n]+ (Removed|Added): [^\n]+)", message)
        for entry in removed_added:
            description, action = entry[0].rsplit(":", 1)
            field_name = f"{description.strip()}_{action.strip().lower()}"
            data[field_name] = {"new_value": action.strip()}

        # Extract date and time
        date_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Z]{3})", message)
        if date_match:
            data["date"] = date_match.group(0)

        return data

    def match_schema(self, data):
        fixed_data = {}
        for key, value in data.items():
            try:
                fixed_key, collector = self.all_seing_eye_fields_mapping().get(key)
                fixed_data[fixed_key] = (collector, value)
            except Exception as e:
                self.logger.warning("Couldn't map key: {key}".format(key=key))

        return fixed_data

    @classmethod
    def all_seing_eye_fields_mapping(cls):
        #TODO: find all unique fields and translate
        return {
            "Officers": (Profile, 'officers'),
            "Standard Directors": (Profile, 'standardDirectorList'),
            "Business Description ": (Profile, 'businessDesc'),

            "Restricted Shares": (Securities, 'restrictedShares'),
            "R": (Securities, 'restrictedShares'),
            "Authorized Shares": (Securities, 'authorizedShares'),
            "AS": (Securities, 'authorizedShares'),
            "Outstanding Shares": (Securities, 'outstandingShares'),
            "OS": (Securities, 'outstandingShares'),
            "Unrestricted Shares": (Securities, 'unrestrictedShares'),
            "UR": (Securities, 'unrestrictedShares'),
            #TODO: DTC, float
            "Tier Code": (Securities, 'tierCode'),
            "date": (Securities, 'date'),

            "Penny Stock Exempt": (Symbols, 'isPennyStockExempt'),
            "Delinquent SEC Reporting ": (Symbols, 'isDelinquent')
        }

    def ticker_collect(self, ticker):
        # Using date as a key for matching entries between collections
        date = arrow.utcnow()

        all_sons = reduce(lambda x, y: x + y.get_sons(), CollectorsFactory.COLLECTIONS.values(), [])
        all_diffs = []

        for collection_name in CollectorsFactory.COLLECTIONS.keys():
            try:
                if collection_name in all_sons:
                    continue

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


def main():
    try:
        Collect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
