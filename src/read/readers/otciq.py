from src import alerters_factory
from src.alert.alerter_base import AlerterBase
from src.read.readers import Symbols


class Otciq(Symbols):
    OTCIQ_KEY = 'hasIqAccount'

    def generate_info(self):
        is_otciq = self.get_latest().get(self.OTCIQ_KEY)

        if is_otciq:
            red_or_green = AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE
        else:
            red_or_green = AlerterBase.RED_CIRCLE_EMOJI_UNICODE

        key = alerters_factory.AlertersFactory.get_alerter(self.name).get_keys_translation().get(self.OTCIQ_KEY)

        return f'{red_or_green} {key}'
