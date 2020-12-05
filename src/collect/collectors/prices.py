from src.collect.site_collector import SiteCollector
from src.find.site import Site, InvalidTickerExcpetion


class Prices(SiteCollector):
    @property
    def name(self) -> str:
        return 'prices'

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                    True)

    def _edit_diff(self, diff):
        return None
