from src.alert.tickers.ticker_alerter import TickerAlerter


class Otciq(TickerAlerter):
    @staticmethod
    def get_keys_translation():
        return {'hasIqAccount': 'Otciq access'}

    @property
    def relevant_keys(self):
        return ['hasIqAccount']

    @staticmethod
    def get_hierarchy() -> dict:
        return {'hasIqAccount': [False, True]}
