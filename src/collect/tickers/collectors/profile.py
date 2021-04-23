from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @staticmethod
    def get_sons():
        return ['securities']

    @staticmethod
    def get_nested_keys():
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
                'otcAward': [dict, 'best50'],
                "indexStatuses": [list, dict, 'indexName'],
                }

    @staticmethod
    def get_drop_keys():
        return ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate',
                'estimatedMarketCapAsOfDate', 'estimatedMarketCap']

    def _check_diff(self, diff):
        elif diff.get('changed_key') == "phone":
            return not _compare_phones(diff.get('old'), diff.get('new'))

    def _compare_phones(self, phone1, phone2):
        def parse_phone(phone, region="US"):
            try:
                return phonenumbers.parse(phone)
            except phonenumbers.NumberParseException:
                return phonenumbers.parse(phone, region)
        return parse_phone(phone1) == parse_phone(phone2)

    def fetch_data(self, data=None):
        data = super().fetch_data()
        # Those keys are either irrelevant or used in other collectors
        [data.pop(key, None) for key in self.get_drop_keys()]
        return data
