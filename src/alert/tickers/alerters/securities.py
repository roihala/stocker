from src.alert.tickers.ticker_alerter import TickerAlerter


class Securities(TickerAlerter):
    # A list of keys that allowed to be alerted
    WHITE_LIST = ['tierDisplayName']

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
    def get_hierarchy() -> dict:
        return {
            'tierDisplayName': ['Grey Market', 'Expert Market', 'Pink No Information', 'Pink Limited Information', 'Pink Current Information', 'OTCQB',
                                'OTCQX International']}

    def _edit_diff(self, diff):
        if diff.get('changed_key') in self.WHITE_LIST:
            return super()._edit_diff(diff)
        else:
            return None
        # TODO: After adding DailyAlert
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'].startswith('showTrustedLogo'):
            return None

        return diff
