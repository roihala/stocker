import difflib
import logging
import re

import pandas as pd

import phonenumbers
from copy import deepcopy

import validators

from src.alert.tickers.ticker_alerter import TickerAlerter
from src.read import readers
from src.read.reader_base import ReaderBase

logger = logging.getLogger('Alert')


class Profile(TickerAlerter):
    # TODO: MAYBE more keys
    ADDRESS_LINES = [['address1', 'address2', 'address3'], ['city', 'state'], ['country', 'zip']]
    EXTRA_DATA = ['officers']

    @staticmethod
    def get_keys_translation():
        return {
            "businessDesc": "Business Description",
            "numberOfEmployees": "Employees Count",
            "primarySicCode": "Sic Code",
            "officers": "Officer",
            "auditors": "Auditor",
            "standardDirectorList": "Director",
            "premierDirectorList": "Director",

            "is12g32b": "12g3-2(b) rule compliant",
            "corporateBrokers":  "Corporate Brokers",
            "countryOfIncorporationName": "Country of Incorporation",
            "investmentBanks": "Investment Banks",
            "investorRelationFirms": "Investor Relation Firms",
            "isBankThrift": "Bank Thrift",
            "legalCounsels": "Legal Counsels",
            "regulatoryAgencyName": "Regulatory Agency",
            "stateOfIncorporationName": "State of Incorporation",
            "yearOfIncorporation": "Year of Incorporation"
        }

    @property
    def relevant_keys(self):
        return ['address', 'address1', 'address2', 'address3', 'auditors', 'businessDesc', 'city', 'country', 'email',
                'facebook', 'fax', 'linkedin', 'name', 'numberOfEmployees', 'officers', 'phone', 'premierDirectorList',
                'primarySicCode', 'standardDirectorList', 'state', 'twitter', 'website', 'zip']

    @property
    def extended_keys(self):
        return ['audited', 'corporateBrokers', 'countryOfIncorporationName', 'deregistered', 'investmentBanks',
                'investorRelationFirms', 'is12g32b', 'isBankThrift', 'legalCounsels', 'regulatoryAgencyName', 'spac',
                'stateOfIncorporationName', 'yearOfIncorporation']

    def _is_valid_diff(self, diff):
        old, new = diff.get('old'), diff.get('new')

        if diff.get('changed_key') == "businessDesc":
            return self.__compare_description(old, new)
        elif diff.get('changed_key') == "phone":
            return self.__parse_phone(old) != self.__parse_phone(new)
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
        return False

    @staticmethod
    def __parse_phone(phone, region="US"):
        try:
            return phonenumbers.parse(phone)
        except phonenumbers.NumberParseException:
            return phonenumbers.parse(phone, region)

    def edit_diff(self, diff):
        diff = super().edit_diff(diff)

        if diff.get('changed_key') == 'phone':
            diff['old'] = phonenumbers.format_number(self.__parse_phone(diff['old']), phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            diff['new'] = phonenumbers.format_number(self.__parse_phone(diff['new']), phonenumbers.PhoneNumberFormat.INTERNATIONAL)

        if diff.get('changed_key') in self.EXTRA_DATA:
            diff['new'] = self.__get_extra_data(diff)

        try:
            diff['new'] = ReaderBase.escape_markdown(diff['new']) if validators.url(diff['new']) else diff['new']
            diff['old'] = ReaderBase.escape_markdown(diff['old']) if validators.url(diff['old']) else diff['old']
        except TypeError:
            pass

        self.__check_sympathy(diff)

        return diff

    def __check_sympathy(self, diff):
        """
        Currently check only new people that exist also in other companies
        """
        if diff.get('changed_key') not in ['officers', 'directors', 'auditors', 'premierDirectorList',
                                           'standardDirectorList']:
            return
        if diff.get('diff_type') == 'remove':
            return
        value = re.compile('^' + re.escape(diff['new']) + '$', re.IGNORECASE)
        df = pd.DataFrame(self._mongo_db.profile.find({f'{diff.get("changed_key")}.name': {value}}))
        tickers = list(df['ticker'].unique())
        if len(tickers) > 0:
            diff['insight'] = 'sympathy'
            diff['insight_fields'] = tickers

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
                date = set([diff.get('date') for diff in diffs])
                if len(date) != 1:
                    raise AttributeError("Address diffs from different dates, falling back")

                date = date.pop()
                old, new = self._reader.get_entry_by_date(date)

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
