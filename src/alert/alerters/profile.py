from geventwebsocket import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors

logger = logging.getLogger('Alert')


class Profile(AlerterBase):
    # TODO: MAYBE more keys
    OTCIQ_KEYS = ['businessDesc', 'officers', 'directors', 'website', 'email', 'phone']

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
    def update_otciq(mongo_db,  diff):
        """
        Updating diff with otciq payload if detected first otciq account approach
        """

        profile = collectors.Profile(mongo_db=mongo_db, ticker=diff.get('ticker'))
        symbols = collectors.Symbols(mongo_db=mongo_db, ticker=diff.get('ticker'))

        logger.info(profile.get_sorted_history(filter_cols=True, ignore_latest=True).columns)
        logger.info(symbols.get_sorted_history(filter_cols=True, ignore_latest=True).columns)

        # Getting a set of the ONLY columns that contain changes.
        columns = set(list(profile.get_sorted_history(filter_cols=True, ignore_latest=True).columns) +
                      list(symbols.get_sorted_history(filter_cols=True, ignore_latest=True).columns))

        # If there aren't any OTCIQ keys in filtered history columns
        if not set(Profile.OTCIQ_KEYS).intersection(columns):
            diff['diff_appendix'] = 'otciq'

        return diff
