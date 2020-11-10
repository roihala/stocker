from src.alert.site_collector import SiteCollector
from src.find.site import Site, InvalidTickerExcpetion


class ShareStructure(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    def fetch_data(self):
        try:
            data = super().fetch_data()
            return data[0]['securities']
        except KeyError:
            raise InvalidTickerExcpetion("Can't get the securities sector from the profile")

    def _edit_diff(self, diff):
        pass
