from copy import deepcopy

from src.alert.tickers.alerters import Profile
from src.alert.tickers.ticker_alerter import TickerAlerter


class Symbols(TickerAlerter):
    @property
    def keys_translation(self):
        return {
            "hasControlDispute": "Control Dispute",
            "hasPromotion": "Promotion",
            "isBankrupt": "Bankrupt",
            "isCaveatEmptor": "Caveat Emptor",
            "isDark": "Dark of Defunct",
            "isDelinquent": "Delinquent SEC Reporting",
            "isLinkedToProhibitedSP": "Prohibited Service Provider",
            "isPennyStockExempt": "Penny Stock Exempt",
            "isShell": "Shell",
            "isShellRisk": "Shell Risk",
            "transferAgentVerified": "Transfer Agent Verified",
            "unableToContact": "Unable to Contact",
            "verifiedProfile": "Verified Profile"
        }

    @property
    def relevant_keys(self):
        return ['hasControlDispute', 'isBankrupt', 'isCaveatEmptor', 'isDark', 'isDelinquent', 'isLinkedToProhibitedSP',
                'isPennyStockExempt', 'isShell', 'isShellRisk', 'transferAgentVerified', 'unableToContact',
                'verifiedProfile']

    @property
    def extended_keys(self):
        return ['isHotSector', 'hasPromotion']

    @staticmethod
    def get_hierarchy() -> dict:
        return {'verifiedProfile': [False, True],
                'isHotSector': [False, True],
                'hasPromotion': [False, True],
                'transferAgentVerified': [False, True],

                'isShell': [True, False],
                'isShellRisk': [True, False],
                'isDelinquent': [True, False],
                'isDark': [True, False],
                'isCaveatEmptor': [True, False],
                'unableToContact': [True, False],
                'isBankrupt': [True, False],
                'hasControlDispute': [True, False],
                'isLinkedToProhibitedSP': [True, False]}
