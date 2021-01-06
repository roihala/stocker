from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    DROP_KEYS = ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                 'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate']
    
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    def fetch_data(self):
        data = super().fetch_data()
        # Those keys are either irrelevant or used in other collectors
        [data.pop(key, None) for key in self.DROP_KEYS]
        return data

    def get_sorted_history(self, apply_filters=True):
        history = super().get_sorted_history(apply_filters)
        for key in self.DROP_KEYS:
            if key in history:
                history = history.drop(key, axis='columns')

        return history
