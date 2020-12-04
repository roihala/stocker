from src.collect.site_collector import SiteCollector
from src.find.site import Site, InvalidTickerExcpetion


class Securities(SiteCollector):
    @property
    def filter_keys(self):
        return ['outstandingSharesAsOfDate', 'authorizedSharesAsOfDate', 'dtcSharesAsOfDate',
                'restrictedSharesAsOfDate', 'unrestrictedSharesAsOfDate',
                'dtcShares', 'tierStartDate', 'tierId', 'numOfRecordShareholdersDate', 'tierName', 'categoryName',
                'categoryId', 'tierCode', 'shortInterest', 'shortInterestDate', 'shortInterestChange',
                'publicFloatAsOfDate', 'isNoInfo', 'currentCapitalChangePayDate',
                'currentCapitalChangeExDate', 'currentCapitalChange', 'currentCapitalChangeRecordDate', 'cusip',
                'hasLevel2', 'isLevel2Entitled', 'primaryVenue', 'tierGroupId', 'isPiggyBacked',
                'notes', 'otcAward', 'showTrustedLogo', 'isUnsolicited', 'statusName']

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @property
    def hierarchy(self):
        return {'transferAgents': [list, dict, 'name']}

    def fetch_data(self):
        try:
            data = super().fetch_data()
            return data['securities'][0]
        except KeyError:
            raise InvalidTickerExcpetion("Can't get the securities sector from the profile")

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'].startswith('showTrustedLogo'):
            return None

        return diff
