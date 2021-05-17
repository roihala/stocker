from src.alert.tickers.ticker_alerter import TickerAlerter


class Securities(TickerAlerter):
    # A list of keys that allowed to be alerted
    WHITE_LIST = ['tierDisplayName']

    @property
    def keys_translation(self):
        return {"tierDisplayName": "Tier",
                "authorizedShares": "Authorized Shares",
                "outstandingShares": "Outstanding Shares",
                "transferAgents": "Transfer Agents",
                "restrictedShares": "Restricted Shares",
                "unrestrictedShares": "Unrestricted Shares"}

    @property
    def relevant_keys(self):
        return ['tierDisplayName']

    @property
    def extended_keys(self):
        return ['authorizedShares', 'outstandingShares', 'transferAgents', 'restrictedShares', 'unrestrictedShares']

    @staticmethod
    def get_hierarchy() -> dict:
        return {
            'tierDisplayName': ['Grey Market', 'Expert Market', 'Pink No Information', 'Pink Limited Information', 'Pink Current Information', 'OTCQB',
                                'OTCQX International']}

    def is_relevant_diff(self, diff):
        if diff.get('changed_key') in self.extended_keys and type(diff.get('new')) is int:
            if self.calc_ratio(diff) < -0.2:
                return True
        return super().is_relevant_diff(diff)

    def edit_diff(self, diff):
        old, new = diff['old'], diff['new']

        diff = super().edit_diff(diff)

        if type(new) == type(old) and type(new) is int:
            ratio = self.calc_ratio(diff)
            old, new = f'{old:,}', f'{new:,}'

            if diff.get('changed_key') in self.extended_keys:
                new += " ({:.0%})".format(ratio)

        diff['old'], diff['new'] = old, new

        return diff

    @staticmethod
    def calc_ratio(diff):
        return (diff.get('new') - diff.get('old')) / diff.get('old')
