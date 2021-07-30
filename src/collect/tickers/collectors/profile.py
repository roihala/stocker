from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'http://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @staticmethod
    def get_sons():
        return ['securities']
