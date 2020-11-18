from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Symbols(SiteCollector):
    FILTER_KEYS = ['isPennyStockExempt', 'verifiedDate']
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'] in self.FILTER_KEYS:
            return None
        return diff

    def get_sorted_history(self, apply_filters=True):
        history = super().get_sorted_history(apply_filters)

        if apply_filters and not history.empty:
            if 'verifiedDate' in history:
                history["verifiedDate"] = history["verifiedDate"].dropna().apply(
                    self.timestamp_to_datestring)

        return history
