import json_flatten

from src.alert.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    SEPERATOR = '&'

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    def _filter_diff(self, diff) -> bool:
        return True
