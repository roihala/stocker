from src.read.reader_base import ReaderBase
from src.alert.tickers import alerters


class Profile(ReaderBase):
    PIN_EMOJI_UNICODE = u'\U0001F4CD'
    INTERESTING_KEYS = ['website', 'phone', 'email', 'facebook', 'linkedin', 'twitter', 'businessDesc']

    def generate_msg(self, exclude=None, escape_markdown=False):
        """
        :param escape_markdown:
        :param exclude: List of keys to exclude
        """
        features = [alerters.Profile.format_address(self.get_latest(), is_paddding=True)] + \
                   [value for key, value in self.get_latest().items() if key in set(self.INTERESTING_KEYS).difference(set(exclude))]
        msg = f'{self.PIN_EMOJI_UNICODE} ' + f'\n{self.PIN_EMOJI_UNICODE} '.join(features)

        return self.escape_markdown(msg) if escape_markdown else msg
