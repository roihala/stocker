from typing import List, Dict

from src.collect.records.records_collector import RecordsCollector


class Filings(RecordsCollector):
    @property
    def url(self):
        return 'https://backend.otcmarkets.com/otcapi/company/financial-report/?pageSize=50&page=1&sortOn=releaseDate&sortDir=DESC'
