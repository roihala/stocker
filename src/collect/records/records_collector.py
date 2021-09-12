import logging
import pandas
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import Dict, List

import arrow
import requests
from retry import retry

from runnable import Runnable
from src.collect.records.filings_collector import FilingsCollector
from src.common.otcm import REQUIRED_HEADERS

logger = logging.getLogger('CollectRecords')


class RecordsCollector(FilingsCollector, ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.cache.get(self.name):
            df = pandas.DataFrame(self.collection.find())
            self.cache[self.name] = df[df['date'] > arrow.utcnow().shift(days=-7).format()].to_dict('records') if 'date' in df.columns else []

    @property
    @abstractmethod
    def records_url(self):
        pass

    def collect(self):
        records = self.fetch_data()

        new_records = self.extract_new_records(records)

        if new_records:
            logger.info(f"Detected new records: {new_records}")
            [record.update({'date': self._date.format(), 'ticker': record.get('symbol'), 'record_id': record.get('id')})
             for record in new_records]
            self.collection.insert_many(new_records)
            self.cache[self.name] += new_records
            self.__flush()

            # Uploading all pdfs to cloud and adding them as diffs
            pdf_paths = [self.download_filing(record.get('id')) for record in new_records]
            cloud_paths = [self.upload_filing(record.get('id'), pdf_path) for record, pdf_path in zip(new_records, pdf_paths)]
            diffs = [self.__generate_diff(record, cloud_path) for record, cloud_path in zip(records, cloud_paths)]
            return diffs
        else:
            return []

    @retry((JSONDecodeError, requests.exceptions.ConnectionError), tries=3, delay=1)
    def fetch_data(self) -> List[Dict]:
        response = requests.get(self.records_url, headers=REQUIRED_HEADERS)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(self.records_url, proxies=Runnable.proxy, headers=REQUIRED_HEADERS)

        if response.status_code != 200:
            logger.warning("Couldn't collect record at {url}, bad status code: {code}".format(
                url=self.records_url,
                code=response.status_code))
            raise ValueError(self.records_url)

        return response.json().get('records')

    def extract_new_records(self, records: List[Dict]) -> List[Dict]:
        return [record for record in records if record.get('id') not in [_.get('id') for _ in self.cache[self.name]]]

    def __flush(self):
        # Caching last 7 days of records
        self.cache[self.name] = [diff for diff in self.cache[self.name] if (arrow.utcnow() - arrow.get(diff.get('releaseDate'))).days < 7]

    def __generate_diff(self, record: dict, cloud_path: str):
        return super().decorate_diff({
            "ticker": record.get('symbol')
        }, cloud_path=cloud_path, record_id=record.get('id'))
