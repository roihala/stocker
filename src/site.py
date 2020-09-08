from string import Formatter
import urllib

import requests


class Site(object):
    TICKER_FORMAT = 'ticker'
    COMPANY_NAME_FORMAT = 'company_name'

    TICKER_TRANSLATION_URL = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={ticker}&region=1&lang=en"

    def __init__(self, name, url, is_otc):
        self.name = name
        self.url = url
        self.is_otc = is_otc

    def get_ticker_url(self, ticker):
        company_name = self.get_company_name(ticker)
        format_keys = self.get_format_keys(self.url)\

        if 'ticker' in format_keys:
            return self.url.format(ticker=ticker)

        elif 'company_name' in format_keys:
            return self.url.format(company_name=urllib.parse.quote(company_name))

        else:
            raise Exception("Invalid site format")

    @staticmethod
    def get_format_keys(string):
        return [key for _, key, _, _ in Formatter().parse(string) if key]

    @staticmethod
    def get_company_name(ticker):
        result = requests.get(Site.TICKER_TRANSLATION_URL.format(ticker=ticker))
        try:
            # Getting the full name by yahoo's json structure.
            full_name = result.json()['ResultSet']['Result'][0]["name"]

        except IndexError:
            raise Exception("There is no such ticker: {ticker}".format(ticker=ticker))

        # Removing any non-alphabetic characters and using the name as list.
        fixed_name = [Site.make_alpha(name_part) for name_part in full_name.split(' ')]

        if len(fixed_name) > 1:
            # Removing company name suffix
            fixed_name = fixed_name[0:-1]

        return ' '.join(fixed_name)

    @staticmethod
    def make_alpha(word):
        return ''.join([letter for letter in word if letter.isalpha()])
