import logging
import pandas
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import Dict, List

import arrow
import requests
from retry import retry

from src.collect.collector_base import CollectorBase


logger = logging.getLogger('RecordsCollect')

username = "yonisoli"
password = "5ff06d-6ecc98-91006b-86dd29-388b2c"

PROXY_RACK_DNS = "megaproxy.rotating.proxyrack.net:222"
proxy_url = "http://{}:{}@{}".format(username, password, PROXY_RACK_DNS)
proxy = {"http": proxy_url,
         'https': proxy_url}


class RecordsCollector(CollectorBase, ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.cache.get(self.name):
            df = pandas.DataFrame(self.collection.find())
            self.cache[self.name] = df[df['date'] > arrow.utcnow().shift(hours=-7).format()].to_dict('records')

    @property
    @abstractmethod
    def url(self):
        pass

    def collect(self):
        records = self.fetch_data()

        new_records = self.extract_new_records(records)

        if new_records:
            [record.update({'date': self._date.format()}) for record in new_records]
            self.collection.insert_many(new_records)
            self.cache[self.name] += new_records
            self.__flush()

        return [self.__generate_diff(record) for record in new_records]

    @retry(JSONDecodeError, tries=3, delay=1)
    def fetch_data(self) -> List[Dict]:
        response = requests.get(self.url)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(self.url, proxies=proxy)

        if response.status_code != 200:
            logger.warning("Couldn't collect record at {url}, bad status code: {code}".format(
                url=self.url,
                code=response.status_code))
            raise ValueError(self.url)

        return response.json().get('records')

    def extract_new_records(self, records: List[Dict]) -> List[Dict]:
        return [record for record in records if record.get('id') not in [record.get('id') for record in self.cache[self.name]]]

    def __flush(self):
        # Caching last 7 days of records
        self.cache[self.name] = [diff for diff in self.cache[self.name] if (arrow.utcnow() - arrow.get(diff.get('releaseDate'))).days < 7]

    def __generate_diff(self, record: dict):
        return {
            "title": record.get('title'),
            "record_id": record.get('id'),
            "diff_type": "add",
            "date": self._date.format(),
            "source": self.name,
            "alerted": False,
            "ticker": record.get('symbol')
        }
