from src.collect.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    DROP_KEYS = ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                 'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate']

    @property
    def filter_keys(self):
        return ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard', 'latestFilingType',
                'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName', 'venue',
                'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered', 'isAlternativeReporting',
                'indexStatuses', 'otcAward', 'otherSecurities', 'corporateBrokers', 'notes']

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @property
    def hierarchy(self):
        return {'tierDisplayName': ['Pink No Information', 'Pink Limited Information', 'Pink Current Information', 'OTCQB', 'OTCQX International']}

    @property
    def nested_keys(self):
        return {'officers': [list, dict, 'name'],
                'premierDirectorList': [list, dict, 'name'],
                'standardDirectorList': [list, dict, 'name'],
                'auditors': [list, dict, 'name'],
                'investorRelationFirms': [list, dict, 'name'],
                'legalCounsels': [list, dict, 'name'],
                'investmentBanks': [list, dict, 'name'],
                'corporateBrokers': [list, dict, 'name'],
                'notes': [list],
                'otherSecurities': [list, dict, 'name'],
                'otcAward': [list, dict, 'best50']
                }

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
