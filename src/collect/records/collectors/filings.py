from typing import List, Dict

from src.collect.records.records_collector import RecordsCollector


class Filings(RecordsCollector):
    @property
    def url(self):
        #TODO
        return 'https://backend.otcmarkets.com/otcapi/company/financial-report/?pageSize=10&page=1&sortOn=releaseDate&sortDir=DESC'
