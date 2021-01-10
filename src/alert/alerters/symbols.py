from src.alert.alerter_base import AlerterBase


class Symbols(AlerterBase):
    @property
    def filter_keys(self):
        return ['isPennyStockExempt', 'verifiedDate']

    @property
    def hierarchy(self):
        return {'verifiedProfile':  [False, True],
                'isHotSector': [False, True],
                'hasPromotion': [False, True],
                'transferAgentVerified': [False, True],

                'isShellRisk': [True, False],
                'isDelinquent': [True, False],
                'isDark': [True, False],
                'isCaveatEmptor': [True, False],
                'unableToContact': [True, False],
                'isBankrupt': [True, False],
                'hasControlDispute': [True, False]}
