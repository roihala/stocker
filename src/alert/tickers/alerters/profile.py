import difflib
import logging
import phonenumbers
from copy import deepcopy

from src.alert.tickers.ticker_alerter import TickerAlerter
from src.read import readers

logger = logging.getLogger('Alert')


class Profile(TickerAlerter):
    # TODO: MAYBE more keys
    OTCIQ_KEYS = ['businessDesc', 'officers', 'directors', 'website', 'email', 'phone', 'city']
    ADDRESS_LINES = [['address1', 'address2', 'address3'], ['city', 'state'], ['country']]
    EXTRA_DATA = ['officers']

    @property
    def filter_keys(self):
        return ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard', 'latestFilingType',
                'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName', 'venue',
                'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered', 'isAlternativeReporting',
                'indexStatuses', 'otcAward', 'otherSecurities', 'corporateBrokers', 'notes', 'reportingStandardMin',
                'auditStatus', 'auditedStatusDisplay', 'countryOfIncorporation', 'countryOfIncorporationName',
                'audited', 'bankId', 'blankCheck', 'blindPool', 'cik', 'companyLogoUrl', 'deregistrationDate',
                'filingCycle', 'fiscalYearEnd', 'hasLogo', 'id', 'investmentBanks', 'investorRelationFirms',
                'is12g32b', 'isBankThrift', 'isInternationalReporting', 'isNonBankRegulated', 'isOtherReporting',
                'regulatoryAgencyId', 'regulatoryAgencyName', 'traderRssdId', 'yearOfIncorporation']

    def _is_valid_diff(self, diff):
        if diff.get('changed_key') == "buisnessDesc":
            return self.__compare_description(diff.get('old'), diff.get('new'))
        elif diff.get('changed_key') == "phone":
            return self.__compare_phones(diff.get('old'), diff.get('new'))
        else:
            return super()._is_valid_diff(diff)

    @staticmethod
    def __compare_description(old, new):
        '''
        Returning False for changes of only non-ascii characters
        '''
        for i in difflib.ndiff(old, new):
            # ndiff encodes every diff by adding +, - or whitespace to the character, separated by whitespace
            # e.g: "- Ã", "+ w"
            if i[0] in ['+', '-'] and i[2].isascii():
                    return True
        return True

    @staticmethod
    def __compare_phones(old, new):
        def parse_phone(phone, region="US"):
            try:
                return phonenumbers.parse(phone)
            except phonenumbers.NumberParseException:
                return phonenumbers.parse(phone, region)
        return parse_phone(old) == parse_phone(new)

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)

        if not diff:
            return diff

        if diff.get('changed_key') in self.ADDRESS_LINES:
            return None

        if diff.get('changed_key') in self.OTCIQ_KEYS:
            diff = self.update_otciq(self._mongo_db, diff)

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

    def generate_msg(self, diff, *args, **kwargs):
        return super().generate_msg(diff, new=self.__get_extra_data(diff))

    def __get_extra_data(self, diff):
        profile = readers.Profile(mongo_db=self._mongo_db, ticker=diff.get('ticker'))

        extra_data_field = diff.get('new')
        try:
            field = next((field for field in self.EXTRA_DATA if field == diff.get('changed_key')), None)
            if field:
                frac_key = field.split('.')
                for key, val in [(key, val) for data_dict in profile.get_latest()[frac_key[0]] if data_dict["name"] == diff.get("new") \
                                            for (key, val) in data_dict.items()]:
                    if val and key != "name":
                        extra_data_field += f"\n{key}: {val}"
            return extra_data_field
        except (StopIteration, KeyError) as e:
            logger.warning(f"Couldn't get extra data for field {diff.get('changed_key')}, not found.")
            logger.exception(e)

    def _edit_batch(self, diffs):
        diffs = super()._edit_batch(diffs)
        return self.squash_addresses(diffs)

    def squash_addresses(self, diffs):
        try:
            # If any address diffs
            to_squash = [diff for diff in diffs if diff.get('changed_key') in [field for line in self.ADDRESS_LINES for field in line]]

            if any(to_squash):
                # TODO: pull the exact diff by date
                old, new = self._reader.get_sorted_history().tail(2).to_dict('records')

                return [diff for diff in diffs if diff not in to_squash] + [self.generate_squashed_diff(to_squash[0], old, new)]

        except Exception as e:
            logger.warning("Couldn't squash diffs: {diffs}".format(diffs=diffs))
            logger.exception(e)

        return diffs

    @staticmethod
    def format_address(record, is_paddding=False):
        """
        Generates pretty address string
        """
        address_lines = []
        for line in Profile.ADDRESS_LINES:
            address_lines.append(', '.join(str(record.get(key)) for key in line if record.get(key)))

        if is_paddding:
            # Visual padding
            return '\n\t\t\t\t\t\t\t\t\t'.join(address_lines)
        else:
            return '\n'.join(address_lines)

    def generate_squashed_diff(self, origin, old, new):
        squashed = deepcopy(origin)
        squashed['old'] = self.format_address(old)
        squashed['new'] = self.format_address(new)
        squashed['changed_key'] = 'address'

        return squashed
