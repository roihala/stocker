from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @property
    def drop_keys(self):
        return ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate',
                'estimatedMarketCapAsOfDate', 'estimatedMarketCap']

    def fetch_data(self):
        data = super().fetch_data()
        # Those keys are either irrelevant or used in other collectors
        [data.pop(key, None) for key in self.drop_keys]
        return data
