from src.alert.records.records_alerter import RecordsAlerter
from src.find.site import Site


class FilingsPdf(RecordsAlerter):
    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={'
                    'ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC', True)

    def generate_msg(self, diffs):
        return f'{self.GREEN_CIRCLE_EMOJI_UNICODE} filings added'

    def generate_payload(self, diffs):
        payload = super().generate_payload(diffs)

        payload.update({'pdf_record_ids': [diff.get('record_id') for diff in diffs]})
        return payload
