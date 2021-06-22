# !/usr/bin/env python3
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from google.cloud import pubsub_v1

from lighweight_runnable import LightRunnable


class CollectScheduler(LightRunnable):
    PUBSUB_TICKERS_TOPIC_NAME = "projects/stocker-300519/topics/collector-tickers"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.publisher = pubsub_v1.PublisherClient()
        self.topic_name = self.PUBSUB_TICKERS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_TICKERS_TOPIC_NAME

    def run(self):
        scheduler = BlockingScheduler()

        self.disable_apscheduler_logs()

        trigger = OrTrigger([IntervalTrigger(minutes=10), DateTrigger()])

        scheduler.add_job(self.publish_tickers,
                          trigger=trigger,
                          max_instances=1,
                          misfire_grace_time=120)

        scheduler.start()

    def publish_tickers(self):
        self.logger.info("Publishing tickers")
        for ticker in self._tickers_list:
            self.publisher.publish(self.topic_name, ticker.encode('utf-8'))


def main():
    try:
        CollectScheduler().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
