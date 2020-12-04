import os

from src.find.site import Site


START_WEBSITE_COMMAND = ["start", "chrome.exe"]

SITES = [
    Site("otcmarkets", '"https://www.otcmarkets.com/stock/{ticker}/profile"', is_otc=True),
    Site("dilution", '"https://imvicharts.ngrok.io/ticker/{ticker}/720"', is_otc=True),
    Site("filingre", '"https://www.filingre.com/stock/{ticker}"', is_otc=True),
    Site("investorshub", '"https://ih.advfn.com/stock-market/NASDAQ/{ticker}/stock-price"', is_otc=True),
    Site("globenewswire", '"https://www.globenewswire.com/Search/NewsSearch?keyword={company_name}"', is_otc=True),
    Site("yahoo", '"https://finance.yahoo.com/quote/{ticker}?ltr=1"', is_otc=False),
    Site("finviz", '"https://finviz.com/quote.ashx?t={ticker}"', is_otc=False),
    Site("stocktwits", '"https://stocktwits.com/symbol/{ticker}"', is_otc=False),
    Site("thefly", '"https://thefly.com/news.php?symbol={ticker}"', is_otc=False),
    Site("bamsec", '"https://www.bamsec.com/entity-search/search?q={ticker}"', is_otc=False),
    Site("prnewswire", '"https://www.prnewswire.com/search/all/?keyword={company_name}"', is_otc=False),
    Site("bio", '"https://www.bio.org/search?keywords={company_name}"', is_otc=False),
    Site("twitter", '"https://twitter.com/search?q=%24{ticker}&src=typed_query"', is_otc=True),
    Site("wayback", '"https://web.archive.org/web/*/{company_site}"', is_otc=True),
    Site("company", '"{company_site}"', is_otc=True),
    Site("google",
         '"https://www.google.com/search?q={company_name}&aqs=chrome..69i57j0l7.815j0j1&sourceid=chrome&ie=UTF-8"',
         is_otc=False)
]


def search_stock(ticker, is_otc, exclude_list, include_list):
    for site in SITES:
        if site.name in include_list:
            os.system(' '.join(START_WEBSITE_COMMAND + [site.get_ticker_url(ticker)]))

        # Making sure that the is_otc flag matches the website's argument
        elif is_otc != site.is_otc:
            continue

        elif site.name in exclude_list:
            continue

        else:
            os.system(' '.join(START_WEBSITE_COMMAND + [site.get_ticker_url(ticker)]))
