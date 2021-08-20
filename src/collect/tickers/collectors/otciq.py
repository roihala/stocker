from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Otciq(SiteCollector):
    @property
    def site(self):
        return Site('otciq', 'https://backend.otcmarkets.com/otcapi/company/hasIqAccount/{ticker}', is_otc=True)

    def fetch_data(self, data=None):
        is_iq = super().fetch_data()
        return {'hasIqAccount': is_iq}
