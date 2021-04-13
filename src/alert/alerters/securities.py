from src.alert.alerter_base import AlerterBase


class Securities(AlerterBase):
    # A list of keys that allowed to be alerted
    WHITE_LIST = ['tierDisplayName', 'outstandingShares', 'authorizedShares']
    MAJOR_CHANGE_ALERT = ['outstandingShares', 'authorizedShares']

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

    @property
    def hierarchy(self):
        return {
            'tierDisplayName': ['Expert Market', 'Pink No Information', 'Pink Limited Information', 'Pink Current Information', 'OTCQB',
                                'OTCQX International']}

    def _edit_diff(self, diff):
        if diff.get('changed_key') in self.WHITE_LIST:
            diff = super()._edit_diff(diff)

            if not diff:
                return diff

            for key in self.MAJOR_CHANGE_ALERT:
                if diff.get('changed_key') == key:
                    osas_change = self._get_osas_change(diff)
                    diff["old"] = "{:,}".format(diff["old"])
                    diff["new"] = "{:,}".format(diff["new"])
                    if abs(osas_change) > 0.1:
                        diff["new"] += " ({:.0%})".format(osas_change)
            return diff
        else:
            return None
        # TODO: After adding DailyAlert
        diff = super()._edit_diff(diff)
        if not diff:
            return diff

        if diff['changed_key'].startswith('showTrustedLogo'):
            return None
            
        return diff

    def _get_osas_change(self, diff):
        """
        Calculates precentage change between old to new
        """
        return (diff.get('new') - diff.get('old')) / diff.get('old')

