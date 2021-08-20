from src.base_factory import BaseFactory
from src.read import readers


class ReadersFactory(BaseFactory):
    COLLECTIONS = {
        'profile': readers.Profile,
        'securities': readers.Securities,
        'symbols': readers.Symbols,
        'otciq': readers.Otciq
    }

    @classmethod
    def factory(cls, name, *args, **kwargs):
        if name in cls.COLLECTIONS:
            return cls._instantiate(cls.COLLECTIONS[name], args, kwargs)
