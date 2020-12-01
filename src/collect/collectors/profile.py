from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    DROP_KEYS = ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                 'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate']
    FILTER_KEYS = ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                   'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                   'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard', 'latestFilingType',
                   'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName', 'venue',
                   'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered', 'isAlternativeReporting']

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

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'] in self.FILTER_KEYS:
            return None

        return diff

    def get_sorted_history(self, apply_filters=True):
        history = super().get_sorted_history(apply_filters)
        for key in self.DROP_KEYS:
            if key in history:
                history = history.drop(key, axis='columns')

        return history