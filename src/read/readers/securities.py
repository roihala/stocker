from src.read.reader_base import ReaderBase


class Securities(ReaderBase):

    INTERESTING_KEYS = ['authorizedShares', 'outstandingShares', 'restrictedShares', 'unrestrictedShares']
    DILUTION_KEYS = ['authorizedShares', 'outstandingShares', 'unrestrictedShares']

    def generate_msg(self):
        return '\n'.join(['{key}: {value:,}'.format(key=key, value=self.get_latest().get(key)) for key in self.INTERESTING_KEYS if self.get_latest().get(key)])
