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
COMP_ABBREVIATIONS = ["inc", "ltd", "corp", "adr", "corporation", "incorporated", "technologies", "solutions", "resources"]

RE_SYMBOL = re.compile(fr"([A-Z]{{3,5}})")
RE_MAIL = re.compile(r"[\w\.-]+@[\w\.-]+(\.[\w]+)+")
RE_WEB_URL = re.compile(r"((?:(?:[a-zA-z\-]+[0-9]*)\.[\w\-]+){2,})")
RE_PHONE_NUMBER = re.compile(r"(\(?\d{3}\D{0,3}\d{3}\D{0,3}\d{4})")

RE_BRACKETS = re.compile(r"\[[^)]*\]")
RE_PARENTHESES = re.compile(r"\([^)]*\)")


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
                pages = self.__get_pages_from_pdf(record_id, response)
                ticker = self.__guess_ticker(pages)

            except Exception as e:
                ticker = ''
                logger.exception(e)

            document = self.__generate_document(record_id, response, ticker=ticker if ticker else '')
            self.collection.insert_one(deepcopy(document))

            if ticker:
                diffs.append(self.__generate_diff(document))
            else:
                logger.warning(f"Couldn't resolve ticker for {record_id} at {response.request.url}")

        return diffs

    @retry(requests.exceptions.ProxyError, tries=3, delay=0.1)
    def fetch_data(self, index) -> requests.models.Response:
        url = self.url.format(id=self.record_id + index)
        response = requests.get(url)

        # Trying with proxy
        if response.status_code == 429:
            response = requests.get(url, proxies=Runnable.proxy)

        return response

    def __get_pages_from_pdf(self, record_id, response) -> List[str]:
        pages = []

        with fitz.open(self.get_pdf(record_id, response)) as doc:

            for page_number in range(0, doc.pageCount):
                pages.append(" ".join(doc[page_number].getText().split()))

        return pages

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

    def __guess_ticker(self, pages) -> str:
        symbols_scores = {}

        by_comp_names = self.__guess_by_company_name(pages)
        by_symbols = self.__extract_symbols_from_pdf(pages)
        by_mail_addresses = self.__guess_by_mail_addresses(pages)
        by_web_urls = self.__guess_by_website_urls(pages)
        by_phone_numbers = self.__guess_by_phone_numbers(pages)

        all_symbols = set(
            by_comp_names +
            by_symbols +
            by_mail_addresses +
            by_web_urls +
            by_phone_numbers)

        for symbol in all_symbols:
            symbols_scores[symbol] = 0

            if symbol in by_comp_names:
                symbols_scores[symbol] += 3
            if symbol in by_symbols:
                symbols_scores[symbol] += 2
            if symbol in by_mail_addresses:
                symbols_scores[symbol] += 1
            if symbol in by_web_urls:
                symbols_scores[symbol] += 1
            if symbol in by_phone_numbers:
                symbols_scores[symbol] += 1

        # Return the symbol with the highest score.
        return max(symbols_scores, key=symbols_scores.get)

    def __get_symbol_from_map(self, comp_name: str) -> str:
        if type(comp_name) is not str or not comp_name:
            return ""

        # the exact same company name
        for symbol, name in self._tickers.items():
            if comp_name == self.__clear_text(name):
                return symbol

        return ""

    def __guess_by_company_name(self, pages) -> List[str]:
        optional_symbols = []

        for page in pages:

            # ['otc markets group inc', 'guidelines v group , inc']
            companies = self.__extract_company_names_from_pdf(self.__clear_text(page))

            if not companies:
                continue

            # split to words & remove commas & dots
            companies_opt = [comp.replace(',', '').replace('.', '').split() for comp in companies]
            """
            [['otc', 'markets', 'group', 'inc'], ['guidelines', 'v', 'group', 'inc']] ->
            [['otc markets group inc', 'markets group inc', 'group inc'], ['guidelines v group inc', 'v group inc', 'group inc']]
            """
            optional_companies = [[" ".join(comp[i:]) for i in range(0, len(comp) - 1)] for comp in companies_opt]
            """
            optional companies -> [["a b c", "b c"], ["d g b c", "g b c", "b c"]]
            search "a b c" -> "d g b c" -> "b c" -> "g b c" ...
            """
            for index in range(0, max(len(_) for _ in optional_companies)):
                for comp_name in optional_companies:
                    if index >= len(comp_name):
                        continue

                    symbol = self.__get_symbol_from_map(comp_name[index])

                    if symbol:
                        optional_symbols.append(symbol)

        return optional_symbols

    def __guess_by_mail_addresses(self, pages) -> List[str]:
        mail_addresses = []
        symbols = []

        for page in pages:
            mail_addresses.extend(RE_MAIL.findall(page))

        for address in mail_addresses:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self.collection.find({"email": address})])

        return symbols

    def __guess_by_website_urls(self, pages) -> List[str]:
        web_urls = []
        symbols = []

        for page in pages:
            web_urls.extend(RE_WEB_URL.findall(page))

        for url in web_urls:
            # search mongo for web URLs --> contains
            symbols.extend([profile["ticker"] for profile in self.collection.find({"website": {"$in", url}})])

        return symbols

    def __guess_by_phone_numbers(self, pages) -> List[str]:
        phone_numbers = []
        symbols = []

        for page in pages:
            phone_numbers.extend(RE_PHONE_NUMBER.findall(page))

        for phone_num in phone_numbers:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self.collection.find({"phone": phone_num})])

        return symbols

    @staticmethod
    def __extract_company_names_from_pdf(text) -> List[str]:
        companies = []

        for abr in COMP_ABBREVIATIONS:
            regex = fr"((?:[a-z\.,-]+ ){{1,4}}{abr}[\. ])"
            matches = re.findall(regex, text)

            if matches:
                companies.extend(matches)

        return None if not companies else companies

    @staticmethod
    def __extract_symbols_from_pdf(pages) -> List[str]:
        matches = []

        for page in pages:
            matches.extend(RE_SYMBOL.findall(page))

        return None if not matches else matches

    @staticmethod
    def __clear_text(_str: str) -> str:
        restricted = [',', '.', '-']
        _str = _str.lower()

        for c in restricted:
            _str = _str.replace(c, '')

        _str = RE_PARENTHESES.sub('', _str)
        _str = RE_BRACKETS.sub('', _str)

        return _str

    @staticmethod
    def get_pdf(record_id, response=None, base_url=None):
        response = response if response else requests.get(base_url.format(id=record_id))
        pdf_path = os.path.join(PDF_DIR, f"{record_id}.pdf")

        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        return pdf_path
