from src.read.reader_base import ReaderBase
from src.alert.tickers import alerters


class Profile(ReaderBase):
    PIN_EMOJI_UNICODE = u'\U0001F4CD'
    INTERESTING_KEYS = ['website', 'phone', 'email', 'facebook', 'linkedin', 'twitter', 'businessDesc']

    def generate_msg(self):
        latest = self.get_latest(clear_nans=True)

        features = [alerters.Profile.format_address(latest, is_paddding=True)] + \
                   [value for key, value in latest.items() if key in self.INTERESTING_KEYS]

        return f'{self.PIN_EMOJI_UNICODE} ' + f'\n{self.PIN_EMOJI_UNICODE} '.join(features)
