import logging
from abc import ABC, abstractmethod
from copy import deepcopy
import requests
from retry import retry


from runnable import Runnable
from src.collect.records.filings_collector import FilingsCollector

logger = logging.getLogger('RecordsCollect')


class DynamicRecordsCollector(FilingsCollector, ABC):
    BATCH_SIZE = 15

    def __init__(self, record_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.record_id = record_id

    @abstractmethod
    def guess_ticker(self, pages) -> str:
        pass

    def collect(self):
        diff = None

        response = self.fetch_data()
        pdf_path = self.get_pdf(self.record_id, response)

        try:
            if pdf_path:
                ticker = self.guess_ticker(self._get_pages_from_pdf(pdf_path))
            else:
                ticker = ''
        except Exception as e:
            ticker = ''
            logger.warning("Couldn't guess ticker")
            logger.exception(e)

        document = self.__generate_document(response, ticker=ticker if ticker else '')
        self.collection.insert_one(deepcopy(document))

        if ticker:
            # Uploading to cloud storage
            cloud_path = self.upload_filing(ticker, pdf_path)

            # Updating document with cloud path
            self.collection.update_one(document, {'$set': {'cloud_path': cloud_path}})
            diff = super().decorate_diff(document, cloud_path=cloud_path, record_id=self.record_id)

        else:
            logger.warning(f"Couldn't resolve ticker for {self.record_id} at {response.request.url}")

        return [diff] if diff else []

    @retry(tries=3, delay=0.5)
    def fetch_data(self) -> requests.models.Response:
        url = self.filing_base_url.format(id=self.record_id)
        response = requests.get(url)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(url, proxies=Runnable.proxy)

        return response

    def __generate_document(self, response, ticker):
        return \
            {
                "record_id": self.record_id,
                "date": self._date.format(),
                "url": response.request.url,
                "ticker": ticker
            }
