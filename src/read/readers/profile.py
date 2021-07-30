from src.read.reader_base import ReaderBase
from src.alert.tickers import alerters


class Profile(ReaderBase):
    PIN_EMOJI_UNICODE = u'\U0001F4CD'
    INTERESTING_KEYS = ['website', 'phone', 'email', 'facebook', 'linkedin', 'twitter', 'businessDesc']

    @staticmethod
    def get_nested_keys():
        return {'officers': [list, dict, 'name'],
                'premierDirectorList': [list, dict, 'name'],
                'standardDirectorList': [list, dict, 'name'],
                'auditors': [list, dict, 'name'],
                'investorRelationFirms': [list, dict, 'name'],
                'legalCounsels': [list, dict, 'name'],
                'investmentBanks': [list, dict, 'name'],
                'corporateBrokers': [list, dict, 'name'],
                'notes': [list],
                'otherSecurities': [list, dict, 'name'],
                'otcAward': [dict, 'best50'],
                "indexStatuses": [list, dict, 'indexName'],
                }

    @staticmethod
    def get_drop_keys():
        return ['securities', 'isProfileVerified', 'isCaveatEmptor', 'isShell', 'isBankrupt', 'unableToContact',
                'isDark', 'numberOfRecordShareholders', 'profileVerifiedAsOfDate', 'tierCode', 'tierStartDate',
                'estimatedMarketCapAsOfDate', 'estimatedMarketCap']

    def generate_info(self, exclude=None, escape_markdown=False):
        """
        :param escape_markdown:
        :param exclude: List of keys to exclude
        """
        features = [alerters.Profile.format_address(self.get_latest(), is_paddding=True)] + \
                   [value for key, value in self.get_latest().items() if key in set(self.INTERESTING_KEYS).difference(set(exclude))]
        msg = f'{self.PIN_EMOJI_UNICODE} ' + f'\n{self.PIN_EMOJI_UNICODE} '.join(features)

        return self.escape_markdown(msg) if escape_markdown else msg
