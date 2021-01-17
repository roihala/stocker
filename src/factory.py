import logging

from src.alert.alerter_base import AlerterBase
from src.collect import collectors
from src.alert import alerters
from src.collect.collector_base import CollectorBase


class Factory(object):
    COLLECTOR_INDEX = 0
    ALERTER_INDEX = 1
    SUB_COLLECTIONS_INDEX = 2

    COLLECTIONS = {
        'profile': (collectors.Profile, alerters.Profile, {'securities': (collectors.Securities, alerters.Securities)}),
        'symbols': (collectors.Symbols, alerters.Symbols)
    }

    @staticmethod
    def collectors_factory(name, sub_collection=None, *args, **kwargs) -> CollectorBase:
        if not sub_collection:
            return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.COLLECTOR_INDEX], args, kwargs)
        else:
            sub_collections = Factory.__get_sub_collections_dict(name)
            if sub_collection in sub_collections:
                return Factory.__instantiate(sub_collections[sub_collection][Factory.COLLECTOR_INDEX], args, kwargs)

        return None

    @staticmethod
    def alerters_factory(name, sub_collection=None, *args, **kwargs) -> AlerterBase:
        if not sub_collection:
            return Factory.__instantiate(Factory.COLLECTIONS[name][Factory.ALERTER_INDEX], args, kwargs)
        else:
            sub_collections = Factory.__get_sub_collections_dict(name)
            if sub_collection in sub_collections.keys():
                return Factory.__instantiate(sub_collections[sub_collection][Factory.ALERTER_INDEX], args, kwargs)

        return None

    @staticmethod
    def get_sub_collections(name):
        return Factory.__get_sub_collections_dict(name).keys()

    @staticmethod
    def __get_sub_collections_dict(name):
        if len(Factory.COLLECTIONS[name]) > Factory.SUB_COLLECTIONS_INDEX:
            return Factory.COLLECTIONS[name][Factory.SUB_COLLECTIONS_INDEX]
        return {}

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
    def get_match(cls):
        if issubclass(cls, CollectorBase):
            return Factory.COLLECTIONS[cls.__name__.lower()][Factory.ALERTER_INDEX]
        elif issubclass(cls, AlerterBase):
            return Factory.COLLECTIONS[cls.__name__.lower()][Factory.COLLECTOR_INDEX]
        else:
            return None
