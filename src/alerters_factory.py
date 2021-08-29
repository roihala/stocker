from src.base_factory import BaseFactory
from src.alert.tickers import alerters as ticker_alerters
from src.alert.records import alerters as records_alerters


class AlertersFactory(BaseFactory):
    COLLECTIONS = {
        'profile': ticker_alerters.Profile,
        'securities': ticker_alerters.Securities,
        'symbols': ticker_alerters.Symbols,
        'otciq': ticker_alerters.Otciq,

        'filings_backend': records_alerters.FilingsBackend,
        'filings_pdf': records_alerters.FilingsPdf
    }

    @classmethod
    def factory(cls, name, *args, **kwargs):
        if name in cls.COLLECTIONS:
            return cls._instantiate(cls.COLLECTIONS[name], args, kwargs)

    @classmethod
    def get_alerter(cls, name):
        return cls.COLLECTIONS.get(name)
