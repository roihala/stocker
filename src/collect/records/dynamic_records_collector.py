import logging
from abc import ABC, abstractmethod
from copy import deepcopy

import arrow
import requests
from retry import retry

from src.collect.records.filings_collector import FilingsCollector
from src.common.proxy import proxy_get

logger = logging.getLogger('CollectRecords')


class DynamicRecordsCollector(FilingsCollector, ABC):
    BATCH_SIZE = 15

    def __init__(self, record_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.record_id = record_id

    def collect(self):
        response = self.fetch_data()
        if not response.ok:
            return []

        # Uploading to cloud storage
        pdf_path = self.download_filing(self.record_id, response)

        cloud_path = self.upload_filing(self.record_id, pdf_path)

        document = self.__generate_document(cloud_path)
        self.collection.insert_one(deepcopy(document))

        diff = super().decorate_diff(document, cloud_path=cloud_path, record_id=self.record_id)

        return [diff]

    @retry(tries=5, delay=0.25)
    def fetch_data(self) -> requests.models.Response:
        url = self.filing_base_url.format(id=self.record_id)
        return proxy_get(url, self._debug)

    def __generate_document(self, cloud_path):
        return \
            {
                "record_id": self.record_id,
                "date": self._date.format(),
                "url": self.filing_base_url.format(id=self.record_id),
                "cloud_path": cloud_path
            }
