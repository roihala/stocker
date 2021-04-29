from src.alert.records.alerters.sec_filings import SecFilings
from src.alert.records.records_alerter import RecordsAlerter
from src.find.site import Site


class Filings(RecordsAlerter):
    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC', True)

    @property
    def brothers(self):
        return [SecFilings(self._mongo_db, self._telegram_bot, self._batch, self._ticker)]
