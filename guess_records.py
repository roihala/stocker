import json
import logging
import requests

from typing import List
from bson import json_util
from google.cloud import pubsub_v1
from google.cloud.pubsub import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from retry import retry

from client import Client
from collect import Collect
from common_runnable import CommonRunnable
from src.collect.records.filings_pdf_guesser import FilingsPdfGuesser

# TODO: logger name
logger = logging.getLogger('')


try:
    import fitz
except Exception:
    logger.warning("Couldn't import fitz")


class GuessRecords(CommonRunnable):
    GUESSER_SUBSCRIPTION_NAME = 'projects/stocker-300519/subscriptions/records-finder-sub'

    def __init__(self):
        super().__init__()
        self._subscription_name = self.GUESSER_SUBSCRIPTION_NAME + '-dev' if self._debug else self.GUESSER_SUBSCRIPTION_NAME
        self._subscriber = SubscriberClient()

        self.profile_mapping = Client.get_latest_data(self._mongo_db.get_collection("profile"))
        self.publisher = pubsub_v1.PublisherClient()
        self.diffs_topic_name = Collect.PUBSUB_DIFFS_TOPIC_NAME + '-dev' if self._debug else Collect.PUBSUB_DIFFS_TOPIC_NAME

    def run(self):
        streaming_pull_future = self._subscriber.subscribe(self._subscription_name, self.guess_ticker)
        with self._subscriber:
            streaming_pull_future.result()

    def guess_ticker(self, batch: PubSubMessage):
        diff = json.loads(batch.data)[0]
        self.logger.info(f"Detected diff: {diff}")

        try:
            guesser = FilingsPdfGuesser(self._mongo_db, self.profile_mapping)
            # Cloud path is used on prod because it's faster
            ticker = guesser.guess_ticker(self.get_pages_from_pdf(diff['url'] if self._debug else diff['cloud_path']))

            if ticker:
                self.logger.info(f"Guessed {ticker} for {diff.get('record_id')}")

                # Updating ticker
                diff['ticker'] = ticker
                guesser.collection.update_one({'record_id': diff['record_id']},
                                              {'$set': {'ticker': ticker}})

                # Publishing diff as list of one diff
                data = json.dumps([diff], default=json_util.default).encode('utf-8')
                self.publisher.publish(self.diffs_topic_name, data)

            batch.ack()

        except Exception as e:
            logger.warning("Couldn't guess ticker")
            logger.exception(e)
            batch.nack()

    @staticmethod
    @retry(tries=5, delay=0.25)
    def get_pages_from_pdf(filing_url) -> List[str]:
        pages = []

        with fitz.open(stream=requests.get(filing_url).content, filetype="pdf") as doc:
            for page_number in range(0, doc.pageCount):
                pages.append(" ".join(doc[page_number].getText().split()))

        return pages


if __name__ == '__main__':
    try:
        GuessRecords().run()
    except Exception as e:
        logging.exception(e)
