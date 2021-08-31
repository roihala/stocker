from src.alert.records.filings_alerter import FilingsAlerter
from src.find.site import Site


class FilingsPdf(FilingsAlerter):
    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={'
                    'ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC', True)
