import logging
import os
import re
from typing import List
from collections import Counter

# TODO: logger name
logger = logging.getLogger('')

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')
COMP_ABBREVIATIONS = {"inc": "incorporated", "ltd": "limited", "corp": "corporation", "adr": None,
                      "incorporated": "inc", "limited": "ltd", "corporation":"corp"}

# ["technologies", "solutions", "resources"]
SYMBOLS_BLACKLIST_SET = {"OTCM", "OTC", "FINRA"}
POPULAR_EMAIL_DOMAINS = ["gmail", "hotmail", "yahoo", "aol", "msn", "orange", "wanadoo", "live", "ymail", "outlook"]

RE_SYMBOL = re.compile(fr"(\b[A-Z]{{3,5}}\b)")
RE_MAIL = re.compile(r"([\w\.-]+@[\w\.-]+(?:\.[\w]+)+)")
RE_WEB_URL = re.compile(r"((?:(?:[a-zA-z\-]+[0-9]*)\.[\w\-]+){2,})")
RE_PHONE_NUMBER = re.compile(r"(\(?\d{3}\D{0,3}\d{3}\D{0,3}\d{4})")
RE_ZIP_CODE = re.compile(r"(^\d{5}(?:[-\s]\d{4})?$)")
RE_CUSIP = re.compile(r"([0-9]{3}[a-zA-Z0-9]{6})")


RE_BRACKETS = re.compile(r"\[[^)]*\]")
RE_PARENTHESES = re.compile(r"\([^)]*\)")


class FilingsPdfGuesser(object):
    def __init__(self, mongo_db, profile_mapping):
        self.mongo_db = mongo_db
        self.collection = self.mongo_db.get_collection('filings_pdf')
        self._mongo__profile = self.mongo_db.get_collection("profile")
        self._mongo__securities = self.mongo_db.get_collection("securities")

        self.profile_mapping = profile_mapping
        self.symbols_and_names = [(ticker, self.clear_text(self.profile_mapping[ticker]["name"]))
                                  for ticker in self.profile_mapping]
        self.symbols = [ticker for ticker in self.profile_mapping]

    def guess_ticker(self, pages) -> str:
        parser_results = [
            self.__guess_by_company_name(pages),
            self.__extract_symbols_from_pdf(pages),
            self.__guess_by_mail_addresses(pages),
            self.__guess_by_website_urls(pages),
            self.__guess_by_phone_numbers(pages),
            self.__guess_by_zip_codes(pages),
            self.__guess_by_cusip(pages)
        ]

        for method_results in parser_results:
            print(method_results)

        # Merge all counters
        tickers_score = sum(parser_results, Counter())

        # Remove blacklisted tickers such as OTCM
        for x in SYMBOLS_BLACKLIST_SET:
            del tickers_score[x]

        # Calculate score
        for ticker in tickers_score:
            multiplier = 0

            for method_results in parser_results:
                if ticker in method_results:
                    multiplier += 1

            tickers_score[ticker] = tickers_score[ticker] * multiplier

        print(tickers_score)
        try:
            highest_score_ticker = tickers_score.most_common(1)[0][0]
            if tickers_score[highest_score_ticker] > 15:
                return highest_score_ticker
            else:
                return ""
        except:
            return ""

    def __get_symbol_from_map(self, comp_name: str) -> str:
        if not comp_name:
            return ""

        # the exact same company name
        for symbol, name in self.symbols_and_names:
            if self.clear_text(comp_name) == name:
                return symbol

        return ""

    def __guess_by_company_name(self, pages) -> Counter:
        optional_symbols = []

        for page in pages:

            # ['otc markets group inc', 'guidelines v group , inc']
            companies = self.__extract_company_names_from_pdf(self.clear_text(page))

            if not companies:
                continue

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

        return Counter(optional_symbols)

    def __guess_by_mail_addresses(self, pages) -> Counter:
        mail_addresses = []
        symbols = []

        for page in pages:
            mail_addresses.extend(RE_MAIL.findall(page))

        for address in mail_addresses:
            domain = address.split('@')[1].split('.')[0]

            if domain not in POPULAR_EMAIL_DOMAINS:
                # search mongo for email address
                symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"email": {"$regex": ".*" +
                                                                                                                domain +
                                                                                                                ".*"}
                                                                                            })])
            else:
                symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"email": address})])

        return Counter(symbols)

    def __guess_by_website_urls(self, pages) -> Counter:
        web_urls = []
        symbols = []

        for page in pages:
            web_urls.extend(RE_WEB_URL.findall(page))

        for url in web_urls:
            # search mongo for web URLs --> contains
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"website": {"$regex": ".*" +
                                                                                                              url + ".*"}})])

        return Counter(symbols)

    def __guess_by_phone_numbers(self, pages) -> Counter:
        phone_numbers = []
        symbols = []

        for page in pages:
            phone_numbers.extend(RE_PHONE_NUMBER.findall(page))

        for phone_num in phone_numbers:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"phone": phone_num})])

        return Counter(symbols)

    def __guess_by_zip_codes(self, pages) -> Counter:
        zip_codes = []
        symbols = []

        for page in pages:
            zip_codes.extend(RE_ZIP_CODE.findall(page))

        for _zip in zip_codes:
            # search mongo for email address
            symbols.extend([profile["ticker"] for profile in self._mongo__profile.find({"zip": {"$regex": ".*" +
                                                                                                          _zip + ".*"}})])

        return Counter(symbols)

    def __guess_by_cusip(self, pages) -> Counter:
        cusips = []
        symbols = []

        for page in pages:
            cusips.extend(RE_CUSIP.findall(page))

        for cp in cusips:
            # search securities for matching cusips
            symbols.extend([sec["symbol"] for sec in self._mongo__securities.find({"cusip": cp})])

        return Counter(symbols)

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

    def __extract_symbols_from_pdf(self, pages) -> Counter:
        symbols = []
        matches = []

        for page in pages:
            matches.extend(RE_SYMBOL.findall(page))

        for symbol in matches:
            if symbol in self.symbols:
                symbols.append(symbol)

        return Counter(symbols)

    @staticmethod
    def clear_text(_str: str) -> str:
        restricted = [',', '.', '-']
        _str = _str.lower()

        for c in restricted:
            _str = _str.replace(c, '')

        _str = RE_PARENTHESES.sub('', _str)
        _str = RE_BRACKETS.sub('', _str)

        return _str
