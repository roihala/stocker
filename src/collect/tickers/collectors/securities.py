from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Securities(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'http://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    def fetch_data(self, data=None):
        try:
            data = super().fetch_data(data)
            return data['securities'][0]
        except KeyError:
            raise ValueError("Can't get the securities sector from the profile")
