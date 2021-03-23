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
