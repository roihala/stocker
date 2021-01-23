from src.alert.alerter_base import AlerterBase


class Securities(AlerterBase):
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

    def _edit_diff(self, diff):
        return None
        # TODO: After adding DailyAlert
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'].startswith('showTrustedLogo'):
            return None

        return diff
