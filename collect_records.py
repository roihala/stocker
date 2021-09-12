import json
import logging
import os

import arrow
import pymongo

from bson import json_util
from collect import Collect
from common_runnable import CommonRunnable
from google.cloud import pubsub_v1

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from src.collect.records.collectors import FilingsBackend, FilingsPdf

global records_cache
records_cache = {}

NAMES_CSV = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'names.csv'))


class CollectRecords(CommonRunnable):
    TICKER_GUESSER_TOPIC_NAME = 'projects/stocker-300519/topics/records-finder'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.publisher = pubsub_v1.PublisherClient()
        self.diffs_topic_name = Collect.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else Collect.PUBSUB_DIFFS_TOPIC_NAME
        self.guesser_topic_name = self.TICKER_GUESSER_TOPIC_NAME + '-dev' if self._debug else self.TICKER_GUESSER_TOPIC_NAME

        self.scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(15)
        }, jobstores={
            'default': MemoryJobStore(),
            'dynamic': MemoryJobStore()
        })
        self.intervals = {}

    def add_dynamics_jobs(self, record_id, count=FilingsPdf.BATCH_SIZE):
        for index in range(count):
            trigger = OrTrigger([IntervalTrigger(seconds=5), DateTrigger()])
            self.scheduler.add_job(self.collect_dynamic_pdf,
                                   id=str(record_id + index),
                                   args=[record_id + index],
                                   trigger=trigger,
                                   max_instances=1,
                                   misfire_grace_time=480,
                                   jobstore='dynamic')

    def run(self):
        record_id = self.__get_mongo_top_id()
        self.add_dynamics_jobs(record_id)

        trigger = OrTrigger([IntervalTrigger(seconds=5), DateTrigger()])
        self.scheduler.add_job(self.collect_backend,
                               args=[],
                               trigger=trigger,
                               max_instances=1,
                               misfire_grace_time=120)

        self.disable_apscheduler_logs()

        self.scheduler.start()

    def collect_dynamic_pdf(self, record_id):
        collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache,
                          'debug': self._debug, 'record_id': record_id}
        collector = FilingsPdf(**collector_args)
        # using diffs here to preserve uniformity, but it's actually going to be transferred to records guesser
        diffs = collector.collect()

        if diffs:
            if not len(diffs) == 1:
                raise ValueError("FilingsPdf should return exactly one record to guess, got ")

            self.logger.info(f"Detected filing in {record_id}: {diffs}")
            data = json.dumps(diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.guesser_topic_name, data)

            self.__update_jobstore(record_id)

    def collect_backend(self):
        date = arrow.utcnow()

        collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache, 'date': date, 'debug': self._debug}
        collector = FilingsBackend(**collector_args)

        diffs = collector.collect()

        if diffs:
            self.logger.info(f"Detected filings: {diffs}")
            self._publish_diffs(diffs)

    def __create_dynamic_job(self, record_id, index):
        trigger = OrTrigger([IntervalTrigger(seconds=20), DateTrigger()])
        self.scheduler.add_job(self.collect_dynamic_pdf,
                               id=index,
                               args=[record_id],
                               trigger=trigger,
                               max_instances=1,
                               misfire_grace_time=120,
                               jobstore='dynamic')

    def _publish_diffs(self, diffs):
        tickers = set([diff.get('ticker') for diff in diffs])

        # Separating publish by tickers
        for ticker in tickers:
            ticker_diffs = [diff for diff in diffs if diff.get('ticker') == ticker]
            data = json.dumps(ticker_diffs, default=json_util.default).encode('utf-8')
            self.publisher.publish(self.diffs_topic_name, data)

    def __get_mongo_top_id(self):
        return int(
            self._mongo_db.filings_pdf.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get('record_id')) + 1

    def __update_jobstore(self, record_id):
        highest_id = record_id

        # Remove all previous jobs
        for job in self.scheduler.get_jobs('dynamic'):
            highest_id = max(highest_id, int(job.id))

            if record_id < int(job.id):
                continue

            # Multiplying batch size by three for a common-sensed buffer
            elif (record_id - int(job.id)) < FilingsPdf.BATCH_SIZE * 3:
                job.pause()
            else:
                job.remove()

        self.add_dynamics_jobs(highest_id + 1, FilingsPdf.BATCH_SIZE - (highest_id - record_id))


def main():
    try:
        CollectRecords().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
