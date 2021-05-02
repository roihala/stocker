from src.alert.records.records_alerter import RecordsAlerter
from src.find.site import Site


class SecFilings(RecordsAlerter):
    @property
    def site(self) -> Site:
        return Site('sec_filings',
                    'https://backend.otcmarkets.com/otcapi/company/sec-filings/{ticker}?symbol={ticker}&page=1&pageSize=50',
                    True)
