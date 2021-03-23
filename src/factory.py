import logging

from src.collect import collectors
from src.alert import alerters
from src.read import readers
from src.alert.alerter_base import AlerterBase
from src.collect.collector_base import CollectorBase
from src.read.reader_base import ReaderBase


class Factory(object):
    COLLECTOR_INDEX = 0
    ALERTER_INDEX = 1
    READER_INDEX = 2

    COLLECTIONS = {
        'profile': (collectors.Profile, alerters.Profile, readers.Profile),
        'securities': (collectors.Securities, alerters.Securities, readers.Securities),
        'symbols': (collectors.Symbols, alerters.Symbols, readers.Symbols)
    }

    @staticmethod
    def collectors_factory(name, *args, **kwargs) -> CollectorBase:
        return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.COLLECTOR_INDEX], args, kwargs)

    @staticmethod
    def alerters_factory(name, *args, **kwargs) -> AlerterBase:
        return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.ALERTER_INDEX], args, kwargs)

    @staticmethod
    def readers_factory(name, *args, **kwargs) -> ReaderBase:
        return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.READER_INDEX], args, kwargs)

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

    @staticmethod
    def get_collector(name):
        return Factory.COLLECTIONS[name][Factory.COLLECTOR_INDEX]
