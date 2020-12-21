from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Symbols(SiteCollector):
    @property
    def filter_keys(self):
        return ['isPennyStockExempt', 'verifiedDate']

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/{ticker}/badges?symbol={ticker}', True)

    @property
    def hierarchy(self):
        return {'verifiedProfile':  [False, True],
                'isHotSector': [False, True],
                'hasPromotion': [False, True],
                'transferAgentVerified': [False, True],

                'isShellRisk': [True, False],
                'isDelinquent': [True, False],
                'isDark': [True, False],
                'isCaveatEmptor': [True, False],
                'unableToContact': [True, False],
                'isBankrupt': [True, False],
                'hasControlDispute': [True, False]}

    def get_sorted_history(self, apply_filters=True):
        history = super().get_sorted_history(apply_filters)

        if apply_filters and not history.empty:
            if 'verifiedDate' in history:
                history["verifiedDate"] = history["verifiedDate"].dropna().apply(
                    self.timestamp_to_datestring)

        return history
