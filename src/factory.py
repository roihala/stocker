import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors
from src.alert import alerters
from src.collect.collector_base import CollectorBase


class Factory(object):
    COLLECTOR_INDEX = 0
    ALERTER_INDEX = 1

    COLLECTIONS = {
        'symbols': (collectors.Symbols, alerters.Symbols),
        'profile': (collectors.Profile, alerters.Profile),
        'prices': (collectors.Prices, alerters.Prices),
        'securities': (collectors.Securities, alerters.Securities)
    }

    @staticmethod
    def colleectors_factory(name, *args, **kwargs) -> CollectorBase:
        return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.COLLECTOR_INDEX], args, kwargs)

    @staticmethod
    def alerters_factory(name, *args, **kwargs) -> AlerterBase:
        return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.ALERTER_INDEX], args, kwargs)

    @staticmethod
    def __instantiate(obj, args, kwargs):
        try:
            return obj(*args, **kwargs)
        except Exception as e:
            logging.getLogger('collector').exception('Could not create an instance of {obj}. exception: {e}'
                                                     .format(obj=obj, e=e))

    @staticmethod
    def resolve_name(obj):
        for name, collections in Factory.COLLECTIONS.items():
            if obj in collections:
                return name

        raise ValueError("Can't resolve name for {obj}".format(obj=obj))
