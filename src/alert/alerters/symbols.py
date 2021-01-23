from src.alert.alerter_base import AlerterBase
from src.alert.alerters import Profile


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

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)

        if diff and diff.get('changed_key') in Profile.OTCIQ_KEYS:

            diff = Profile.update_otciq(self._mongo_db, diff)

        return diff
