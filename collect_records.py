import json
import logging

import arrow

from bson import json_util
from collect import Collect
from runnable import Runnable
from google.cloud import pubsub_v1

from src.factory import Factory

global records_cache
records_cache = {}


class RecordsCollect(Runnable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_name = Collect.PUBSUB_TOPIC_NAME + '-dev' if self._debug else Collect.PUBSUB_TOPIC_NAME

    def run(self):
        if self._debug:
            while True:
                self.collect_records()

    def collect_records(self):
        date = arrow.utcnow()

        for collection_name in Factory.RECORDS_COLLECTIONS.keys():
            collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache, 'date': date, 'debug': self._debug,
                              'write': self._write}
            collector = Factory.collectors_factory(collection_name, **collector_args)
            diffs = collector.collect()
            print('diffs', diffs)
            if diffs:
                self._publish_diffs(diffs)

    def _publish_diffs(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])

        # Separating publish by tickers
        for ticker in tickers:
            ticker_diffs = [diff for diff in diffs if diff.get('ticker') == ticker]
            self._mongo_db.diffs.insert_many(ticker_diffs)
            data = json.dumps(ticker_diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.topic_name, data)


def main():
    try:
        RecordsCollect().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
