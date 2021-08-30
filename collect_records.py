import json
import logging
import os
import time
import arrow
import pandas as pd
import pymongo
from apscheduler.jobstores.memory import MemoryJobStore

from bson import json_util

from collect import Collect
from common_runnable import CommonRunnable
from google.cloud import pubsub_v1

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.collect.records.collectors import FilingsBackend, FilingsPdf
from src.read import readers

global records_cache
records_cache = {}

NAMES_CSV = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'names.csv'))


class CollectRecords(CommonRunnable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_name = Collect.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else Collect.PUBSUB_DIFFS_TOPIC_NAME
        self.tickers_mapping = self.__get_tickers_mapping()
        self.scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(15)
        }, jobstores={
            'default': MemoryJobStore(),
            'dynamic': MemoryJobStore()
        })

    def run(self):
        if self._debug:
            record_id = int(
                self._mongo_db.filings_pdf.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get(
                    'record_id')) + 1

            self.collect_backend()
            for i in range(FilingsPdf.BATCH_SIZE):
                self.collect_pdf(record_id + i)

        trigger = OrTrigger([IntervalTrigger(seconds=20), DateTrigger()])

        record_id = int(
            self._mongo_db.filings_pdf.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get('record_id')) + 1

        for index in range(FilingsPdf.BATCH_SIZE):
            self.scheduler.add_job(self.collect_pdf,
                                   args=[record_id + index],
                                   trigger=trigger,
                                   max_instances=1,
                                   misfire_grace_time=120,
                                   jobstore='dynamic')

        trigger = OrTrigger([IntervalTrigger(seconds=10), DateTrigger()])
        self.scheduler.add_job(self.collect_backend,
                               args=[],
                               trigger=trigger,
                               max_instances=1,
                               misfire_grace_time=120)

        self.disable_apscheduler_logs()

        self.scheduler.start()

    def collect_pdf(self, record_id):
        date = arrow.utcnow()

        collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache, 'date': date, 'debug': self._debug,
                          'record_id': record_id}
        collector = FilingsPdf(**collector_args)

        diffs = collector.collect()

        if diffs:
            self._publish_diffs(diffs)

            # Re-running jobs according to the new record_id
            [job.modify(**{'args': [job.args[0] + FilingsPdf.BATCH_SIZE]})
             for job in self.scheduler.get_jobs('dynamic') if job.args[0] <= record_id]

    def collect_backend(self):
        date = arrow.utcnow()

        collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache, 'date': date, 'debug': self._debug}
        collector = FilingsBackend(**collector_args)

        diffs = collector.collect()

        if diffs:
            self._publish_diffs(diffs)

    def _publish_diffs(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])

        if not tickers:
            self.logger.info(f'diffs: {diffs}')
            data = json.dumps(diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.topic_name, data)
            return

        # Separating publish by tickers
        for ticker in tickers:
            ticker_diffs = [diff for diff in diffs if diff.get('ticker') == ticker]
            self.logger.info(f'diffs: {ticker_diffs}')
            data = json.dumps(ticker_diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.topic_name, data)

    def __get_tickers_mapping(self):
        if self._debug:
            return pd.read_csv(NAMES_CSV, header=None, index_col=0, squeeze=True).to_dict()

        tickers = pd.DataFrame({'Ticker': self._tickers_list})
        tickers['CompanyName'] = tickers['Ticker'].apply(lambda row: self.__get_company_name(row))
        return tickers.set_index('Ticker').to_dict()['CompanyName']

    def __get_company_name(self, ticker):
        try:
            return readers.Profile(self._mongo_db, ticker).get_latest()['name']
        except Exception:
            return None


def main():
    try:
        CollectRecords().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
