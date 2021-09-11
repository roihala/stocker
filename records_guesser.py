import logging

from google.cloud.pubsub import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage

from common_runnable import CommonRunnable


class RecordsGuesser(CommonRunnable):
    GUESSER_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/records-finder-sub'

    def __init__(self):
        super().__init__()
        self._subscription_name = self.GUESSER_SUBSCRIPTION_NAME + '-dev' if self._debug else self.GUESSER_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()

    def run(self):
        streaming_pull_future = self._subscriber.subscribe(self._subscription_name, self.guess_ticker)
        with self._subscriber:
            streaming_pull_future.result()

    def guess_ticker(self, batch: PubSubMessage):
        # TODO
        record_id = 0

        collector_args = {'mongo_db': self._mongo_db, 'cache': records_cache, 'date': date, 'debug': self._debug,
                          'record_id': record_id + index, 'symbols_and_names': self.symbols_and_names,
                          'profile_mapping': self.profile_mapping}
        collector = FilingsPdf(**collector_args)

        response = collector.fetch_data()





if __name__ == '__main__':
    try:
        RecordsGuesser().run()
    except Exception as e:
        logging.exception(e)
