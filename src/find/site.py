from string import Formatter
import urllib

import requests


class Site(object):
    TICKER_FORMAT = 'ticker'
    COMPANY_NAME_FORMAT = 'company_name'

    TICKER_TRANSLATION_URL = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={ticker}&region=1&lang=en"
    TICKER_PROFILE_URL = 'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}'

    TICKERS_DELIMITER = "%2C"

    def __init__(self, name, url, is_otc, api_key=None):
        self.name = name
        self.url = url
        self.is_otc = is_otc
        self.api_key = api_key

    def get_ticker_url(self, ticker, strip=False):
        format_keys = self.get_format_keys(self.url)

        if 'ticker' in format_keys:
            url = self.url.format(ticker=ticker)

        elif 'company_name' in format_keys:
            url = self.url.format(company_name=urllib.parse.quote(self.get_company_name(ticker)))

        elif 'company_site' in format_keys:
            url = self.url.format(company_site=self.get_company_site(ticker))

        else:
            raise Exception("Invalid site format: {url}".format(url=self.url))

        return url.strip('"') if strip else url

    def get_company_site(self, ticker):
        if not self.is_otc:
            raise Exception("Site.get_company_site: Unimplemented for non OTC markets")

        response = requests.get(self.TICKER_PROFILE_URL.format(ticker=ticker))

        try:
            return response.json()['website']
        except KeyError:
            raise Exception("Couldn't get the website of {ticker}".format(ticker=ticker))

    def get_tickers_list_url(self, tickers_list):
        format_keys = self.get_format_keys(self.url)
        if 'tickers_list' in format_keys and 'api_key' in format_keys:
            if self.api_key:
                return self.url.format(api_key=self.api_key, tickers_list=self.TICKERS_DELIMITER.join(tickers_list))
            else:
                raise Exception("No API key supplied for site: {url}".format(self.url))
        else:
            raise Exception("Invalid site format: {url}".format(url=self.url))

    @staticmethod
    def get_format_keys(string):
        return [key for _, key, _, _ in Formatter().parse(string) if key]

    @staticmethod
    def get_company_name(ticker):
        if not Site.is_ticker_exist(ticker):
            raise InvalidTickerExcpetion("There is no such ticker: {ticker}".format(ticker=ticker))

        response = requests.get(Site.TICKER_TRANSLATION_URL.format(ticker=ticker))

        # Getting the full name by yahoo's json structure.
        full_name = response.json()['ResultSet']['Result'][0]["name"]

        # Removing any non-alphabetic characters and using the name as list.
        fixed_name = [Site.make_alpha(name_part) for name_part in full_name.split(' ')]

        if len(fixed_name) > 1:
            # Removing company name suffix
            fixed_name = fixed_name[0:-1]

        return ' '.join(fixed_name)

    @staticmethod
    def make_alpha(word):
        return ''.join([letter for letter in word if letter.isalpha()])

    @staticmethod
    def is_ticker_exist(ticker):
        response = requests.get(Site.TICKER_TRANSLATION_URL.format(ticker=ticker))

        # Yahoo's json structure should contain a list with information.
        result_list = response.json()['ResultSet']['Result']

        if len(result_list) == 0:
            return False

        else:
            return True


class InvalidTickerExcpetion(Exception):
    pass
