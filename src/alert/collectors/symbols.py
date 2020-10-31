from src.alert.site_collector import SiteCollector
from src.find.site import Site


class Symbols(SiteCollector):
    @property
    def site(self):
        return Site(self._collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)

    def _filter_diff(self, diff) -> bool:
        if diff['changed_key'] == 'verifiedDate':
            return False
        return True
