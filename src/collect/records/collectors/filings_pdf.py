import logging
import os
import re
from typing import List

from src.collect.records.dynamic_records_collector import DynamicRecordsCollector

logger = logging.getLogger('RecordsCollect')

try:
    import fitz
except Exception:
    logger.warning("Couldn't import fitz")

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')
COMP_ABBREVIATIONS = {"inc": "incorporated", "ltd": "limited", "corp": "corporation", "adr": None,
                      "incorporated": "inc", "limited": "ltd", "corporation":"corp"}

# ["technologies", "solutions", "resources"]
SYMBOLS_BLACKLIST_SET = {"OTCM", "FINRA"}

RE_SYMBOL = re.compile(fr"(\b[A-Z]{{3,5}}\b)")
RE_MAIL = re.compile(r"([\w\.-]+@[\w\.-]+(?:\.[\w]+)+)")
RE_WEB_URL = re.compile(r"((?:(?:[a-zA-z\-]+[0-9]*)\.[\w\-]+){2,})")
RE_PHONE_NUMBER = re.compile(r"(\(?\d{3}\D{0,3}\d{3}\D{0,3}\d{4})")
RE_ZIP_CODE = re.compile(r"(^\d{5}(?:[-\s]\d{4})?$)")

RE_BRACKETS = re.compile(r"\[[^)]*\]")
RE_PARENTHESES = re.compile(r"\([^)]*\)")


class FilingsPdf(DynamicRecordsCollector):
    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from client import Client
        self._mongo__profile = self._mongo_db.get_collection("profile")
        self._profile_mapping = Client.get_latest_data(self._mongo__profile)
        self._symbols_and_names = [(ticker, self.__clear_text(self._profile_mapping[ticker]["name"]))
                                   for ticker in self._profile_mapping]

    @property
    def filing_base_url(self):
        return 'http://www.otcmarkets.com/financialReportViewer?id={id}'

    def guess_ticker(self, pages) -> str:
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
    def __extract_company_names_from_pdf(text) -> List[str]:
        companies = []
        matches = []

        # if regex captures shortcut abr then add the full abr and vice versa
        for abr in COMP_ABBREVIATIONS.keys():
            regex = fr"((?:[a-z\.,-]+ ){{1,4}}{abr}[\. ])"
            results = list(set(re.findall(regex, text)))

            for res in results:
                matches.append(res)
                if COMP_ABBREVIATIONS[abr]:
                    matches.append(res.replace(abr, COMP_ABBREVIATIONS[abr]))

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
