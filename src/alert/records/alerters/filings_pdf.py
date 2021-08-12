from src.alert.records.filings_alerter import FilingsAlerter
from src.find.site import Site
from src.read.reader_base import ReaderBase


class FilingsPdf(FilingsAlerter):
    @property
    def site(self) -> Site:
        return Site('filings',
                    'https://backend.otcmarkets.com/otcapi/company/{ticker}/financial-report?symbol={'
                    'ticker}&page=1&pageSize=50&statusId=A&sortOn=releaseDate&sortDir=DESC', True)

    def generate_msg(self, diffs, prev_date):
        msg = '\n'.join(['{green_circle_emoji} {cloud_path}'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                                    cloud_path=ReaderBase.escape_markdown(diff.get('cloud_path'))) for diff in diffs])

        return f"*Filings* added:\n{msg}\nPrevious filing date: " \
            f"{ReaderBase.format_stocker_date(prev_date, format='YYYY-MM-DD', style='_')}\n"
