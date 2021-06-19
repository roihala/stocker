from src.collect.records.dynamic_records_collector import DynamicRecordsCollector


FILINGS_PDF_URL = 'http://www.otcmarkets.com/financialReportViewer?id={id}'


class FilingsPdf(DynamicRecordsCollector):
    @property
    def url(self):
        return FILINGS_PDF_URL
