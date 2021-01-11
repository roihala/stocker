from src.alert.daily_alerter import DailyAlerter


class Securities(DailyAlerter):
    @property
    def filter_keys(self):
        return ['outstandingSharesAsOfDate', 'authorizedSharesAsOfDate', 'dtcSharesAsOfDate',
                'restrictedSharesAsOfDate', 'unrestrictedSharesAsOfDate',
                'dtcShares', 'tierStartDate', 'tierId', 'numOfRecordShareholdersDate', 'tierName', 'categoryName',
                'categoryId', 'tierCode', 'shortInterest', 'shortInterestDate', 'shortInterestChange',
                'publicFloatAsOfDate', 'isNoInfo', 'currentCapitalChangePayDate',
                'currentCapitalChangeExDate', 'currentCapitalChange', 'currentCapitalChangeRecordDate', 'cusip',
                'hasLevel2', 'isLevel2Entitled', 'primaryVenue', 'tierGroupId', 'isPiggyBacked',
                'notes', 'otcAward', 'showTrustedLogo', 'isUnsolicited', 'statusName', 'foreignExchangeTier',
                'foreignExchangeName', 'isOtcQX', 'foreignExchangeId']

    @staticmethod
    def get_nested_keys():
        return {'transferAgents': [list, dict, 'name'],
                'notes': [list]}

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'].startswith('showTrustedLogo'):
            return None

        return diff
