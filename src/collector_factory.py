from src.base_factory import BaseFactory
from src.collect.tickers import collectors as ticker_collectors


class CollectorsFactory(BaseFactory):
    COLLECTIONS = {
        'profile': ticker_collectors.Profile,
        'securities': ticker_collectors.Securities,
        'symbols': ticker_collectors.Symbols,
    }

    @classmethod
    def factory(cls, name, *args, **kwargs):
        if name in cls.COLLECTIONS:
            return cls._instantiate(cls.COLLECTIONS[name], args, kwargs)

    @classmethod
    def get_collectors(cls):
        return [_ for _ in cls.COLLECTIONS.values()]

    @classmethod
    def get_collector(cls, name):
        return cls.COLLECTIONS.get(name)

    @classmethod
    def get_father_collections(cls):
        # Securities is son of profile
        return [collection for collection in cls.COLLECTIONS if collection != 'securities']
