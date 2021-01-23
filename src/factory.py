import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors
from src.alert import alerters
from src.collect.collector_base import CollectorBase


class Factory(object):
    COLLECTOR_INDEX = 0
    ALERTER_INDEX = 1

    COLLECTIONS = {
        'profile': (collectors.Profile, alerters.Profile),
        'securities': (collectors.Securities, alerters.Securities),
        'symbols': (collectors.Symbols, alerters.Symbols)
    }

    @staticmethod
    def collectors_factory(name, *args, **kwargs) -> CollectorBase:
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
    def get_alerters():
        return [value[Factory.ALERTER_INDEX] for value in Factory.COLLECTIONS.values()]

    @staticmethod
    def get_collectors():
        return [value[Factory.COLLECTOR_INDEX] for value in Factory.COLLECTIONS.values()]
