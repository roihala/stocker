from copy import deepcopy

from src.alert.alerter_base import AlerterBase
from src.alert.alerters import Profile


class Symbols(AlerterBase):
    @property
    def filter_keys(self):
        return ['isPennyStockExempt', 'verifiedDate']

    @property
    def hierarchy(self):
        return {'verifiedProfile': [False, True],
                'isHotSector': [False, True],
                'hasPromotion': [False, True],
                'transferAgentVerified': [False, True],

                'isShellRisk': [True, False],
                'isDelinquent': [True, False],
                'isDark': [True, False],
                'isCaveatEmptor': [True, False],
                'unableToContact': [True, False],
                'isBankrupt': [True, False],
                'hasControlDispute': [True, False],
                'isLinkedToProhibitedSP': [True, False]}

    @property
    def humanized_keys() -> dict:
        return {
            "verifiedProfile": "Verified Profile",
            "isDark": "Dark or Defunct"
        }

    def generate_msg(self, diff):
        original_diff = deepcopy(diff)
        diff = self._edit_diff(diff)

        if not diff:
            return ''

        msg = None

        if diff.get('diff_type') == 'change':
            if diff.get('old') is False:
                msg = '{green_circle_emoji}{key} added'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                               key=diff.get('changed_key'))
            elif diff.get('old') is True:
                msg = '{red_circle_emoji}{key} removed'.format(red_circle_emoji=self.RED_CIRCLE_EMOJI_UNICODE,
                                                               key=diff.get('changed_key'))

        # If managed to generate boolean-type alert message
        if msg:
            return msg
        else:
            # Falling back to regular format
            super().get_alert_msg(original_diff)

    def _edit_diff(self, diff):
        diff = super()._edit_diff(diff)

        if diff and diff.get('changed_key') in Profile.OTCIQ_KEYS:
            diff = Profile.update_otciq(self._mongo_db, diff)

        return diff
