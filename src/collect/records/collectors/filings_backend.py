from src.collect.records.records_collector import RecordsCollector


class FilingsBackend(RecordsCollector):
    @property
    def filing_base_url(self):
        return 'https://backend.otcmarkets.com/otcapi/company/financial-report/{id}/content'

    @property
    def records_url(self):
        return 'https://backend.otcmarkets.com/otcapi/company/financial-report/?pageSize=50&page=1&sortOn=releaseDate&sortDir=DESC'
