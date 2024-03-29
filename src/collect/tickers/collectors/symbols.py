from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Symbols(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'http://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)
