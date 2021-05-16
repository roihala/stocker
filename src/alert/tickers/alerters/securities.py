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
