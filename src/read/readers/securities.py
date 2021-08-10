from src.read.reader_base import ReaderBase


class Securities(ReaderBase):

    INTERESTING_KEYS = ['authorizedShares', 'outstandingShares', 'restrictedShares', 'unrestrictedShares']
    DILUTION_KEYS = ['authorizedShares', 'outstandingShares', 'unrestrictedShares']

    @staticmethod
    def get_nested_keys():
        return {'transferAgents': [list, dict, 'name'],
                'notes': [list]}

    def generate_info(self):
        return '\n'.join(['{key}: {value:,}'.format(key=key, value=self.get_latest().get(key)) for key in self.INTERESTING_KEYS if self.get_latest().get(key)])
