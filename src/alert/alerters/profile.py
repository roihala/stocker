import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors
from src.read import readers

logger = logging.getLogger('Alert')


class Profile(AlerterBase):
    # TODO: MAYBE more keys
    OTCIQ_KEYS = ['businessDesc', 'officers', 'directors', 'website', 'email', 'phone', 'city']
    ADDRESS_LINES = [['address1', 'address2'], ['city',  'state'], ['country']]

    @property
    def filter_keys(self):
        return ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard', 'latestFilingType',
                'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName', 'venue',
                'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered', 'isAlternativeReporting',
                'indexStatuses', 'otcAward', 'otherSecurities', 'corporateBrokers', 'notes', 'reportingStandardMin',
                'auditStatus', 'auditedStatusDisplay']

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)

        if not diff:
            return diff

        if diff.get('changed_key') in self.OTCIQ_KEYS:
            diff = self.update_otciq(self._mongo_db, diff)

        if diff.get('changed_key') in [key for line in self.ADDRESS_LINES for key in line]:
            records = readers.Profile(mongo_db=self._mongo_db, ticker=diff.get('ticker')).get_sorted_history().tail(2)
            diff['old'], diff['new'] = self.format_address(records.iloc[0]), self.format_address(records.iloc[1]) 
                                                       
            diff['changed_key'] = "address"

        return diff

    @staticmethod
    def update_otciq(mongo_db, diff):
        """
        Updating diff with otciq payload if detected first otciq account approach
        """

        profile = readers.Profile(mongo_db=mongo_db, ticker=diff.get('ticker'))
        symbols = readers.Symbols(mongo_db=mongo_db, ticker=diff.get('ticker'))

        if len(profile.get_sorted_history(filter_rows=True, ignore_latest=True).index) == 1 and \
                len(symbols.get_sorted_history(filter_rows=True, ignore_latest=True).index) == 1:
            diff['diff_appendix'] = 'otciq'

        return diff

    def format_address(self, record):
        """
        Generates pretty address string
        """
        address_lines = []
        for line in self.ADDRESS_LINES:
            address_lines.append(', '.join(record.get(key) for key in line if record.get(key)))
        return '\n'.join(address_lines)
