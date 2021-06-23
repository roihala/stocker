import logging
import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Dict, List

import fitz
import pymongo
import requests
from retry import retry

from runnable import Runnable
from src.collect.collector_base import CollectorBase

logger = logging.getLogger('RecordsCollect')

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')
MAX_PAGE_SEARCH = 3
COMP_ABBREVIATIONS = ["inc", "ltd", "corp", "corporation", "incorporated"]


class DynamicRecordsCollector(CollectorBase, ABC):
    def __init__(self, tickers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.record_id = self.collection.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get('record_id') + 1
        self._tickers = tickers

    @property
    @abstractmethod
    def url(self):
        # This url must contain {id} format string
        pass

    def collect(self):
        responses = self.__get_responses()
        diffs = []

        for record_id, response in {_: resp for _, resp in responses.items() if resp.ok}.items():
            try:
                ticker = self.__guess_ticker(record_id, response)
            except Exception as e:
                ticker = ''
                logger.exception(e)

            document = self.__generate_document(record_id, response, ticker=ticker if ticker else '')
            self.collection.insert_one(deepcopy(document))

            if ticker:
                diffs.append(self.__generate_diff(document))
            else:
                logger.warning(f"Couldn't resolve ticker for {record_id} at {response.request.url}")
            self.record_id = max(self.record_id, record_id)

        return diffs

    @retry(requests.exceptions.ProxyError, tries=3, delay=0.1)
    def fetch_data(self, index) -> requests.models.Response:
        url = self.url.format(id=self.record_id + index)
        response = requests.get(url)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(url, proxies=Runnable.proxy)

        return response

    def __generate_document(self, record_id, response, ticker):
        return \
            {
                "record_id": record_id,
                "date": self._date.format(),
                "url": response.request.url,
                "ticker": ticker
            }

    def __generate_diff(self, document) -> List[Dict]:
        diff = deepcopy(document)
        diff.update({'diff_type': 'add',
                     'source': self.name
                     })
        return diff

    def __get_responses(self):
        responses = {}
        for i in range(10):
            try:
                responses[self.record_id + i] = self.fetch_data(i)
            except Exception as e:
                logger.warning(f"Couldn't collect record {self.record_id + i}")
                logger.exception(e)

        return responses

    def __guess_ticker(self, record_id, response):
        with fitz.open(self.get_pdf(record_id, response)) as doc:
            ticker = self.__guess_by_company_name(doc)

            if ticker:
                return ticker
            else:
                # TODO: Other guess
                return None

    def __guess_by_company_name(self, doc):
        for page_number in range(0, MAX_PAGE_SEARCH):

            # ['otc markets group inc', 'guidelines v group , inc']
            companies = self.__extract_company_names_from_pdf(doc, page_number)

            if not companies:
                continue

            # split to words & remove commas & dots
            companies_opt = [comp.replace(',', '').replace('.', '').split() for comp in companies]

            # [['otc', 'markets', 'group', 'inc'], ['guidelines', 'v', 'group', 'inc']] ->
            # [['otc markets group inc', 'markets group inc', 'group inc'], ['guidelines v group inc', 'v group inc', 'group inc']]
            optional_companies = [[" ".join(comp[i:]) for i in range(0, len(comp) - 1)] for comp in companies_opt]
            """
            optional companies -> [["a b c", "b c"], ["d g b c", "g b c", "b c"]]
            search "a b c" -> "d g b c" -> "b c" -> "g b c" ...
            """
            for index in range(0, max(len(_) for _ in optional_companies)):
                for comp_name in optional_companies:
                    if index >= len(comp_name):
                        continue

                    result = self.__get_symbol_from_map(comp_name[index])

                    if result:
                        return result

        return None

    def __extract_company_names_from_pdf(self, doc, page_number: int) -> list:
        companies = []
        page = doc[page_number]
        txt = " ".join(page.getText().lower().split())

        for abr in COMP_ABBREVIATIONS:
            regex = fr"((?:[a-z\.,-]+ ){{1,4}}{abr}[\. ])"
            matches = re.findall(regex, txt)

            if matches:
                companies = companies + matches

        return (None if not companies else companies)

    def __get_symbol_from_map(self, comp_name: str) -> str:
        # TODO: Change names.csv company names to lower without commas or dots.
        # that will save us the name.lower().replace(',', '').replace('.', '') statement.
        if type(comp_name) is not str or not comp_name:
            return None

        # the exact same company name
        for symbol, name in self._tickers.items():
            if comp_name == name.lower().replace(',', '').replace('.', ''):
                return symbol

        return None

    @staticmethod
    def get_pdf(record_id, response=None, base_url=None):
        response = response if response else requests.get(base_url.format(id=record_id))
        pdf_path = os.path.join(PDF_DIR, f"{record_id}.pdf")

        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        return pdf_path
