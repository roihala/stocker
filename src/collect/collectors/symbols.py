from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Symbols(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)

    def get_sorted_history(self, apply_filters=True):
        history = super().get_sorted_history(apply_filters)

        if apply_filters and not history.empty:
            if 'verifiedDate' in history:
                history["verifiedDate"] = history["verifiedDate"].dropna().apply(
                    self.timestamp_to_datestring)

        return history
