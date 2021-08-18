import logging
import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Dict, List, Tuple

import arrow
import pymongo
import requests
from retry import retry

from google.cloud import storage

from runnable import Runnable
from src.collect.collector_base import CollectorBase

logger = logging.getLogger('RecordsCollect')

try:
    import fitz
except Exception:
    logger.warning("Couldn't import fitz")

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')
COMP_ABBREVIATIONS = ["inc", "ltd", "corp", "adr", "corporation", "limited", "incorporated"]

# ["technologies", "solutions", "resources"]
SYMBOLS_BLACKLIST_SET = {"OTCM", "FINRA"}

RE_SYMBOL = re.compile(fr"(\b[A-Z]{{3,5}}\b)")
RE_MAIL = re.compile(r"([\w\.-]+@[\w\.-]+(?:\.[\w]+)+)")
RE_WEB_URL = re.compile(r"((?:(?:[a-zA-z\-]+[0-9]*)\.[\w\-]+){2,})")
RE_PHONE_NUMBER = re.compile(r"(\(?\d{3}\D{0,3}\d{3}\D{0,3}\d{4})")
RE_ZIP_CODE = re.compile(r"(^\d{5}(?:[-\s]\d{4})?$)")

RE_BRACKETS = re.compile(r"\[[^)]*\]")
RE_PARENTHESES = re.compile(r"\([^)]*\)")


