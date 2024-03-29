from src.base_factory import BaseFactory
from src.collect.records import collectors as records_collectors


class RecordsFactory(BaseFactory):
    COLLECTIONS = {
        'filings_backend': records_collectors.FilingsBackend,
        'filings_pdf': records_collectors.FilingsPdf
    }

    @classmethod
    def factory(cls, name, *args, **kwargs):
        if name in cls.COLLECTIONS:
            return cls._instantiate(cls.COLLECTIONS[name], args, kwargs)
