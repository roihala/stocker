import logging

from src.alert.tickers.ticker_alerter import TickerAlerter
from src.read import readers

logger = logging.getLogger('Alert')


class Profile(TickerAlerter):
    # TODO: MAYBE more keys
    OTCIQ_KEYS = ['businessDesc', 'officers', 'directors', 'website', 'email', 'phone', 'city']
    ADDRESS_KEYS = ['address1', 'address2', 'city', 'state', 'country']
    EXTRA_DATA = ['officers']

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

        if diff.get('changed_key') in self.ADDRESS_KEYS:
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
        if any([diff for diff in diffs if diff.get('changed_key') in self.ADDRESS_KEYS]):
            logger.info(self._reader.get_sorted_history().tail(2))
            raise Exception('kaki')
            # old, new = self._reader.get_sorted_history().tail(2).to_json('records')
        else:
            return diffs
        asdf


        address_diffs = [diff for diff in diffs if diff.get('changed_key') in self.ADDRESS_KEYS]

        # if address_diffs:

        adsf




        address_exists = False
        united_diff = None
        squashed_diffs = diffs[:]

        for diff in diffs:
            if diff.get("changed_key") in [field for line in self.ADDRESS_KEYS for field in line]:
                united_diff = diff
                squashed_diffs.remove(diff)
                address_exists = True

        if address_exists:
            records = readers.Profile(mongo_db=self._mongo_db, ticker=united_diff.get('ticker')).get_sorted_history().tail(2)
            try:
                united_diff['old'], united_diff['new'] = self.format_address(records.iloc[0]), self.format_address(records.iloc[1])
            except IndexError:
                united_diff['new'] = self.format_address(records.iloc[0])
            united_diff["changed_key"] = "address"
            squashed_diffs.append(united_diff)
        return squashed_diffs

    def format_address(self, record):
        """
        Generates pretty address string
        """
        address_lines = []
        for line in self.ADDRESS_KEYS:
            address_lines.append(', '.join(record.get(key) for key in line if record.get(key)))
        return '\n'.join(address_lines)
