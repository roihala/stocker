import logging
from abc import ABC, abstractmethod
from typing import Dict, List

import pymongo
import requests

from runnable import Runnable
from src.collect.collector_base import CollectorBase


logger = logging.getLogger('RecordsCollect')


class DynamicRecordsCollector(CollectorBase, ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.record_id = self.collection.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get('record_id') + 1

    @property
    @abstractmethod
    def url(self):
        # This url must contain {id} format string
        pass

    def collect(self):
        responses = [self.fetch_data(i) for i in range(5)]

        if any([response.ok for response in responses]):
            self.collection.insert_many(self.__generate_documents(responses))
            return self.__generate_diffs(responses)

    def fetch_data(self, index) -> requests.models.Response:
        url = self.url.format(id=self.record_id + index)
        response = requests.get(url)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(url, proxies=Runnable.proxy)

        return response

    def __generate_documents(self, responses):
        return [
            {
                "record_id": self.record_id + index,
                "date": self._date.format(),
                "url": response.request.url
            }
            for index, response in enumerate(responses) if response.ok
        ]

    def __generate_diffs(self, responses) -> List[Dict]:
        return [
            {
                "record_id": self.record_id + index,
                "diff_type": "add",
                "date": self._date.format(),
                "source": self.name,
                "url": response.request.url
            }
            for index, response in enumerate(responses) if response.ok
        ]
