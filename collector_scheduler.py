# !/usr/bin/env python3
import logging

from google.cloud import pubsub_v1

from lighweight_runnable import LightRunnable


class CollectScheduler(LightRunnable):
    PUBSUB_TICKERS_TOPIC_NAME = "projects/stocker-300519/topics/collector-tickers"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.publisher = pubsub_v1.PublisherClient()
        self.topic_name = self.PUBSUB_TICKERS_TOPIC_NAME + '-dev' if self._debug else self.PUBSUB_TICKERS_TOPIC_NAME

    def run(self):
        self.logger.info("Publishing tickers")
        for ticker in self._tickers_list:
            self.publisher.publish(self.topic_name, ticker.encode('utf-8'))
        self.logger.info("Finished publishing tickers")


def main():
    try:
        CollectScheduler().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
