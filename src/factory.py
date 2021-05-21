import logging

from src.collect.tickers import collectors as ticker_collectors
from src.collect.records import collectors as records_collectors
from src.alert.tickers import alerters as ticker_alerters
from src.alert.records import alerters as records_alerters
from src.read import readers
from src.alert.alerter_base import AlerterBase
from src.collect.tickers.ticker_collector import TickerCollector
from src.read.reader_base import ReaderBase


class Factory(object):
    COLLECTOR_INDEX = 0
    ALERTER_INDEX = 1
    READER_INDEX = 2

    TICKER_COLLECTIONS = {
        'profile': (ticker_collectors.Profile, ticker_alerters.Profile, readers.Profile),
        'securities': (ticker_collectors.Securities, ticker_alerters.Securities, readers.Securities),
        'symbols': (ticker_collectors.Symbols, ticker_alerters.Symbols, readers.Symbols)
    }

    RECORDS_COLLECTIONS = {
        'filings': (records_collectors.Filings, records_alerters.Filings),
        'filings_pdf': (records_collectors.FilingsPdf, records_alerters.FilingsPdf),
        'secfilings': (None, records_alerters.SecFilings)
    }

    @staticmethod
    def collectors_factory(name, *args, **kwargs) -> TickerCollector:
        if name in Factory.TICKER_COLLECTIONS:
            return Factory.__instantiate(Factory.TICKER_COLLECTIONS[name][Factory.COLLECTOR_INDEX], args, kwargs)
        elif name in Factory.RECORDS_COLLECTIONS:
            return Factory.__instantiate(Factory.RECORDS_COLLECTIONS[name][Factory.COLLECTOR_INDEX], args, kwargs)

    @staticmethod
    def alerters_factory(name, *args, **kwargs) -> AlerterBase:
        if name in Factory.TICKER_COLLECTIONS:
            return Factory.__instantiate(Factory.TICKER_COLLECTIONS[name][Factory.ALERTER_INDEX], args, kwargs)
        elif name in Factory.RECORDS_COLLECTIONS:
            return Factory.__instantiate(Factory.RECORDS_COLLECTIONS[name][Factory.ALERTER_INDEX], args, kwargs)

    @staticmethod
    def readers_factory(name, *args, **kwargs) -> ReaderBase:
        return Factory.__instantiate(Factory.TICKER_COLLECTIONS[name][Factory.READER_INDEX], args, kwargs)

    @staticmethod
    def __instantiate(obj, args, kwargs):
        try:
            return obj(*args, **kwargs)

        except Exception as e:
            logging.getLogger('collector').exception('Could not create an instance of {obj}. exception: {e}'
                                                     .format(obj=obj, e=e))

    @staticmethod
    def get_tickers_collectors():
        return [value[Factory.COLLECTOR_INDEX] for value in Factory.TICKER_COLLECTIONS.values()]

    @staticmethod
    def get_collector(name):
        if name in Factory.TICKER_COLLECTIONS:
            return Factory.TICKER_COLLECTIONS[name][Factory.COLLECTOR_INDEX]
        elif name in Factory.RECORDS_COLLECTIONS:
            return Factory.RECORDS_COLLECTIONS[name][Factory.COLLECTOR_INDEX]

    @staticmethod
    def get_alerter(name):
        if name in Factory.TICKER_COLLECTIONS:
            return Factory.TICKER_COLLECTIONS[name][Factory.ALERTER_INDEX]
        elif name in Factory.RECORDS_COLLECTIONS:
            return Factory.RECORDS_COLLECTIONS[name][Factory.ALERTER_INDEX]