class DynamicRecordsCollector(CollectorBase, ABC):
    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from client import Client
        self.record_id = int(
            self.collection.find().sort('record_id', pymongo.DESCENDING).limit(1)[0].get('record_id')) + 1

        self._mongo__profile = self._mongo_db.get_collection("profile")
        self._profile_mapping = Client.get_latest_data(self._mongo__profile)
        self._symbols_and_names = [(ticker, self.__clear_text(self._profile_mapping[ticker]["name"]))
                                   for ticker in self._profile_mapping]

        self._bucket_name = self.name + '-dev' if self._debug else self.name
        self._storage_bucket = storage.Client().bucket(self._bucket_name)

    @property
    @abstractmethod
    def url(self):
        # This url must contain {id} format string
        pass

    def collect(self):
        responses = self.__get_responses()
        diffs = []

        for record_id, response in {_: resp for _, resp in responses.items() if resp.ok}.items():
            pdf_path = self.get_pdf(record_id, response)

            try:
                ticker = self.__guess_ticker(self.__get_pages_from_pdf(pdf_path))
            except Exception as e:
                ticker = ''
                logger.exception(e)

            document = self.__generate_document(record_id, response, ticker=ticker if ticker else '')
            self.collection.insert_one(deepcopy(document))

            if ticker:
                # Uploading to cloud storage
                blob = f"{ticker}/{arrow.utcnow().timestamp}"
                self._storage_bucket.blob(blob).upload_from_filename(pdf_path)
                cloud_path = self.CLOUD_STORAGE_BASE_PATH.format(bucket=self._bucket_name, blob=blob)
                diffs.append(self.__generate_diff(document, cloud_path))

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

    def __generate_diff(self, document, cloud_path) -> List[Dict]:
        diff = deepcopy(document)
        diff.update({'diff_type': 'add',
                     'source': self.name,
                     'cloud_path': cloud_path
                     })
        return diff

    def __get_responses(self):
        responses = {}
        self.record_id = 295387

        for i in range(2):
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
        by_zip_codes = self.__guess_by_zip_codes(pages)

        # logger.info("COMP_NAMES RESULTS: " + str(by_comp_names))
        # logger.info("SYMBOLS RESULT: " + str(by_symbols))
        # logger.info("MAIL_ADDRESSES RESULTS: " + str(by_mail_addresses))
        # logger.info("WEB: " + str(by_web_urls))
        # logger.info("PHONES: " + str(by_phone_numbers))
        # logger.info("ZIP_CODES: " + str(by_zip_codes))

        all_symbols = set(
            by_comp_names +
            by_symbols +
            by_mail_addresses +
            by_web_urls +
            by_phone_numbers) - SYMBOLS_BLACKLIST_SET

        for symbol in all_symbols:
            symbols_scores[symbol] = 0

            if symbol in by_comp_names:
                symbols_scores[symbol] += 2
            if symbol in by_symbols:
                symbols_scores[symbol] += 1 if len(by_symbols) > 1 else 2
            if symbol in by_mail_addresses:
                symbols_scores[symbol] += 1 if len(by_mail_addresses) > 1 else 2
            if symbol in by_web_urls:
                symbols_scores[symbol] += 1 if len(by_web_urls) > 1 else 2
            if symbol in by_phone_numbers:
                symbols_scores[symbol] += 1 if len(by_phone_numbers) > 1 else 2
            if symbol in by_zip_codes:
                symbols_scores[symbol] += 1 if len(by_zip_codes) > 1 else 2

        # Return the symbol with the highest score.
        if symbols_scores:
            symbol = max(symbols_scores, key=symbols_scores.get)
            return symbol if symbols_scores[symbol] > 4 else ""
        else:
            return ""

    def __get_symbol_from_map(self, comp_name: str) -> str:
        if not comp_name:
            return ""

        # the exact same company name
        for symbol, name in self._symbols_and_names:
            if self.__clear_text(comp_name) == name:
                return symbol

        return ""

    def __guess_by_company_name(self, pages) -> List[str]:
        optional_symbols = []

        for page in pages:

            # ['otc markets group inc', 'guidelines v group , inc']
            companies = self.__extract_company_names_from_pdf(self.__clear_text(page))

            if not companies:
                continue

            # logger.info("COMPANY_NAMES: " + str(companies))

            # split to words & remove commas & dots
            companies_opt = [comp.split() for comp in companies]
            """
            [['otc', 'markets', 'group', 'inc'], ['guidelines', 'v', 'group', 'inc']] ->
            [['otc markets group inc', 'markets group inc', 'group inc'], ['guidelines v group', 'v group', 'group', 'inc']]
            """
            optional_companies = [[" ".join(comp[i:]) for i in range(0, len(comp) - 2)] for comp in companies_opt]
            """
            optional companies -> [["a b c", "b c"], ["d g b c", "g b c", "b c"]]
            search "a b c" -> "d g b c" -> "b c" -> "g b c" ...
            """
            for index in range(0, max(len(_) for _ in optional_companies)):
                for opt_comp_names in optional_companies:
                    if index >= len(opt_comp_names):
                        continue

                    symbol = self.__get_symbol_from_map(opt_comp_names[index])

                    if symbol:
                        optional_symbols.append(symbol)

        return list(set(optional_symbols)) if optional_symbols else []

    def __guess_by_mail_addresses(self, pages) -> List[str]:
        mail_addresses = []
        symbols = []

        for page in pages:
            mail_addresses.extend(RE_MAIL.findall(page))

        # logger.info("MAILS: " + str(mail_addresses))
        for address in mail_addresses:
            domain = address.split('@')[1]

            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"email": {"$regex": ".*" +
                                                                                                            domain}})])

        return list(set(symbols)) if symbols else []

    def __guess_by_website_urls(self, pages) -> List[str]:
        web_urls = []
        symbols = []

        for page in pages:
            web_urls.extend(RE_WEB_URL.findall(page))

        # logger.info("WEBSITES: " + str(web_urls))
        for url in web_urls:
            # search mongo for web URLs --> contains
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"website": {"$regex": ".*" +
                                                                                                              url + ".*"}})])

        return list(set(symbols)) if symbols else []

    def __guess_by_phone_numbers(self, pages) -> List[str]:
        phone_numbers = []
        symbols = []

        for page in pages:
            phone_numbers.extend(RE_PHONE_NUMBER.findall(page))

        # logger.info("PHONE NUMBERS: " + str(phone_numbers))
        for phone_num in phone_numbers:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"phone": phone_num})])

        return list(set(symbols)) if symbols else []

    def __guess_by_zip_codes(self, pages) -> List[str]:
        zip_codes = []
        symbols = []

        for page in pages:
            zip_codes.extend(RE_ZIP_CODE.findall(page))

        # logger.info("ZIP CODES: " + str(zip_codes))
        for _zip in zip_codes:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"zip": {"$regex": ".*" +
                                                                                                          _zip + ".*"}})])

        return list(set(symbols)) if symbols else []

    @staticmethod
    def get_pdf(record_id, response=None, base_url=None):
        response = response if response else requests.get(base_url.format(id=record_id))
        pdf_path = os.path.join(PDF_DIR, f"{record_id}.pdf")

        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        return pdf_path

    @staticmethod
    def __get_pages_from_pdf(pdf_path) -> List[str]:
        pages = []

        with fitz.open(pdf_path) as doc:
            for page_number in range(0, doc.pageCount):
                pages.append(" ".join(doc[page_number].getText().split()))

        return pages

    @staticmethod
    def __extract_company_names_from_pdf(text) -> List[str]:
        companies = []

        # TODO: if regex captures shortcut abr then add the full abr and vice versa
        for abr in COMP_ABBREVIATIONS:
            regex = fr"((?:[a-z\.,-]+ ){{1,4}}{abr}[\. ])"
            matches = list(set(re.findall(regex, text)))

            if matches:
                companies.extend(matches)

        return None if not companies else companies

    @staticmethod
    def __extract_symbols_from_pdf(pages) -> List[str]:
        matches = []

        for page in pages:
            matches.extend(RE_SYMBOL.findall(page))

        return list(set(matches)) if matches else []

    @staticmethod
    def __clear_text(_str: str) -> str:
        restricted = [',', '.', '-']
        _str = _str.lower()

        for c in restricted:
            _str = _str.replace(c, '')

        _str = RE_PARENTHESES.sub('', _str)
        _str = RE_BRACKETS.sub('', _str)

        return _str
