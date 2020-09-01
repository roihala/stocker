#!/usr/bin/env python

import requests
import argparse
import os

from src.Gui.App import run_gui

TICKER_TRANSLATION_URL = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={ticker}&region=1&lang=en"
START_WEBSITE_COMMAND = "start chrome.exe "

TICKER_SITES = [
    "https://finance.yahoo.com/quote/{ticker}?ltr=1",
    "https://finviz.com/quote.ashx?t={ticker}",
    "https://stocktwits.com/symbol/{ticker}",
    "https://ih.advfn.com/stock-market/NASDAQ/{ticker}/stock-price",
    "https://thefly.com/news.php?symbol={ticker}",
    "https://www.otcmarkets.com/stock/{ticker}/overview"
]

SEARCH_SITES = {
    "https://www.globenewswire.com/Search/NewsSearch?keyword={company_name}",
    "https://www.prnewswire.com/search/all/?keyword={company_name}",
    "https://www.bio.org/search?keywords={company_name}"
}


def get_company_name(ticker):
    result = requests.get(TICKER_TRANSLATION_URL.format(ticker=ticker))
    try:
        # Getting the full name by yahoo's json structure.
        full_name = result.json()['ResultSet']['Result'][0]["name"]

    except IndexError:
        raise Exception("There is no such ticker: {ticker}".format(ticker=ticker))

    # Removing any non-alphabetic characters and using the name as list.
    fixed_name = [make_alpha(name_part) for name_part in full_name.split(' ')]

    if len(fixed_name) > 1:
        # Removing company name suffix
        fixed_name = fixed_name[0:-1]

    return ' '.join(fixed_name)


def make_alpha(word):
    return ''.join([letter for letter in word if letter.isalpha()])


def search_stock(ticker):
    company_name = get_company_name(ticker)

    for site in TICKER_SITES:
        os.system(START_WEBSITE_COMMAND + '"' + site.format(ticker=args.ticker) + '"')

    for site in SEARCH_SITES:
        os.system(START_WEBSITE_COMMAND + '"' + site.format(company_name=company_name) + '"')


def main():
    args = get_args()

    if not args.ticker:
        run_gui()

    search_stock(args.ticker)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', dest='ticker')

    return parser.parse_args()


if __name__ == '__main__':
    main()
