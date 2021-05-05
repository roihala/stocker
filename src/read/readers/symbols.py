from src.alert.alerter_base import AlerterBase
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

    def generate_msg(self):
        latest = self.get_latest()

        # For every true symbol
        true_symbols = [symbol for symbol, value in latest.items() if value is True]
        return '\n'.join(sorted([self.red_or_green(symbol) + ' ' + symbol for symbol in true_symbols], reverse=True))

    def red_or_green(self, symbol):
        try:
            hierarchy = self._alerter.get_hierarchy().get(symbol)
            if hierarchy.index(False) < hierarchy.index(True):
                return AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE
            else:
                return AlerterBase.RED_CIRCLE_EMOJI_UNICODE
        except Exception:
            return ''
