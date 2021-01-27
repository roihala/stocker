from geventwebsocket import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors

logger = logging.getLogger('Alert')


class Profile(AlerterBase):
    # TODO: MAYBE more keys
    OTCIQ_KEYS = ['businessDesc', 'officers', 'directors', 'website', 'email', 'phone', 'city']

    @property
    def filter_keys(self):
        return ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard', 'latestFilingType',
                'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName', 'venue',
                'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered', 'isAlternativeReporting',
                'indexStatuses', 'otcAward', 'otherSecurities', 'corporateBrokers', 'notes', 'reportingStandardMin',
                'auditStatus', 'auditedStatusDisplay']

    @property
    def hierarchy(self):
        return {
            'tierDisplayName': ['Pink No Information', 'Pink Limited Information', 'Pink Current Information', 'OTCQB',
                                'OTCQX International']}

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)

        if diff and diff.get('changed_key') in self.OTCIQ_KEYS:
            diff = self.update_otciq(self._mongo_db, diff)

        return diff

    @staticmethod
    def update_otciq(mongo_db, diff):
        """
        Updating diff with otciq payload if detected first otciq account approach
        """

        profile = collectors.Profile(mongo_db=mongo_db, ticker=diff.get('ticker'))
        symbols = collectors.Symbols(mongo_db=mongo_db, ticker=diff.get('ticker'))

        if len(profile.get_sorted_history(filter_rows=True, ignore_latest=True).index) == 1 and \
                len(symbols.get_sorted_history(filter_rows=True, ignore_latest=True).index) == 1:
            diff['diff_appendix'] = 'otciq'

        return diff
