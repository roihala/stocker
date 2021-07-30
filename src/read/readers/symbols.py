import arrow

from src.alert.alerter_base import AlerterBase
from src import alerters_factory
from src.read.reader_base import ReaderBase


class Symbols(ReaderBase):
    def get_sorted_history(self, filter_rows=False, filter_cols=False, ignore_latest=False):
        history = super().get_sorted_history(filter_rows, filter_cols, ignore_latest)

        # If all of the filters are applied
        if filter_rows and filter_cols and not history.empty:
            if 'verifiedDate' in history:
                history["verifiedDate"] = history["verifiedDate"].apply(
                    self.timestamp_to_datestring)

        return history

    def generate_info(self):
        # For every true symbol
        true_symbols = [symbol for symbol, value in self.get_latest().items() if value is True]

        return '\n'.join(sorted([self.generate_line(symbol) for symbol in true_symbols], reverse=True))

    def generate_line(self, symbol):
        try:
            hierarchy = alerters_factory.AlertersFactory.get_alerter(self.name).get_hierarchy().get(symbol)
            if hierarchy.index(False) < hierarchy.index(True):
                red_or_green = AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE
            else:
                red_or_green = AlerterBase.RED_CIRCLE_EMOJI_UNICODE

            return f'{red_or_green} {symbol} {"[" + arrow.get(self.get_latest().get("verifiedDate")).format("MM/YY") + "]" if symbol == "verifiedProfile" else ""}'
        except ValueError:
            return symbol
