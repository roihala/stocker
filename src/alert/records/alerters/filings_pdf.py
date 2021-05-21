from src.alert.records.records_alerter import RecordsAlerter
from src.find.site import Site


class FilingsPdf(RecordsAlerter):
    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC', True)

    def _get_previous_date(self, diffs):
        # No previous date for unknown tickers
        return None

    def _get_record_title(self, diff):
        return diff.get('url')
